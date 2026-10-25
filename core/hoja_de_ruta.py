"""Hoja de ruta determinista: los pasos a seguir según la submateria (config/hojas_de_ruta.yaml).

No interviene ningún LLM. Cada paso lleva su base legal con cita literal (verificada contra el BOE por
scripts/verificar_hojas_de_ruta.py), el plazo calculado por CalendarEngine si lo hay y quién puede darlo
según las reglas de postulación.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

from config.settings import CONFIG_DIR

RUTA = CONFIG_DIR / "hojas_de_ruta.yaml"


class BasePaso(BaseModel):
    norma: str
    articulo: str
    cita: str


class PasoHojaRuta(BaseModel):
    titulo: str
    que_hacer: str
    quien: Literal["tu", "abogado", "segun_cuantia"]
    base: list[BasePaso]
    plazo: str | None = None
    escrito: str | None = None
    vigente_desde: date | None = None  # el paso solo aplica a hechos de esa fecha o posteriores


class PasoResuelto(PasoHojaRuta):
    """Paso listo para mostrar: `quien` ya resuelto y, si procede, la fecha límite calculada por el motor."""

    quien_texto: str
    fecha_limite: str | None = None
    base_legal_plazo: str | None = None


@lru_cache(maxsize=1)
def cargar(ruta: Path = RUTA) -> dict[str, list[PasoHojaRuta]]:
    datos: dict[str, Any] = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    comunes = {k: PasoHojaRuta.model_validate(v) for k, v in datos.get("pasos_comunes", {}).items()}
    hojas: dict[str, list[PasoHojaRuta]] = {}
    for sub, pasos in datos.get("hojas", {}).items():
        lista = []
        for p in pasos:
            if "comun" in p:
                if p["comun"] not in comunes:
                    raise ValueError(f"{sub}: paso común desconocido «{p['comun']}»")
                lista.append(comunes[p["comun"]])
            else:
                lista.append(PasoHojaRuta.model_validate(p))
        hojas[sub] = lista
    return hojas


_QUIEN = {
    "tu": "Lo puedes hacer tú",
    "abogado": "Necesitas abogado",
}


def aplicables(submateria: str | None, fecha_hechos: date | None = None) -> list[PasoHojaRuta]:
    """Pasos de la submateria aplicables a la fecha de los hechos. Un paso con `vigente_desde` solo se muestra si
    consta que los hechos son de esa fecha o posteriores: una norma nueva nunca se presume aplicable al pasado."""
    pasos = cargar().get(submateria or "", [])
    return [
        p for p in pasos if p.vigente_desde is None or (fecha_hechos is not None and fecha_hechos >= p.vigente_desde)
    ]


def hoja_de_ruta(
    submateria: str | None,
    *,
    fecha_hechos: date | None = None,
    plazos: list[dict[str, Any]] | None = None,
    requiere_abogado: bool | None = None,
) -> list[PasoResuelto]:
    """Pasos de la submateria. `plazos`: los del dictamen (motor determinista), por `tipo_plazo_id`."""
    if not submateria:
        return []
    por_tipo = {p["tipo_plazo_id"]: p for p in plazos or []}
    out = []
    for paso in aplicables(submateria, fecha_hechos):
        if paso.quien == "segun_cuantia":
            quien_texto = (
                "Según la cuantía: mira «Abogado y procurador»"
                if requiere_abogado is None
                else _QUIEN["abogado" if requiere_abogado else "tu"]
            )
        else:
            quien_texto = _QUIEN[paso.quien]
        plazo = por_tipo.get(paso.plazo or "")
        out.append(
            PasoResuelto(
                **paso.model_dump(),
                quien_texto=quien_texto,
                fecha_limite=plazo["fecha_limite_segura"] if plazo else None,
                base_legal_plazo=plazo["base_legal"] if plazo else None,
            )
        )
    return out
