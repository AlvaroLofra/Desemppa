"""Normalización tipográfica de texto jurídico, con mapa de offsets al texto original.

Se usa en el guardarraíl de cita literal (G3): la comparación se hace sobre texto normalizado,
pero el resaltado en el visor necesita offsets del texto original.
"""

from __future__ import annotations

import re
import unicodedata

LIGATURES = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "st",
    "ﬆ": "st",
}
_CHAR_MAP = {
    "«": '"',
    "»": '"',
    "“": '"',
    "”": '"',
    "„": '"',
    "‟": '"',
    "″": '"',
    "‘": "'",
    "’": "'",
    "‚": "'",
    "‛": "'",
    "′": "'",
    "´": "'",
    "`": "'",
    "–": "-",
    "—": "-",
    "‒": "-",
    "―": "-",
    "‐": "-",
    "‑": "-",
    "−": "-",
    " ": " ",
    " ": " ",
    " ": " ",
    " ": " ",
    "\t": " ",
    "\r": " ",
    "\n": " ",
    "…": "...",
}
_DROP = {"­", "​", "‌", "‍", "﻿"}  # guion blando y caracteres invisibles
_HYPHEN_BREAK = re.compile(r"(\w)-\s*\n\s*(\w)")


def fix_ligatures(text: str) -> str:
    for lig, rep in LIGATURES.items():
        text = text.replace(lig, rep)
    return text


def dehyphenate(text: str) -> str:
    """Une palabras partidas a final de línea ("contra-\\nto" -> "contrato")."""
    return _HYPHEN_BREAK.sub(r"\1\2", text)


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Devuelve (texto normalizado, offsets) donde offsets[i] es el índice en `text` del carácter i."""
    out: list[str] = []
    offsets: list[int] = []
    prev_space = True
    for idx, ch in enumerate(text):
        if ch in _DROP:
            continue
        rep = LIGATURES.get(ch) or _CHAR_MAP.get(ch)
        if rep is None:
            rep = unicodedata.normalize("NFKC", ch)
        for r in rep.lower():
            if r.isspace():
                if prev_space:
                    continue
                r, prev_space = " ", True
            else:
                prev_space = False
            out.append(r)
            offsets.append(idx)
    while out and out[-1] == " ":
        out.pop()
        offsets.pop()
    return "".join(out), offsets


def normalize(text: str) -> str:
    return normalize_with_map(text)[0]


def fold(text: str) -> str:
    """Minúsculas y sin tildes, para búsquedas por nombre ("Alcalá" == "alcala")."""
    decomposed = unicodedata.normalize("NFD", normalize(text))
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
