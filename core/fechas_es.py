"""Fechas que el ciudadano ha escrito de verdad (determinista, sin LLM).

Sirve para comprobar que una fecha que devuelve el triaje consta en el texto o en las aclaraciones y no la ha
deducido o calculado el modelo (p. ej., «han pasado 2 años y 4 meses» ⇒ el modelo NO puede fijar la fecha).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from core.normalize import fold

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}  # fmt: skip
_MES = "|".join(MESES)
_DIA_MES_ANIO = re.compile(rf"\b(\d{{1,2}})\s+de\s+({_MES})(?:\s+(?:de|del)\s+(\d{{4}}))?\b")
_NUMERICA = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})\b")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MES_ANIO = re.compile(rf"\b({_MES})\s+(?:de|del)\s+(\d{{4}})\b")
_HACE = re.compile(r"\bhace\s+(\d{1,3})\s+(dias|semanas)\b")
_RELATIVAS = {"hoy": 0, "ayer": 1, "anteayer": 2, "antes de ayer": 2}


@dataclass
class FechasTexto:
    exactas: set[date] = field(default_factory=set)
    meses: set[tuple[int, int]] = field(default_factory=set)  # (año, mes) dichos sin día


def _fecha(anio: int, mes: int, dia: int) -> date | None:
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def fechas_en_texto(texto: str, hoy: date) -> FechasTexto:
    t = fold(texto)
    out = FechasTexto()
    for d, m, a in _DIA_MES_ANIO.findall(t):
        f = _fecha(int(a) if a else hoy.year, MESES[m], int(d))
        if f:
            out.exactas.add(f)
    for d, m, a in _NUMERICA.findall(t):
        anio = int(a) + 2000 if len(a) == 2 else int(a)
        f = _fecha(anio, int(m), int(d))
        if f:
            out.exactas.add(f)
    for a, m, d in _ISO.findall(t):
        f = _fecha(int(a), int(m), int(d))
        if f:
            out.exactas.add(f)
    for m, a in _MES_ANIO.findall(t):
        out.meses.add((int(a), MESES[m]))
    for n, unidad in _HACE.findall(t):
        out.exactas.add(hoy - timedelta(days=int(n) * (7 if unidad == "semanas" else 1)))
    for palabra, dias in _RELATIVAS.items():
        if re.search(rf"\b{palabra}\b", t):
            out.exactas.add(hoy - timedelta(days=dias))
    return out


_VACIAS_EVENTO = {"fecha", "exacta", "del", "de", "la", "el", "los", "las", "o", "y", "en", "que", "su", "tu"}


def fecha_del_evento(texto: str, evento: str, hoy: date) -> date | None:
    """La fecha que el usuario escribe en la MISMA frase que el evento del plazo («El 10 de marzo compré…» para
    «fecha de compra o entrega»). Solo si hay exactamente una candidata; nunca se calcula ni se deduce otra cosa."""
    raices = {w[:5] for w in re.findall(r"[a-z]+", fold(evento)) if len(w) > 3 and w not in _VACIAS_EVENTO}
    if not raices:
        return None
    candidatas: set[date] = set()
    for frase in re.split(r"[.;:!?\n]+", texto):
        palabras = {w[:5] for w in re.findall(r"[a-z]+", fold(frase))}
        if raices & palabras:
            exactas = fechas_en_texto(frase, hoy).exactas
            if len(exactas) == 1:
                candidatas |= exactas
    return next(iter(candidatas)) if len(candidatas) == 1 else None


def fecha_consta(f: date, texto: str, hoy: date) -> bool:
    """¿La fecha exacta aparece (o se deduce sin cálculo de calendario: «hoy», «ayer», «hace N días»)?"""
    return f in fechas_en_texto(texto, hoy).exactas


def mes_consta(f: date, texto: str, hoy: date) -> bool:
    """¿Consta al menos el mes y el año (suficiente para saber qué ley estaba vigente)?"""
    fechas = fechas_en_texto(texto, hoy)
    return (
        f in fechas.exactas
        or (f.year, f.month) in fechas.meses
        or any((e.year, e.month) == (f.year, f.month) for e in fechas.exactas)
    )
