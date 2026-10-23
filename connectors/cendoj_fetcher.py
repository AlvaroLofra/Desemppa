"""Corpus local de jurisprudencia (Cache-First) — dossier §1.2.2.

Sin `playwright-stealth`: el corpus crece por (a) importación de sentencias que aporta el usuario
(PDF/texto o URL concreta) y (b) un fetcher identificado y cortés (1 petición / 10 s, tope diario),
que solo descarga URLs concretas; no automatiza el buscador del CENDOJ.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import date

import httpx

from connectors.cendoj_parser import SentenciaParseada, parse_sentencia
from connectors.embeddings import Embedder
from connectors.pdf_extractor import extract_pdf
from core.normalize import normalize
from storage.lance_schema import JurisprudenciaStore, chunk_text

USER_AGENT = "IurisIA/0.1 (asistente legal personal; uso no comercial; descarga puntual)"
_NORMA_CITADA_RE = re.compile(
    r"art(?:[íi]culo|\.)s?\s+(\d+(?:\s?bis|\s?ter)?)(?:[^.;\n]{0,60}?)\b(LEC|LAU|ET|LRJS|LPH|CC|C[óo]digo Civil|"
    r"LJCA|TRLGDCU|LGT|CE)\b",
    re.I,
)


class FetchLimitReached(Exception):
    pass


class PoliteFetcher:
    def __init__(
        self,
        *,
        min_interval_s: float = 10.0,
        daily_cap: int = 200,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True
        )
        self._interval = min_interval_s
        self._cap = daily_cap
        self._last = 0.0
        self._day = date.today()
        self._count = 0
        self._lock = asyncio.Lock()
        self.last_user_agent: str | None = None

    async def get(self, url: str) -> httpx.Response:
        async with self._lock:
            if date.today() != self._day:
                self._day, self._count = date.today(), 0
            if self._count >= self._cap:
                raise FetchLimitReached(f"tope diario de {self._cap} descargas alcanzado")
            wait = self._interval - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()
            self._count += 1
        response = await self._client.get(url, headers={"User-Agent": USER_AGENT})
        self.last_user_agent = response.request.headers.get("user-agent")
        response.raise_for_status()
        return response

    async def aclose(self) -> None:
        await self._client.aclose()


def infer_jurisdiccion(parsed: SentenciaParseada, text: str) -> str:
    probe = f"{parsed.organo or ''} {text[:3000]}".lower()
    if "social" in probe:
        return "social"
    if "contencioso" in probe:
        return "contencioso"
    if "penal" in probe:
        return "penal"
    if "militar" in probe:
        return "militar"
    return "civil"


def normas_citadas(text: str) -> list[str]:
    found = {f"{m.group(2).upper()}:a{m.group(1).replace(' ', '').lower()}" for m in _NORMA_CITADA_RE.finditer(text)}
    return sorted(found)


@dataclass
class ImportResult:
    roj_id: str
    nueva: bool
    chunks_indexados: int
    avisos: list[str]


class CendojRepository:
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

    async def import_pdf(self, data: bytes, **kwargs: object) -> ImportResult:
        return await self.import_text(extract_pdf(data).text, **kwargs)  # type: ignore[arg-type]

    async def import_text(
        self,
        text: str,
        *,
        submaterias: list[str] | None = None,
        origen: str = "import_usuario",
        url: str | None = None,
        roj_hint: str | None = None,
    ) -> ImportResult:
        parsed = parse_sentencia(text)
        avisos: list[str] = []
        roj = parsed.roj or roj_hint
        if not roj:
            raise ValueError("no se encuentra el identificador ROJ en el texto de la sentencia")
        if parsed.fecha is None:
            raise ValueError(f"{roj}: no se encuentra la fecha de la resolución")
        if not parsed.fundamentos or not parsed.fallo:
            avisos.append(f"{roj}: segmentación incompleta (fundamentos o fallo no detectados)")
        if parsed.votos_particulares:
            avisos.append(f"{roj}: {len(parsed.votos_particulares)} voto(s) particular(es) aislado(s)")
        jurisdiccion = infer_jurisdiccion(parsed, text)
        existed = self._con.execute("SELECT 1 FROM cendoj_sentencias WHERE roj_id = ?", (roj,)).fetchone()
        values = (
            roj,
            parsed.ecli,
            parsed.organo or "desconocido",
            parsed.nivel or "JUZGADO",
            jurisdiccion,
            json.dumps(submaterias or [], ensure_ascii=False),
            parsed.fecha.isoformat(),
            parsed.ponente,
            parsed.antecedentes_purgados,
            parsed.fundamentos or "",
            parsed.fallo or "",
            "\n\n---\n\n".join(parsed.votos_particulares) or None,
            json.dumps(normas_citadas(parsed.fundamentos), ensure_ascii=False),
            origen,
            url,
            hashlib.sha256(normalize(text).encode("utf-8")).hexdigest(),
        )
        self._con.execute(
            """INSERT INTO cendoj_sentencias(roj_id, ecli, tribunal, nivel, jurisdiccion, submaterias,
                   fecha_resolucion, ponente, antecedentes_purgados, fundamentos_mayoria, fallo, voto_particular,
                   normas_citadas, origen, url_oficial, texto_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(roj_id) DO UPDATE SET ecli=excluded.ecli, tribunal=excluded.tribunal,
                 nivel=excluded.nivel, jurisdiccion=excluded.jurisdiccion, submaterias=excluded.submaterias,
                 fecha_resolucion=excluded.fecha_resolucion, ponente=excluded.ponente,
                 antecedentes_purgados=excluded.antecedentes_purgados,
                 fundamentos_mayoria=excluded.fundamentos_mayoria, fallo=excluded.fallo,
                 voto_particular=excluded.voto_particular, normas_citadas=excluded.normas_citadas,
                 url_oficial=excluded.url_oficial, texto_hash=excluded.texto_hash, cached_at=datetime('now')""",
            values,
        )
        indexed = await self._index(roj, parsed, jurisdiccion, submaterias or [])
        if self._store is None or self._embedder is None:
            avisos.append(f"{roj}: sin índice vectorial (solo búsqueda léxica)")
        return ImportResult(roj_id=roj, nueva=existed is None, chunks_indexados=indexed, avisos=avisos)

    async def _index(self, roj: str, parsed: SentenciaParseada, jurisdiccion: str, submaterias: list[str]) -> int:
        if self._store is None or self._embedder is None or parsed.fecha is None:
            return 0
        pieces: list[tuple[str, int | None, str]] = []
        for n, (_, body) in enumerate(parsed.fundamentos_lista, start=1):
            pieces.extend(("fundamentos_mayoria", n, c) for c in chunk_text(body))
        pieces.extend(("fallo", None, c) for c in chunk_text(parsed.fallo))
        if not pieces:
            return 0
        vectors = await self._embedder.embed([p[2] for p in pieces], "RETRIEVAL_DOCUMENT")
        rows = [
            {
                "chunk_id": f"{roj}#{seccion}#{i}",
                "roj_id": roj,
                "ecli": parsed.ecli,
                "nivel": parsed.nivel or "JUZGADO",
                "tribunal": parsed.organo or "desconocido",
                "jurisdiccion": jurisdiccion,
                "submaterias": submaterias,
                "fecha_resolucion": parsed.fecha,
                "seccion": seccion,
                "fd_numero": fd,
                "chunk_text": chunk,
                "normas_citadas": normas_citadas(chunk),
                "vector": vec,
                "embedding_model": self._embedder.model,
                "texto_hash": hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
            }
            for i, ((seccion, fd, chunk), vec) in enumerate(zip(pieces, vectors, strict=True))
        ]
        self._store.delete_roj(roj)
        self._store.add(rows)
        return len(rows)

    # ---------- cola de búsquedas en background ----------
    def enqueue(self, query: str, prioridad: int = 5) -> int:
        cur = self._con.execute("INSERT INTO cendoj_fetch_queue(query, prioridad) VALUES (?, ?)", (query, prioridad))
        return int(cur.lastrowid or 0)

    def pending(self, limit: int = 10) -> list[tuple[int, str]]:
        rows = self._con.execute(
            "SELECT id, query FROM cendoj_fetch_queue WHERE estado = 'pendiente' ORDER BY prioridad, id LIMIT ?",
            (limit,),
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    def detalle(self, roj_id: str) -> dict[str, str | None] | None:
        row = self._con.execute(
            "SELECT ecli, fundamentos_mayoria, fallo, url_oficial FROM cendoj_sentencias WHERE roj_id = ?", (roj_id,)
        ).fetchone()
        if row is None:
            return None
        return {"ecli": row[0], "fundamentos": row[1], "fallo": row[2], "url": row[3]}

    def count(self) -> int:
        return int(self._con.execute("SELECT count(*) FROM cendoj_sentencias").fetchone()[0])
