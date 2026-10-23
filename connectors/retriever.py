"""Recuperación híbrida de jurisprudencia: FTS5 (BM25) + LanceDB (vector) con Reciprocal Rank Fusion."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date

from connectors.boe_client import fts_query
from connectors.embeddings import Embedder
from storage.lance_schema import JurisprudenciaStore

RRF_K = 60


@dataclass
class SentenciaRecuperada:
    roj_id: str
    score: float
    tribunal: str
    nivel: str
    jurisdiccion: str
    fecha_resolucion: date
    fragmentos: list[str] = field(default_factory=list)
    fuentes: set[str] = field(default_factory=set)  # {"bm25", "vector"}


def rrf(rankings: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for pos, key in enumerate(ranking, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + pos)
    return scores


class HybridRetriever:
    def __init__(
        self,
        con: sqlite3.Connection,
        *,
        store: JurisprudenciaStore | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self._con = con
        self._store = store
        self._embedder = embedder

    def _bm25(self, query: str, jurisdiccion: str | None, limit: int) -> list[tuple[str, str]]:
        sql = """SELECT s.roj_id, snippet(cendoj_fts, 0, '', '', '…', 48)
                 FROM cendoj_fts JOIN cendoj_sentencias s ON s.id = cendoj_fts.rowid
                 WHERE cendoj_fts MATCH ?"""
        params: list[object] = [fts_query(query)]
        if jurisdiccion:
            sql += " AND s.jurisdiccion = ?"
            params.append(jurisdiccion)
        sql += " ORDER BY bm25(cendoj_fts) LIMIT ?"
        params.append(limit)
        return [(r[0], r[1]) for r in self._con.execute(sql, params).fetchall()]

    async def _vector(self, query: str, jurisdiccion: str | None, limit: int) -> list[tuple[str, str]]:
        if self._store is None or self._embedder is None or self._store.count() == 0:
            return []
        [vector] = await self._embedder.embed([query], "RETRIEVAL_QUERY")
        rows = self._store.search(vector, k=limit, jurisdiccion=jurisdiccion)
        return [(r["roj_id"], r["chunk_text"]) for r in rows]

    async def search(
        self, query: str, *, jurisdiccion: str | None = None, k: int = 5, candidates: int = 20
    ) -> list[SentenciaRecuperada]:
        lexical = self._bm25(query, jurisdiccion, candidates)
        semantic = await self._vector(query, jurisdiccion, candidates)
        rank_lex = list(dict.fromkeys(r for r, _ in lexical))
        rank_vec = list(dict.fromkeys(r for r, _ in semantic))
        scores = rrf([rank_lex, rank_vec])
        fragments: dict[str, list[str]] = {}
        for roj, text in semantic + lexical:
            if text and text not in fragments.setdefault(roj, []):
                fragments[roj].append(text)
        results: list[SentenciaRecuperada] = []
        for roj, score in sorted(scores.items(), key=lambda kv: -kv[1])[:k]:
            row = self._con.execute(
                "SELECT tribunal, nivel, jurisdiccion, fecha_resolucion FROM cendoj_sentencias WHERE roj_id = ?",
                (roj,),
            ).fetchone()
            if row is None:
                continue
            results.append(
                SentenciaRecuperada(
                    roj_id=roj,
                    score=score,
                    tribunal=row[0],
                    nivel=row[1],
                    jurisdiccion=row[2],
                    fecha_resolucion=date.fromisoformat(row[3]),
                    fragmentos=fragments.get(roj, [])[:3],
                    fuentes={n for n, rank in (("bm25", rank_lex), ("vector", rank_vec)) if roj in rank},
                )
            )
        return results
