"""Derecho de la UE desde el repositorio oficial de la Oficina de Publicaciones (Cellar, mismo texto que EUR-Lex).

La web de EUR-Lex responde 202 sin contenido a los clientes automáticos (protección antibots), pero Cellar sirve el
documento por negociación de contenido: `http://publications.europa.eu/resource/celex/{CELEX}` con
`Accept: text/html` y `Accept-Language: spa`. Es el texto del Diario Oficial (no una versión consolidada).
Comprobado el 24-10-2026 con el Reglamento (CE) 261/2004.
"""

from __future__ import annotations

import html
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

CELLAR_URL = "http://publications.europa.eu/resource/celex/{celex}"
EURLEX_URL = "https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:{celex}"
_ART_RE = re.compile(r"^Art[íi]culo\s+(\d+)\s*(bis)?$", re.I)


class EURLexError(Exception):
    pass


@dataclass
class ArticuloUE:
    celex: str
    articulo: str
    titulo: str
    texto: str
    url: str


def texto_plano(documento_html: str) -> str:
    """HTML del Diario Oficial → líneas de texto (un párrafo por línea)."""
    sin_scripts = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", documento_html, flags=re.S | re.I)
    plano = html.unescape(re.sub(r"<[^>]+>", "\n", sin_scripts)).replace("\xa0", " ")
    lineas = [re.sub(r"[ \t]+", " ", ln).strip() for ln in plano.splitlines()]
    return "\n".join(ln for ln in lineas if ln)


def parse_articulos(documento_html: str) -> dict[str, tuple[str, str]]:
    """{número: (título, texto completo del artículo con su encabezado)}."""
    lineas = texto_plano(documento_html).splitlines()
    marcas = [(i, m) for i, ln in enumerate(lineas) if (m := _ART_RE.match(ln))]
    out: dict[str, tuple[str, str]] = {}
    for k, (i, m) in enumerate(marcas):
        fin = marcas[k + 1][0] if k + 1 < len(marcas) else len(lineas)
        cuerpo = lineas[i:fin]
        # Tras el último artículo vienen la fórmula final y los anexos: se corta en «Hecho en …».
        corte = next((j for j, ln in enumerate(cuerpo) if ln.startswith("Hecho en ")), len(cuerpo))
        cuerpo = cuerpo[:corte]
        numero = m.group(1) + (m.group(2) or "").lower()
        titulo = cuerpo[1] if len(cuerpo) > 1 else ""
        out.setdefault(numero, (titulo, "\n".join(cuerpo)))
    return out


class EURLexRepository:
    def __init__(self, con: sqlite3.Connection, *, client: httpx.AsyncClient | None = None, ttl_days: int = 30) -> None:
        self._con = con
        self._client = client
        self._ttl = timedelta(days=ttl_days)

    async def _descargar(self, celex: str) -> str:
        client = self._client or httpx.AsyncClient(timeout=60, follow_redirects=True)
        try:
            r = await client.get(
                CELLAR_URL.format(celex=celex), headers={"Accept": "text/html", "Accept-Language": "spa"}
            )
        except httpx.HTTPError as exc:
            raise EURLexError(f"no se pudo descargar {celex}: {exc}") from exc
        finally:
            if self._client is None:
                await client.aclose()
        if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
            raise EURLexError(f"EUR-Lex/Cellar respondió {r.status_code} para {celex}")
        return r.text

    async def documento(self, celex: str) -> str:
        row = self._con.execute("SELECT html, descargado_en FROM eurlex_cache WHERE celex = ?", (celex,)).fetchone()
        if row and datetime.now(UTC) - datetime.fromisoformat(row[1]) < self._ttl:
            return str(row[0])
        try:
            doc = await self._descargar(celex)
        except EURLexError:
            if row:  # mejor el texto en caché que nada
                return str(row[0])
            raise
        self._con.execute(
            "INSERT OR REPLACE INTO eurlex_cache(celex, html, descargado_en) VALUES (?, ?, ?)",
            (celex, doc, datetime.now(UTC).isoformat()),
        )
        return doc

    async def get_articulo(self, celex: str, articulo: str) -> ArticuloUE:
        arts = parse_articulos(await self.documento(celex))
        if articulo not in arts:
            raise EURLexError(f"el artículo {articulo} no aparece en {celex}")
        titulo, texto = arts[articulo]
        return ArticuloUE(celex, articulo, titulo, texto, EURLEX_URL.format(celex=celex))
