"""Reglas deterministas de postulación (dossier §1.3.2, guardarraíl G9)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

from core.schemas import AdvertenciaPostulacion

RULES_PATH = Path(__file__).resolve().parents[1] / "config" / "postulacion.yaml"


class CasoPostulacion(BaseModel):
    jurisdiccion: str
    procedimiento: str | None = None
    fase: Literal["inicial", "instancia", "recurso"] | None = None
    cuantia_eur: float | None = None
    funcionario_personal: bool = False


@lru_cache
def _load(path: Path = RULES_PATH) -> dict[str, Any]:
    return dict(yaml.safe_load(path.read_text(encoding="utf-8")))


def _matches(cond: dict[str, Any], caso: CasoPostulacion) -> bool:
    for key, expected in cond.items():
        if key == "cuantia_max":
            if caso.cuantia_eur is None or caso.cuantia_eur > float(expected):
                return False
        elif key == "cuantia_min_exclusiva":
            if caso.cuantia_eur is None or caso.cuantia_eur <= float(expected):
                return False
        elif getattr(caso, key) != expected:
            return False
    return True


def evaluar(caso: CasoPostulacion) -> AdvertenciaPostulacion:
    for regla in _load()["reglas"]:
        if _matches(regla["si"], caso):
            return AdvertenciaPostulacion(
                requiere_abogado=bool(regla["abogado"]),
                requiere_procurador=bool(regla["procurador"]),
                bloquea_escritos=bool(regla["bloquea_escritos"]),
                base_legal=regla["base_legal"],
                texto_usuario=regla["texto"],
            )
    raise AssertionError("postulacion.yaml debe terminar con una regla por defecto")
