"""Modelos y parser de la API de Datos Abiertos del BOE (legislación consolidada).

El texto de los bloques se sirve en XML con un <version> por cada redacción histórica:
  <bloque id="a36" tipo="precepto" titulo="Artículo 36">
    <version id_norma="BOE-A-1994-26003" fecha_publicacion="19941125" fecha_vigencia="19950101"><p>..</p></version>
"""

from __future__ import annotations

from datetime import date
from typing import Any

from lxml import etree
from pydantic import BaseModel, Field, field_validator


def parse_boe_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()[:8]
    if len(value) != 8 or not value.isdigit():
        return None
    return date(int(value[:4]), int(value[4:6]), int(value[6:8]))


def as_list(value: Any) -> list[Any]:
    """La API devuelve un objeto suelto cuando hay un único elemento y una lista cuando hay varios."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


class NormaMeta(BaseModel):
    id_norma: str
    titulo: str
    rango: str | None = None
    ambito: str = "estatal"
    derogada: bool = False
    fecha_actualizacion: str | None = None
    url_html: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict, repr=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> NormaMeta:
        ambito = (data.get("ambito") or {}).get("texto", "Estatal")
        return cls(
            id_norma=data["identificador"],
            titulo=data.get("titulo", ""),
            rango=(data.get("rango") or {}).get("texto"),
            ambito="estatal" if ambito.lower() == "estatal" else f"autonomico:{ambito}",
            derogada=data.get("estatus_derogacion") == "S",
            fecha_actualizacion=data.get("fecha_actualizacion"),
            url_html=data.get("url_html_consolidada"),
            raw=data,
        )


class IndiceEntry(BaseModel):
    id_bloque: str
    titulo: str = ""
    fecha_actualizacion: date | None = None

    @field_validator("titulo", mode="before")
    @classmethod
    def _none_to_empty(cls, v: Any) -> str:
        return v or ""


class BloqueVersion(BaseModel):
    id_norma_modificadora: str
    fecha_publicacion: date | None
    vigencia_desde: date
    vigencia_hasta: date | None = None  # exclusiva: inicio de la versión siguiente
    texto: str


class Bloque(BaseModel):
    id_norma: str
    id_bloque: str
    tipo: str | None = None
    titulo: str = ""
    versiones: list[BloqueVersion]

    def version_at(self, fecha: date | None) -> BloqueVersion | None:
        if fecha is None:
            return self.versiones[-1] if self.versiones else None
        candidates = [v for v in self.versiones if v.vigencia_desde <= fecha]
        return candidates[-1] if candidates else None


def _paragraph_text(p: etree._Element) -> str:
    return " ".join("".join(p.itertext()).split())


def parse_bloque_xml(id_norma: str, xml: bytes) -> Bloque:
    root = etree.fromstring(xml)
    code = root.findtext("status/code")
    if code and code != "200":
        raise ValueError(f"BOE respondió {code}: {root.findtext('status/text')}")
    node = root.find("data/bloque")
    if node is None:
        raise ValueError("respuesta del BOE sin <bloque>")
    versiones: list[BloqueVersion] = []
    for v in node.findall("version"):
        start = parse_boe_date(v.get("fecha_vigencia")) or parse_boe_date(v.get("fecha_publicacion"))
        if start is None:
            continue
        parts = [
            _paragraph_text(el)
            for el in v.iter()
            if el.tag == "p" or (el.tag in ("td", "th") and el.find(".//p") is None)
        ]
        versiones.append(
            BloqueVersion(
                id_norma_modificadora=v.get("id_norma") or id_norma,
                fecha_publicacion=parse_boe_date(v.get("fecha_publicacion")),
                vigencia_desde=start,
                texto="\n".join(p for p in parts if p),
            )
        )
    # Varias redacciones con la misma fecha de vigencia (correcciones del mismo día): prevalece la última
    # publicada, que es la que figura después en el XML.
    por_fecha: dict[date, BloqueVersion] = {}
    for v in versiones:
        por_fecha[v.vigencia_desde] = v
    versiones = sorted(por_fecha.values(), key=lambda x: x.vigencia_desde)
    for current, nxt in zip(versiones, versiones[1:], strict=False):
        current.vigencia_hasta = nxt.vigencia_desde
    return Bloque(
        id_norma=id_norma,
        id_bloque=node.get("id") or "",
        tipo=node.get("tipo"),
        titulo=node.get("titulo") or "",
        versiones=versiones,
    )


def parse_indice_json(payload: dict[str, Any]) -> list[IndiceEntry]:
    entries: list[IndiceEntry] = []
    for item in as_list(payload.get("data")):
        for b in as_list(item.get("bloque") if isinstance(item, dict) else None):
            entries.append(
                IndiceEntry(
                    id_bloque=b["id"],
                    titulo=b.get("titulo") or "",
                    fecha_actualizacion=parse_boe_date(b.get("fecha_actualizacion")),
                )
            )
    return entries


def articulo_to_bloque(articulo: str) -> str:
    """'36' -> 'a36'; 'Art. 1902' -> 'a1902'; '36 bis' -> 'a36bis'; ids ya válidos se respetan."""
    raw = articulo.strip().lower()
    for prefix in ("artículo", "articulo", "art.", "art"):
        if raw.startswith(prefix):
            raw = raw[len(prefix) :]
            break
    raw = raw.replace(" ", "").replace(".", "")
    if raw and raw[0].isdigit():
        return f"a{raw}"
    return raw
