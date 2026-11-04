"""Cliente de la API de Datos Abiertos del BOE y repositorio con caché SQLite (dossier §1.2.1)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sqlite3
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from lxml import etree

from connectors.boe_models import (
    Bloque,
    BloqueVersion,
    IndiceEntry,
    NormaMeta,
    articulo_to_bloque,
    parse_bloque_xml,
    parse_indice_json,
    parse_texto_xml,
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

    async def _get(
        self, path: str, accept: str, params: dict[str, Any] | None = None, *, timeout: float | None = None
    ) -> httpx.Response:
        async with self._lock:
            wait = self._interval - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()
        try:
            kwargs: dict[str, Any] = {"headers": {"Accept": accept}}
            if params is not None:
                kwargs["params"] = params
            if timeout is not None:
                kwargs["timeout"] = timeout
            response = await self._client.get(path, **kwargs)
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

    async def buscar_normas(self, terminos: str, *, limit: int = 20) -> list[NormaMeta]:
        """Busca en el catálogo de legislación consolidada normas cuyo título contenga todas las palabras de
        `terminos` (sintaxis `query_string` de la documentación oficial de la API). El LLM solo aporta palabras:
        se quitan signos para que no pueda inyectar campos u operadores, y las derogadas se descartan aquí.
        Pendiente de verificar en vivo: el 01-11-2026 el BOE respondía 500 incluso a sus ejemplos documentados
        (ver `tests/contract/test_live_boe_busqueda.py`)."""
        palabras = [p for p in re.findall(r"\w+", fold(terminos)) if len(p) > 2 and not p.isdigit()][:6]
        if not palabras:
            return []
        consulta = {"query": {"query_string": {"query": " and ".join(f"titulo:{p}" for p in palabras)}}}
        params = {"query": json.dumps(consulta, ensure_ascii=False), "limit": limit}
        # Ruta absoluta: con base_url y ruta vacía httpx añadiría una "/" final que no es el recurso documentado.
        response = await self._get(str(self._client.base_url).rstrip("/"), "application/json", params)
        data = response.json().get("data")
        items = data if isinstance(data, list) else [data] if data else []
        normas = [NormaMeta.from_api(i) for i in items if isinstance(i, dict) and i.get("identificador")]
        return [n for n in normas if not n.derogada]

    async def texto_completo(self, id_norma: str) -> list[Bloque]:
        """Todos los bloques de la norma, con todas sus versiones, en una sola petición (`/id/{id}/texto`).

        SIN VERIFICAR EN VIVO (04-11-2026, entorno sin acceso al BOE): se asume que cada <bloque> tiene la misma forma
        que la respuesta de `/texto/bloque/{id}`. Si la respuesta no trae bloques, se lanza BOEError y quien llama
        descarga bloque a bloque (`indice` + `bloque`, verificados). Lo comprueba
        `tests/contract/test_live_boe_corpus.py` (`-m live`)."""
        response = await self._get(f"/id/{id_norma}/texto", "application/xml", timeout=180)
        try:
            bloques = parse_texto_xml(id_norma, response.content)
        except (ValueError, etree.XMLSyntaxError) as exc:
            raise BOEError(f"texto completo de {id_norma} ilegible: {exc}") from exc
        if not bloques:
            raise BOEError(f"el texto completo de {id_norma} no trae bloques")
        return bloques


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _claves_identidad(id_norma: str) -> list[str]:
    """Palabras que el título oficial debe contener (`titulo_boe_contiene` en config/catalogo_normas.json).

    Solo las llevan las normas cuyo identificador no se ha podido verificar al añadirlas: así un identificador
    equivocado nunca sirve el texto de otra ley, porque el BOE lo desmiente en tiempo real."""
    from core.materias import normas  # import diferido: core.materias no depende de connectors

    for meta in normas().values():
        if meta.get("id") == id_norma:
            return [fold(str(c)).lower() for c in meta.get("titulo_boe_contiene", [])]
    return []


@dataclass(frozen=True)
class PreceptoEncontrado:
    """Un precepto del corpus local en la versión vigente a la fecha pedida."""

    id_norma: str
    id_bloque: str
    titulo: str
    vigencia_desde: date
    vigencia_hasta: date | None
    inicio: str  # comienzo del texto de esa versión
    ubicacion: str
    score: float  # bm25: cuanto más negativo, más pertinente


# Palabras vacías del español (sin tildes): en una consulta OR solo añaden ruido al BM25.
_VACIAS = frozenset(
    """
    al algo algun alguna algunas alguno algunos ante antes aqui asi aun cada como con contra cual cuales cuando de del
    desde donde durante el ella ellas ellos en entre era eran es esa esas ese eso esos esta estaba estado estan estar
    estas este esto estos fue fueron ha habia han hasta hay he hemos la las le les lo los mas me mi mis mucho muy nada
    ni no nos nosotros nuestra nuestro o os otra otras otro otros para pero poco por porque puede pueden puedo que
    quien quiero se sea segun ser si sido sin sobre son su sus tambien te tengo tiene tienen todo todos tu tus un una
    uno unos usted ya yo
    """.split()
)


def consulta_fts_legal(texto: str, *, max_terminos: int = 24) -> str:
    """Consulta FTS5 para buscar preceptos: términos sin palabras vacías y, en los largos, también su raíz como
    prefijo («arrendamientos» -> "arrendamientos" OR "arrendamient"*), porque el índice no aplica lematización."""
    vistos: list[str] = []
    for t in "".join(c if c.isalnum() else " " for c in fold(texto).lower()).split():
        if len(t) > 2 and not t.isdigit() and t not in _VACIAS and t not in vistos:
            vistos.append(t)
    partes: list[str] = []
    for t in vistos[:max_terminos]:
        partes.append(f'"{t}"')
        if len(t) >= 7:
            partes.append(f'"{t[: max(5, len(t) - 3)]}"*')
    return " OR ".join(partes) or '""'


class BOERepository:
    """Caché-first: SQLite (`boe_normas`, `boe_bloques`) y, si falta o caducó, la API."""

    def __init__(self, con: sqlite3.Connection, client: BOEClient, *, ttl_days: int = 7) -> None:
        self._con = con
        self._client = client
        self._ttl = timedelta(days=ttl_days)
        self._indices: dict[str, dict[str, str]] = {}

    @property
    def client(self) -> BOEClient:
        return self._client

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
        titulo = fold(meta.titulo).lower()
        faltan = [c for c in _claves_identidad(id_norma) if c not in titulo]
        if faltan:
            raise BOEError(
                f"{id_norma} no es la norma esperada: su título oficial («{meta.titulo}») no contiene "
                f"«{', '.join(faltan)}»"
            )
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
    def _cached_bloque(self, id_norma: str, id_bloque: str, *, ignorar_caducidad: bool = False) -> Bloque | None:
        rows = self._con.execute(
            """SELECT titulo, version_vigencia_desde, version_vigencia_hasta, id_norma_modificadora,
                      texto_consolidado, cached_at
               FROM boe_bloques WHERE id_norma = ? AND id_bloque = ? ORDER BY version_vigencia_desde""",
            (id_norma, id_bloque),
        ).fetchall()
        if not rows or (not ignorar_caducidad and self._expired(rows[-1][5])):
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

    def get_bloque_local(self, id_norma: str, id_bloque: str) -> Bloque | None:
        """La copia local sin mirar su antigüedad (corpus descargado o caché caducada): respaldo cuando el BOE no
        responde. Quien la use debe avisar de que el texto es el de la última descarga."""
        return self._cached_bloque(id_norma, id_bloque, ignorar_caducidad=True)

    def descargado_en(self, id_norma: str, id_bloque: str) -> str | None:
        row = self._con.execute(
            "SELECT MAX(cached_at) FROM boe_bloques WHERE id_norma = ? AND id_bloque = ?", (id_norma, id_bloque)
        ).fetchone()
        return str(row[0]) if row and row[0] else None

    def store_bloque(self, bloque: Bloque) -> None:
        self._store_bloque(bloque)

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

    async def cachear_norma_completa(self, id_norma: str) -> int:
        """Descarga el texto completo de una norma en una sola petición y guarda en caché todos sus bloques con
        versiones, para que `search` (FTS5) pueda buscar en toda la ley. Devuelve cuántos bloques guardó."""
        await self.ensure_norma(id_norma)
        guardados = 0
        for bloque in await self._client.texto_completo(id_norma):
            if bloque.id_bloque and bloque.versiones:
                self._store_bloque(bloque)
                guardados += 1
        return guardados

    async def get_articulo(self, id_norma: str, articulo: str) -> Bloque:
        return await self.get_bloque(id_norma, await self.resolve_bloque(id_norma, articulo))

    def search(self, query: str, limit: int = 10, *, normas: list[str] | None = None) -> list[dict[str, Any]]:
        """Búsqueda léxica (FTS5/BM25) sobre la versión vigente de los bloques cacheados. Con `normas`, solo en
        esas leyes (las descubiertas para la consulta): la lista cerrada de la que el LLM elegirá artículos."""
        filtro, params = "", [fts_query(query)]
        if normas is not None:
            if not normas:
                return []
            filtro = f" AND b.id_norma IN ({', '.join('?' * len(normas))})"
            params += normas
        rows = self._con.execute(
            f"""SELECT b.id_norma, b.id_bloque, b.titulo, snippet(boe_bloques_fts, 0, '[', ']', '…', 12)
               FROM boe_bloques_fts JOIN boe_bloques b ON b.id = boe_bloques_fts.rowid
               WHERE boe_bloques_fts MATCH ? AND b.version_vigencia_hasta IS NULL{filtro}
               ORDER BY bm25(boe_bloques_fts) LIMIT ?""",
            (*params, limit),
        ).fetchall()
        return [{"id_norma": r[0], "id_bloque": r[1], "titulo": r[2], "snippet": r[3]} for r in rows]

    def precepto_a_fecha(self, id_norma: str, id_bloque: str, fecha: date) -> PreceptoEncontrado | None:
        """La versión de un precepto guardado vigente en `fecha` (None si no estaba en vigor o no está guardado)."""
        f = fecha.isoformat()
        r = self._con.execute(
            """SELECT b.titulo, b.version_vigencia_desde, b.version_vigencia_hasta, substr(b.texto_consolidado, 1, 420),
                      COALESCE(cb.ubicacion, '')
               FROM boe_bloques b
               LEFT JOIN boe_corpus_bloques cb ON cb.id_norma = b.id_norma AND cb.id_bloque = b.id_bloque
               WHERE b.id_norma = ? AND b.id_bloque = ? AND b.version_vigencia_desde <= ?
                 AND (b.version_vigencia_hasta IS NULL OR b.version_vigencia_hasta > ?)""",
            (id_norma, id_bloque, f, f),
        ).fetchone()
        if r is None:
            return None
        return PreceptoEncontrado(
            id_norma=id_norma,
            id_bloque=id_bloque,
            titulo=r[0] or "",
            vigencia_desde=date.fromisoformat(r[1]),
            vigencia_hasta=date.fromisoformat(r[2]) if r[2] else None,
            inicio=r[3] or "",
            ubicacion=r[4] or "",
            score=0.0,
        )

    def buscar_a_fecha(
        self, consulta: str, fecha: date, *, normas: Sequence[str] | None = None, limit: int = 20
    ) -> list[PreceptoEncontrado]:
        """BM25 sobre la versión de cada precepto VIGENTE EN `fecha` (desde <= fecha < hasta): un precepto reformado
        después de los hechos devuelve su redacción anterior y uno introducido después no aparece. El título del
        bloque pesa tres veces más que el texto."""
        f = fecha.isoformat()
        sql = """SELECT b.id_norma, b.id_bloque, b.titulo, b.version_vigencia_desde, b.version_vigencia_hasta,
                        substr(b.texto_consolidado, 1, 420), COALESCE(cb.ubicacion, ''),
                        bm25(boe_bloques_fts, 1.0, 3.0) AS score
                 FROM boe_bloques_fts JOIN boe_bloques b ON b.id = boe_bloques_fts.rowid
                 LEFT JOIN boe_corpus_bloques cb ON cb.id_norma = b.id_norma AND cb.id_bloque = b.id_bloque
                 WHERE boe_bloques_fts MATCH ? AND b.version_vigencia_desde <= ?
                   AND (b.version_vigencia_hasta IS NULL OR b.version_vigencia_hasta > ?)"""
        params: list[object] = [consulta_fts_legal(consulta), f, f]
        if normas:
            sql += f" AND b.id_norma IN ({', '.join('?' * len(normas))})"
            params.extend(normas)
        sql += " ORDER BY score LIMIT ?"
        params.append(limit)
        return [
            PreceptoEncontrado(
                id_norma=r[0],
                id_bloque=r[1],
                titulo=r[2] or "",
                vigencia_desde=date.fromisoformat(r[3]),
                vigencia_hasta=date.fromisoformat(r[4]) if r[4] else None,
                inicio=r[5] or "",
                ubicacion=r[6] or "",
                score=float(r[7]),
            )
            for r in self._con.execute(sql, params).fetchall()
        ]


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
_UNIDADES = ["uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve"]
_DECENAS = {
    30: "treinta",
    40: "cuarenta",
    50: "cincuenta",
    60: "sesenta",
    70: "setenta",
    80: "ochenta",
    90: "noventa",
}


def _construir_num_palabra() -> dict[str, str]:
    mapa = {w: str(i) for i, w in enumerate(_ORDINALES, start=1)}
    for u_idx, u_txt in enumerate(_UNIDADES, start=1):
        mapa[u_txt] = str(u_idx)
    mapa["un"] = "1"
    mapa["veintiun"] = "21"
    for dec_val, dec_txt in _DECENAS.items():
        mapa[dec_txt] = str(dec_val)
        for u_idx, u_txt in enumerate(_UNIDADES, start=1):
            n = str(dec_val + u_idx)
            mapa[f"{dec_txt} y {u_txt}"] = n
            mapa[f"{dec_txt}y{u_txt}"] = n
            if u_idx == 1:
                mapa[f"{dec_txt} y un"] = n
    mapa["cien"] = "100"
    for k, v in list(mapa.items()):
        if int(v) < 100:
            mapa[f"ciento {k}"] = str(100 + int(v))
    return mapa


_NUM_PALABRA = _construir_num_palabra()


def _titulo_es_articulo(titulo: str, numero: str) -> bool | None:
    """True/False si el título ("Artículo 26", "Artículo 36 bis", "Artículo noveno" en la LPH, "Artículo treinta y ocho"
    en la LCS, "Artículo 121-21" en el CCCat) corresponde al número; None si el bloque no es un artículo."""
    t = fold(titulo or "").lower()
    m = re.match(r"^\s*art[íi]culo\s+(\d+(?:-\d+)?)\s*(bis|ter|quater)?\b", t)
    if m:
        return (m.group(1) + (m.group(2) or "")) == numero
    m = re.match(r"^\s*art[íi]culo\s+(.*)", t)
    if not m:
        return None
    # Numeral en palabras: el prefijo más largo que sea un número («ciento cuatro», «treinta y ocho»); lo que sigue
    # puede ser «bis/ter/quater» o el epígrafe del artículo («Artículo diez. Objeto», «Artículo primero Ámbito»).
    palabras = re.findall(r"[a-z]+", m.group(1))
    for n in range(min(4, len(palabras)), 0, -1):
        valor = _NUM_PALABRA.get(" ".join(palabras[:n]))
        if valor is not None:
            sufijo = palabras[n] if len(palabras) > n and palabras[n] in ("bis", "ter", "quater") else ""
            return (valor + sufijo) == numero
    return None


def fts_query(text: str) -> str:
    """Convierte texto libre en una consulta FTS5 segura (términos OR entre comillas)."""
    terms = [t for t in "".join(c if c.isalnum() else " " for c in text).split() if len(t) > 2]
    return " OR ".join(f'"{t}"' for t in terms[:16]) or '""'
