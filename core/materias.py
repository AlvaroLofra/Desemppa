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


class Submateria(BaseModel):
    clave: str
    descripcion: str
    jurisdiccion: str
    procedimiento: str | None = None
    normas: list[NormaRef] = Field(default_factory=list)
    campos_criticos: list[str] = Field(default_factory=list)
    plazos: list[str] = Field(default_factory=list)
    terminos_cendoj: list[str] = Field(default_factory=list)
    doctrina_cambiante: bool = False
    competencia_local: bool = False
    foral_relevante: bool = False
    fuera_alcance: bool = False
    ambigua: bool = False
    cji: bool = False
    notas: str = ""


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
    return "\n".join(f"- {s.clave} [{s.jurisdiccion}]: {s.descripcion}" for s in submaterias().values())
