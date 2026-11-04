"""Recuperación híbrida de preceptos del corpus legal A LA FECHA DE LOS HECHOS (lista cerrada para el cribado).

Varias consultas (términos que propone el triaje + resumen de los hechos) se buscan por BM25 en la versión vigente en
la fecha; si hay embeddings, también por vectores con el mismo filtro de vigencia. Los rankings se fusionan con
Reciprocal Rank Fusion. El resultado es una lista de preceptos que EXISTEN en el BOE: el modelo solo puede elegir de
ella (docs/vision.md §3).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from connectors.boe_client import BOERepository, PreceptoEncontrado
from connectors.embeddings import Embedder
from connectors.retriever import rrf
from core.errors import ProviderError
from storage.lance_schema import LegislacionStore

log = logging.getLogger(__name__)


@dataclass
class Candidato:
    precepto: PreceptoEncontrado
    score: float
    fuentes: set[str] = field(default_factory=set)  # {"bm25", "vector"}

    @property
    def clave(self) -> tuple[str, str]:
        return (self.precepto.id_norma, self.precepto.id_bloque)


class RecuperadorLegislacion:
    def __init__(
        self, boe: BOERepository, *, store: LegislacionStore | None = None, embedder: Embedder | None = None
    ) -> None:
        self._boe = boe
        self._store = store
        self._embedder = embedder

    @property
    def vectorial(self) -> bool:
        return self._store is not None and self._embedder is not None and self._store.count() > 0

    async def buscar(
        self,
        consultas: list[str],
        fecha: date,
        *,
        normas: list[str] | None = None,
        k: int = 30,
        por_consulta: int = 25,
    ) -> list[Candidato]:
        consultas = list(dict.fromkeys(q.strip() for q in consultas if q and q.strip()))
        if not consultas:
            return []
        info: dict[tuple[str, str], PreceptoEncontrado] = {}
        rankings: list[list[tuple[str, str]]] = []
        lexicos: set[tuple[str, str]] = set()
        for q in consultas:
            ranking = []
            for h in self._boe.buscar_a_fecha(q, fecha, normas=normas, limit=por_consulta):
                clave = (h.id_norma, h.id_bloque)
                info.setdefault(clave, h)
                if clave not in ranking:
                    ranking.append(clave)
            lexicos.update(ranking)
            rankings.append(ranking)
        vectoriales: set[tuple[str, str]] = set()
        if self.vectorial:
            assert self._store is not None and self._embedder is not None
            try:
                [vector] = await self._embedder.embed([" ".join(consultas)[:2000]], "RETRIEVAL_QUERY")
                ranking_vec: list[tuple[str, str]] = []
                for row in self._store.search(vector, fecha=fecha, normas=normas, k=por_consulta * 2):
                    clave = (str(row["id_norma"]), str(row["id_bloque"]))
                    if clave in ranking_vec:
                        continue
                    if clave not in info:
                        p = self._boe.precepto_a_fecha(clave[0], clave[1], fecha)
                        if p is None:
                            continue
                        info[clave] = p
                    ranking_vec.append(clave)
                vectoriales = set(ranking_vec)
                # Pesa como el conjunto de las consultas léxicas, no como una más.
                rankings.extend([ranking_vec] * max(1, len(consultas) // 2))
            except (ProviderError, OSError, ValueError) as exc:
                log.warning("Búsqueda vectorial de legislación no disponible: %s", exc)
        puntuaciones = rrf([[f"{a}|{b}" for a, b in r] for r in rankings])
        salida = []
        for clave_txt, score in sorted(puntuaciones.items(), key=lambda kv: -kv[1])[:k]:
            a, b = clave_txt.split("|", 1)
            clave = (a, b)
            salida.append(
                Candidato(
                    precepto=info[clave],
                    score=score,
                    fuentes={n for n, s in (("bm25", lexicos), ("vector", vectoriales)) if clave in s},
                )
            )
        return salida
