"""Cliente de la API de Datos Abiertos del BOE y repositorio con caché SQLite (dossier §1.2.1)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sqlite3
import time
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from connectors.boe_models import (
    Bloque,
    BloqueVersion,
    IndiceEntry,
    NormaMeta,
    articulo_to_bloque,
    parse_bloque_xml,
    parse_indice_json,
)
from core.normalize import fold, normalize

BASE_URL = "https://www.boe.es/datosabiertos/api/legislacion-consolidada"
USER_AGENT = "IurisIA/0.1 (asistente legal personal; uso no comercial)"


class BOEError(Exception):
    pass


class BOEClient:
    """Acceso HTTP cortés: como máximo `max_rps` peticiones por segundo."""

    def __init__(self, *, client: httpx.AsyncClient | None = None, max_rps: float = 2.0) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=BASE_URL, headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True
        )
        self._interval = 1.0 / max_rps
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, accept: str) -> httpx.Response:
        async with self._lock:
            wait = self._interval - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()
        try:
            response = await self._client.get(path, headers={"Accept": accept})
        except httpx.HTTPError as exc:
            raise BOEError(f"BOE no accesible: {exc}") from exc
        if response.status_code == 404:
            raise BOEError(f"no encontrado en el BOE: {path}")
        if response.status_code >= 400:
            raise BOEError(f"BOE respondió {response.status_code} en {path}")
        return response

    async def metadatos(self, id_norma: str) -> NormaMeta:
        response = await self._get(f"/id/{id_norma}/metadatos", "application/json")
        data = response.json().get("data")
        items = data if isinstance(data, list) else [data]
        if not items or not items[0]:
            raise BOEError(f"sin metadatos para {id_norma}")
        return NormaMeta.from_api(items[0])

    async def indice(self, id_norma: str) -> list[IndiceEntry]:
        response = await self._get(f"/id/{id_norma}/texto/indice", "application/json")
        return parse_indice_json(response.json())

    async def bloque(self, id_norma: str, id_bloque: str) -> Bloque:
        response = await self._get(f"/id/{id_norma}/texto/bloque/{id_bloque}", "application/xml")
        try:
            return parse_bloque_xml(id_norma, response.content)
        except ValueError as exc:
            raise BOEError(str(exc)) from exc


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


class BOERepository:
    """Caché-first: SQLite (`boe_normas`, `boe_bloques`) y, si falta o caducó, la API."""

    def __init__(self, con: sqlite3.Connection, client: BOEClient, *, ttl_days: int = 7) -> None:
        self._con = con
        self._client = client
        self._ttl = timedelta(days=ttl_days)
        self._indices: dict[str, dict[str, str]] = {}

    async def resolve_bloque(self, id_norma: str, articulo: str) -> str:
        """Cada norma nombra sus bloques a su manera (LAU: 'a36'; Código Civil: 'art1561'; Ley 15/2022:
        'a2-8' para el art. 26). Se resuelve con el índice oficial de la norma (cacheado en memoria):
        primero por id, después por el título del bloque ("Artículo 26")."""
        base = articulo_to_bloque(articulo)
        if not base.startswith("a") or not base[1:2].isdigit():
            return base
        if id_norma not in self._indices:
            try:
                self._indices[id_norma] = {e.id_bloque: e.titulo for e in await self._client.indice(id_norma)}
            except BOEError:
                self._indices[id_norma] = {}
        indice = self._indices[id_norma]
        numero = base[1:]
        for candidato in (base, "art" + numero):
            if candidato in indice and _titulo_es_articulo(indice[candidato], numero) is not False:
                return candidato
        for id_bloque, titulo in indice.items():
            if _titulo_es_articulo(titulo, numero):
                return id_bloque
        cached = self._con.execute(
            "SELECT id_bloque FROM boe_bloques WHERE id_norma = ? AND id_bloque IN (?, ?) LIMIT 1",
            (id_norma, base, "art" + base[1:]),
        ).fetchone()
        return str(cached[0]) if cached else base

    # ---------- normas ----------
    async def ensure_norma(self, id_norma: str) -> NormaMeta:
        row = self._con.execute(
            "SELECT metadatos_json, fetched_at FROM boe_normas WHERE id_norma = ?", (id_norma,)
        ).fetchone()
        if row and not self._expired(row[1]):
            return NormaMeta.from_api(json.loads(row[0]))
        meta = await self._client.metadatos(id_norma)
        self._con.execute(
            """INSERT INTO boe_normas(id_norma, titulo, rango, ambito, estado, fecha_actualizacion, metadatos_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id_norma) DO UPDATE SET titulo=excluded.titulo, rango=excluded.rango,
                 ambito=excluded.ambito, estado=excluded.estado, fecha_actualizacion=excluded.fecha_actualizacion,
                 metadatos_json=excluded.metadatos_json, fetched_at=datetime('now')""",
            (
                id_norma,
                meta.titulo,
                meta.rango,
                meta.ambito,
                "derogada" if meta.derogada else "vigente",
                meta.fecha_actualizacion,
                json.dumps(meta.raw, ensure_ascii=False),
            ),
        )
        return meta

    def _expired(self, fetched_at: str | None) -> bool:
        if not fetched_at:
            return True
        now = datetime.now(UTC).replace(tzinfo=None)  # SQLite guarda datetime('now') en UTC sin zona
        return now - datetime.fromisoformat(fetched_at) > self._ttl

    # ---------- bloques ----------
    def _cached_bloque(self, id_norma: str, id_bloque: str) -> Bloque | None:
        rows = self._con.execute(
            """SELECT titulo, version_vigencia_desde, version_vigencia_hasta, id_norma_modificadora,
                      texto_consolidado, cached_at
               FROM boe_bloques WHERE id_norma = ? AND id_bloque = ? ORDER BY version_vigencia_desde""",
            (id_norma, id_bloque),
        ).fetchall()
        if not rows or self._expired(rows[-1][5]):
            return None
        return Bloque(
            id_norma=id_norma,
            id_bloque=id_bloque,
            titulo=rows[0][0] or "",
            versiones=[
                BloqueVersion(
                    id_norma_modificadora=r[3] or id_norma,
                    fecha_publicacion=None,
                    vigencia_desde=date.fromisoformat(r[1]),
                    vigencia_hasta=date.fromisoformat(r[2]) if r[2] else None,
                    texto=r[4],
                )
                for r in rows
            ],
        )

    def _store_bloque(self, bloque: Bloque) -> None:
        self._con.execute("BEGIN")
        try:
            self._con.execute(
                "DELETE FROM boe_bloques WHERE id_norma = ? AND id_bloque = ?", (bloque.id_norma, bloque.id_bloque)
            )
            for v in bloque.versiones:
                self._con.execute(
                    """INSERT INTO boe_bloques(id_norma, id_bloque, titulo, version_vigencia_desde,
                           version_vigencia_hasta, id_norma_modificadora, texto_consolidado, texto_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        bloque.id_norma,
                        bloque.id_bloque,
                        bloque.titulo,
                        v.vigencia_desde.isoformat(),
                        _iso(v.vigencia_hasta),
                        v.id_norma_modificadora,
                        v.texto,
                        hashlib.sha256(normalize(v.texto).encode("utf-8")).hexdigest(),
                    ),
                )
            self._con.execute("COMMIT")
        except Exception:
            self._con.execute("ROLLBACK")
            raise

    async def get_bloque(self, id_norma: str, id_bloque: str, *, refresh: bool = False) -> Bloque:
        if not refresh:
            cached = self._cached_bloque(id_norma, id_bloque)
            if cached is not None:
                return cached
        await self.ensure_norma(id_norma)
        bloque = await self._client.bloque(id_norma, id_bloque)
        self._store_bloque(bloque)
        return bloque

    async def get_articulo(self, id_norma: str, articulo: str) -> Bloque:
        return await self.get_bloque(id_norma, await self.resolve_bloque(id_norma, articulo))

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Búsqueda léxica (FTS5/BM25) sobre la versión vigente de los bloques cacheados."""
        rows = self._con.execute(
            """SELECT b.id_norma, b.id_bloque, b.titulo, snippet(boe_bloques_fts, 0, '[', ']', '…', 12)
               FROM boe_bloques_fts JOIN boe_bloques b ON b.id = boe_bloques_fts.rowid
               WHERE boe_bloques_fts MATCH ? AND b.version_vigencia_hasta IS NULL
               ORDER BY bm25(boe_bloques_fts) LIMIT ?""",
            (fts_query(query), limit),
        ).fetchall()
        return [{"id_norma": r[0], "id_bloque": r[1], "titulo": r[2], "snippet": r[3]} for r in rows]


_ORDINALES = [
    "primero",
    "segundo",
    "tercero",
    "cuarto",
    "quinto",
    "sexto",
    "septimo",
    "octavo",
    "noveno",
    "diez",
    "once",
    "doce",
    "trece",
    "catorce",
    "quince",
    "dieciseis",
    "diecisiete",
    "dieciocho",
    "diecinueve",
    "veinte",
    "veintiuno",
    "veintidos",
    "veintitres",
    "veinticuatro",
    "veinticinco",
    "veintiseis",
    "veintisiete",
    "veintiocho",
    "veintinueve",
    "treinta",
]
_NUM_PALABRA = {w: str(i) for i, w in enumerate(_ORDINALES, start=1)}


def _titulo_es_articulo(titulo: str, numero: str) -> bool | None:
    """True/False si el título ("Artículo 26", "Artículo 36 bis", "Artículo noveno" en la LPH, "Artículo 121-21" en
    el Código civil de Cataluña) corresponde al número; None si el bloque no es un artículo."""
    m = re.match(r"^\s*art[íi]culo\s+(\d+(?:-\d+)?|[a-záéíóúü]+)\s*(bis|ter|quater)?\b", fold(titulo or ""), re.I)
    if not m:
        return None
    valor = m.group(1) if m.group(1)[0].isdigit() else _NUM_PALABRA.get(m.group(1))
    if valor is None:
        return None
    return (valor + (m.group(2) or "").lower()) == numero


def fts_query(text: str) -> str:
    """Convierte texto libre en una consulta FTS5 segura (términos OR entre comillas)."""
    terms = [t for t in "".join(c if c.isalnum() else " " for c in text).split() if len(t) > 2]
    return " OR ".join(f'"{t}"' for t in terms[:16]) or '""'
