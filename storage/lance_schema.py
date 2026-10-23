"""Tabla vectorial LanceDB `jurisprudencia_chunks` (dossier §3.3)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import lancedb
import pyarrow as pa

TABLE = "jurisprudencia_chunks"
SECCIONES_INDEXABLES = ("fundamentos_mayoria", "fallo")  # nunca voto_particular


def juris_schema(dim: int) -> pa.Schema:
    return pa.schema(
        [
            pa.field("chunk_id", pa.string(), nullable=False),
            pa.field("roj_id", pa.string(), nullable=False),
            pa.field("ecli", pa.string()),
            pa.field("nivel", pa.string(), nullable=False),
            pa.field("tribunal", pa.string(), nullable=False),
            pa.field("jurisdiccion", pa.string(), nullable=False),
            pa.field("submaterias", pa.list_(pa.string())),
            pa.field("fecha_resolucion", pa.date32(), nullable=False),
            pa.field("seccion", pa.string(), nullable=False),
            pa.field("fd_numero", pa.int16()),
            pa.field("chunk_text", pa.string(), nullable=False),
            pa.field("normas_citadas", pa.list_(pa.string())),
            pa.field("vector", pa.list_(pa.float32(), dim), nullable=False),
            pa.field("embedding_model", pa.string(), nullable=False),
            pa.field("texto_hash", pa.string(), nullable=False),
        ]
    )


def chunk_text(text: str, *, max_chars: int = 2000, overlap: float = 0.15) -> list[str]:
    """Trozos de ~300–500 tokens con solape del 15 %, cortando preferentemente en fin de párrafo o frase."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    chunks: list[str] = []
    start = 0
    step_back = int(max_chars * overlap)
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            cut = max(text.rfind("\n", start + max_chars // 2, end), text.rfind(". ", start + max_chars // 2, end))
            if cut > start:
                end = cut + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - step_back, start + 1)
    return [c for c in chunks if c]


class JurisprudenciaStore:
    def __init__(self, directory: Path, dim: int) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(directory))
        self.dim = dim
        self._table = self._db.create_table(TABLE, schema=juris_schema(dim), exist_ok=True)

    def count(self) -> int:
        return int(self._table.count_rows())

    def delete_roj(self, roj_id: str) -> None:
        self._table.delete(f"roj_id = '{roj_id.replace(chr(39), chr(39) * 2)}'")

    def add(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            if row["seccion"] not in SECCIONES_INDEXABLES:
                raise ValueError(f"sección no indexable: {row['seccion']}")
            if len(row["vector"]) != self.dim:
                raise ValueError("dimensión de embedding incorrecta")
        if rows:
            self._table.add(rows)

    def search(
        self,
        vector: list[float],
        *,
        k: int = 20,
        jurisdiccion: str | None = None,
        niveles: list[str] | None = None,
        desde: date | None = None,
    ) -> list[dict[str, Any]]:
        filters = []
        if jurisdiccion:
            filters.append(f"jurisdiccion = '{jurisdiccion}'")
        if niveles:
            filters.append("nivel IN (" + ", ".join(f"'{n}'" for n in niveles) + ")")
        if desde:
            filters.append(f"fecha_resolucion >= date '{desde.isoformat()}'")
        query: Any = self._table.search(vector)
        query = query.distance_type("cosine")
        if filters:
            query = query.where(" AND ".join(filters), prefilter=True)
        return list(query.limit(k).to_list())
