"""Catálogos jurídicos estáticos: submaterias (§4.1) y normas BOE núcleo."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

CONFIG = Path(__file__).resolve().parents[1] / "config"


class NormaRef(BaseModel):
    norma: str
    articulos: list[str]


class NormaUE(BaseModel):
    celex: str  # p. ej. 32004R0261
    titulo: str
    articulos: list[str]


class NormasForales(BaseModel):
    """Ajuste de normas cuando se aplica un Derecho civil territorial (p. ej. Cataluña)."""

    anade: list[NormaRef] = Field(default_factory=list)
    quita: list[str] = Field(default_factory=list)  # alias de normas estatales que no se aplican en ese territorio


class Submateria(BaseModel):
    clave: str
    descripcion: str
    jurisdiccion: str
    procedimiento: str | None = None
    normas: list[NormaRef] = Field(default_factory=list)
    normas_forales: dict[str, NormasForales] = Field(default_factory=dict)  # clave: territorio (CT, ...)
    normas_ue: list[NormaUE] = Field(default_factory=list)
    campos_criticos: list[str] = Field(default_factory=list)
    # Respuestas cerradas de los campos críticos que no son de sí/no («¿A o B?»): campo → opciones.
    opciones_campos: dict[str, list[str]] = Field(default_factory=dict)
    plazos: list[str] = Field(default_factory=list)
    terminos_cendoj: list[str] = Field(default_factory=list)
    doctrina_cambiante: bool = False
    competencia_local: bool = False
    foral_relevante: bool = False
    fuera_alcance: bool = False
    ambigua: bool = False
    cji: bool = False
    notas: str = ""


def normas_aplicables(sub: Submateria, territorio_foral: str | None) -> list[NormaRef]:
    """Normas de la submateria; con Derecho foral, se quitan las estatales desplazadas y se añaden las propias."""
    ajuste = sub.normas_forales.get(territorio_foral or "")
    if ajuste is None:
        return list(sub.normas)
    return [n for n in sub.normas if n.norma not in ajuste.quita] + list(ajuste.anade)


@lru_cache
def submaterias() -> dict[str, Submateria]:
    raw = yaml.safe_load((CONFIG / "catalogo_materias.yaml").read_text(encoding="utf-8"))["submaterias"]
    return {k: Submateria(clave=k, **v) for k, v in raw.items()}


@lru_cache
def normas() -> dict[str, dict[str, Any]]:
    return dict(json.loads((CONFIG / "catalogo_normas.json").read_text(encoding="utf-8"))["normas"])


def id_norma(alias: str) -> str:
    return str(normas()[alias]["id"])


def catalogo_para_prompt() -> str:
    return "\n".join(
        f"- {s.clave} [{s.jurisdiccion}]: {s.descripcion}"
        + (f" · campos críticos: {'; '.join(s.campos_criticos)}" if s.campos_criticos else "")
        for s in submaterias().values()
        if not s.fuera_alcance
    )


def catalogo_normas_para_prompt() -> str:
    return "\n".join(f"- {alias}: {meta['titulo']}" for alias, meta in normas().items())
