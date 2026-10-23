"""Casos sintéticos con permutaciones controladas (dossier v2.1 §9.2): cambian fechas, cuantías y nombres
preservando la ratio decidendi, para detectar respuestas memorizadas."""

from __future__ import annotations

import random
import re

_NOMBRES = ["Lucía Romero", "Andrés Molina", "Carmen Vidal", "Javier Ortega", "Elena Navarro", "Pablo Rubio"]
_EMPRESAS = ["Servicios Alfa S.L.", "Comercial Beta S.A.", "Gestiones Gamma S.L.", "Hostelería Delta S.L."]
_FECHA = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_ANIO = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
_IMPORTE = re.compile(r"\b(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?)\s*(€|euros)", re.I)
_EMPRESA = re.compile(r"\b[A-ZÁÉÍÓÚÑ][\wáéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñ]+)*\s+S\.(?:L|A)\.(?:U\.)?")


def _fmt(amount: float) -> str:
    entero, dec = f"{amount:.2f}".split(".")
    miles = f"{int(entero):,}".replace(",", ".")
    return miles if dec == "00" else f"{miles},{dec}"


def permutar(texto: str, *, seed: int = 0, desplazamiento_anios: int | None = None) -> str:
    rnd = random.Random(seed)
    shift = desplazamiento_anios if desplazamiento_anios is not None else rnd.choice([-3, -2, 2, 3])
    factor = rnd.choice([0.8, 0.9, 1.1, 1.25])
    texto = _FECHA.sub(lambda m: f"{m.group(1)}/{m.group(2)}/{int(m.group(3)) + shift}", texto)
    texto = _ANIO.sub(lambda m: str(int(m.group(1)) + shift), texto)

    def _imp(m: re.Match[str]) -> str:
        valor = float(m.group(1).replace(".", "").replace(",", "."))
        return f"{_fmt(round(valor * factor, 2))} {m.group(2)}"

    texto = _IMPORTE.sub(_imp, texto)
    vistos: dict[str, str] = {}
    empresas = iter(rnd.sample(_EMPRESAS, len(_EMPRESAS)))
    texto = _EMPRESA.sub(lambda m: vistos.setdefault(m.group(0), next(empresas, "Empresa Omega S.L.")), texto)
    nombres = iter(rnd.sample(_NOMBRES, len(_NOMBRES)))
    return re.sub(r"\[\[PERSONA_\d+\]\]", lambda m: vistos.setdefault(m.group(0), next(nombres, "Persona X")), texto)
