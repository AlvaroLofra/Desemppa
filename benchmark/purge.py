"""Protocolo anti-fuga (dossier v2.1 §9): de una sentencia real solo queda la narración fáctica, sin el
resultado de instancias previas ni identificadores que permitan al modelo "recordar" el caso."""

from __future__ import annotations

import re

from connectors.cendoj_parser import parse_sentencia, purge_antecedentes

_IDS = re.compile(r"(Roj:[^\n]*|ECLI:\S*|Id Cendoj:[^\n]*|N[ºo°]\s*de\s*Recurso:[^\n]*|Ponente:[^\n]*)", re.I)
_ORGANOS = re.compile(r"(Juzgado|Audiencia|Tribunal)\s+[^,.\n]{0,80}", re.I)


def hechos_purgados(texto_sentencia: str) -> str:
    """Antecedentes sin historia procesal, sin identificadores ni nombres de órganos."""
    s = parse_sentencia(texto_sentencia)
    hechos = s.antecedentes_purgados or purge_antecedentes(s.antecedentes)
    hechos = _IDS.sub("", hechos)
    hechos = _ORGANOS.sub("el órgano judicial", hechos)
    return re.sub(r"\n{3,}", "\n\n", hechos).strip()
