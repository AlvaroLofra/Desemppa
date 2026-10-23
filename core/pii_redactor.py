"""Seudonimización reversible de datos personales antes de enviar texto a un proveedor externo (§1.1.4).

Detecta DNI/NIE (con letra de control válida), IBAN español, teléfonos, emails, matrículas y
nombres propios introducidos por fórmulas habituales ("me llamo", "D.", "Dña.", "el señor"...).
El mapa token -> valor original nunca sale del equipo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_NAME = r"[A-ZÁÉÍÓÚÑ][a-záéíóúñü]+(?:\s+(?:de\s+(?:la\s+|los\s+)?|del\s+|y\s+)?[A-ZÁÉÍÓÚÑ][a-záéíóúñü]+){0,3}"

# Orden importante: lo más específico primero.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("IBAN", re.compile(r"\bES\d{2}(?:[ -]?\d{4}){5}\b", re.I)),
    ("NIE", re.compile(r"\b[XYZ][- ]?\d{7}[- ]?[A-Z]\b", re.I)),
    ("DNI", re.compile(r"\b\d{8}[- ]?[A-Z]\b", re.I)),
    ("TELEFONO", re.compile(r"(?<![\d€.,])(?:\+34[ -]?)?[6789]\d{2}[ -]?\d{3}[ -]?\d{3}(?![\d€])")),
    ("MATRICULA", re.compile(r"\b\d{4}[ -]?[BCDFGHJKLMNPRSTVWXYZ]{3}\b")),
    (
        "PERSONA",
        re.compile(
            r"(?:\b(?i:me llamo|mi nombre es|don|doña|señor|señora)|\bD\.|\bDª\.|\bDña\.|\bSr\.|\bSra\.)\s+"
            r"(?P<v>" + _NAME + ")"
        ),
    ),
]


def valid_dni(value: str) -> bool:
    raw = re.sub(r"[- ]", "", value.upper())
    return len(raw) == 9 and raw[:8].isdigit() and _DNI_LETTERS[int(raw[:8]) % 23] == raw[8]


def valid_nie(value: str) -> bool:
    raw = re.sub(r"[- ]", "", value.upper())
    if len(raw) != 9 or raw[0] not in "XYZ":
        return False
    return valid_dni(str("XYZ".index(raw[0])) + raw[1:])


_VALIDATORS = {"DNI": valid_dni, "NIE": valid_nie}


@dataclass
class Redaction:
    text: str
    mapping: dict[str, str] = field(default_factory=dict)

    def restore(self, text: str) -> str:
        for token, original in self.mapping.items():
            text = text.replace(token, original)
        return text


def redact(text: str, *, mapping: dict[str, str] | None = None) -> Redaction:
    """Sustituye los datos personales por tokens [[TIPO_n]]. Reutiliza `mapping` para ser coherente
    entre varios textos de una misma consulta (el mismo DNI recibe siempre el mismo token)."""
    mapping = dict(mapping or {})
    reverse = {v: k for k, v in mapping.items()}
    counters: dict[str, int] = {}
    for token in mapping:
        kind = token.strip("[]").rsplit("_", 1)[0]
        counters[kind] = max(counters.get(kind, 0), int(token.strip("[]").rsplit("_", 1)[1]))

    def token_for(kind: str, value: str) -> str:
        if value in reverse:
            return reverse[value]
        counters[kind] = counters.get(kind, 0) + 1
        token = f"[[{kind}_{counters[kind]}]]"
        mapping[token] = value
        reverse[value] = token
        return token

    for kind, pattern in _PATTERNS:
        check = _VALIDATORS.get(kind)

        def _sub(m: re.Match[str], kind: str = kind, check: object = check) -> str:
            # Si el patrón tiene grupo "v", solo se sustituye ese tramo (se conserva "me llamo ", "D. "...).
            group = "v" if "v" in m.re.groupindex else 0
            value = m.group(group)
            if callable(check) and not check(value):
                return m.group(0)
            start, end = m.start(group) - m.start(0), m.end(group) - m.start(0)
            whole = m.group(0)
            return whole[:start] + token_for(kind, value) + whole[end:]

        text = pattern.sub(_sub, text)
    return Redaction(text=text, mapping=mapping)


def contains_pii(text: str) -> bool:
    return bool(redact(text).mapping)
