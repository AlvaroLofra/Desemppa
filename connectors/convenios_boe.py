"""Descarga verificada de convenios colectivos publicados en el BOE.

Ninguna referencia del seed se da por buena: antes de indexar, el documento del BOE debe ser una resolución que
«registra y publica» un convenio o acuerdo y su texto debe contener el código de convenio esperado. Así un
`boletin_ref` equivocado (o inventado) se rechaza en vez de acabar citado como fuente verificada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

import httpx
from lxml import etree

BOE_XML_URL = "https://www.boe.es/diario_boe/xml.php?id={ref}"
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True)
_CODIGO_RE = re.compile(r"C[óo]digo\s+de\s+convenio[^0-9]{0,20}(\d{14})", re.I)


@dataclass
class DocumentoBOE:
    ref: str
    titulo: str
    fecha_publicacion: date | None
    codigos_convenio: list[str]
    texto: str
    modificaciones_posteriores: list[str] = field(default_factory=list)


def parse_documento(ref: str, xml_bytes: bytes) -> DocumentoBOE:
    root = etree.fromstring(xml_bytes, parser=_PARSER)
    titulo = (root.findtext("metadatos/titulo") or "").strip()
    fecha_raw = (root.findtext("metadatos/fecha_publicacion") or "").strip()
    fecha = datetime.strptime(fecha_raw, "%Y%m%d").date() if re.fullmatch(r"\d{8}", fecha_raw) else None
    texto_el = root.find("texto")  # hijo directo: <analisis> también contiene elementos <texto>
    partes: list[str] = []
    if texto_el is not None:
        for p in texto_el.iter("p"):
            t = re.sub(r"\s+", " ", "".join(p.itertext())).strip()
            if t:
                partes.append(t)
    texto = "\n".join(partes)
    modificaciones = [
        str(post.get("referencia"))
        for post in root.iterfind("analisis/referencias/posteriores/posterior")
        if post.get("referencia") and "MODIFICA" in (post.findtext("palabra") or "").upper()
    ]
    return DocumentoBOE(
        ref=ref,
        titulo=titulo,
        fecha_publicacion=fecha,
        codigos_convenio=sorted(set(_CODIGO_RE.findall(texto))),
        texto=texto,
        modificaciones_posteriores=modificaciones,
    )


def verificar_documento(doc: DocumentoBOE, codigo_esperado: str) -> list[str]:
    """Motivos por los que el documento NO es el convenio esperado (lista vacía = verificado)."""
    errores: list[str] = []
    titulo = doc.titulo.lower()
    if "registra y publica" not in titulo or not ("convenio" in titulo or "acuerdo" in titulo):
        errores.append(f"el título no es el de un convenio registrado: «{doc.titulo[:140]}»")
    if any(x in titulo for x in ("revisión salarial", "tablas salariales", "sentencia", "acta")):
        errores.append("el documento es una revisión, acta o sentencia, no el texto del convenio")
    if codigo_esperado not in doc.codigos_convenio:
        encontrados = ", ".join(doc.codigos_convenio) or "ninguno"
        errores.append(f"el texto no contiene el código de convenio {codigo_esperado} (encontrados: {encontrados})")
    if doc.fecha_publicacion is None:
        errores.append("el documento no tiene fecha de publicación")
    return errores


def descargar_documento(ref: str, client: httpx.Client) -> DocumentoBOE:
    resp = client.get(BOE_XML_URL.format(ref=ref))
    resp.raise_for_status()
    return parse_documento(ref, resp.content)
