"""Segmentación de sentencias (texto plano del PDF del CENDOJ) — dossier §3.1 v2.1 y Bloque 3.

Separa encabezado, antecedentes, fundamentos de derecho (mayoría), fallo y votos particulares.
Los votos particulares se aíslan para que nunca entren en el dossier como doctrina, y los
antecedentes se purgan de la historia procesal previa (qué resolvieron instancias anteriores).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

_SECTION_RE = re.compile(
    r"^\s*(?P<h>A\s*N\s*T\s*E\s*C\s*E\s*D\s*E\s*N\s*T\s*E\s*S(?:\s+D\s*E\s+H\s*E\s*C\s*H\s*O)?"
    r"|H\s*E\s*C\s*H\s*O\s*S\s+P\s*R\s*O\s*B\s*A\s*D\s*O\s*S"
    r"|F\s*U\s*N\s*D\s*A\s*M\s*E\s*N\s*T\s*O\s*S\s+D\s*E\s+D\s*E\s*R\s*E\s*C\s*H\s*O"
    r"|F\s*A\s*L\s*L\s*O|P\s*A\s*R\s*T\s*E\s+D\s*I\s*S\s*P\s*O\s*S\s*I\s*T\s*I\s*V\s*A"
    r"|V\s*O\s*T\s*O\s+P\s*A\s*R\s*T\s*I\s*C\s*U\s*L\s*A\s*R)\b[^\n]*$",
    re.M | re.I,
)
_ROJ_RE = re.compile(r"Roj:\s*(?P<roj>(?:STS|SAP|STSJ|SAN|ATS|AAP|SJSO|SJPI|SJCA|SJM)\s+[A-Z]{0,3}\s*\d+/\d{4})", re.I)
_ECLI_RE = re.compile(r"ECLI:\s*(?P<ecli>ES:[A-Z]+:\d{4}:\d+[A-Z]?)", re.I)
_DATE_RE = re.compile(r"Fecha:\s*(?P<d>\d{2})/(?P<m>\d{2})/(?P<y>\d{4})")
_ORGANO_RE = re.compile(r"Órgano:\s*(?P<o>[^\n]+)", re.I)
_PONENTE_RE = re.compile(r"Ponente:\s*(?P<p>[^\n]+)", re.I)
_FD_RE = re.compile(
    r"^\s*(?P<n>PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[ÉE]PTIMO|OCTAVO|NOVENO|D[ÉE]CIMO"
    r"(?:\s*(?:PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[ÉE]PTIMO|OCTAVO|NOVENO))?|\d{1,2})\s*[.\-–:]+",
    re.M | re.I,
)
# Frases típicas de la historia procesal que contaminan el benchmark (fuga del resultado previo).
_PROCEDURAL_RE = re.compile(
    r"(dict[óo]\s+sentencia|cuyo fallo|fallo\s+(?:es|era|del tenor)|parte dispositiva|recurso de (?:apelaci[óo]n|"
    r"suplicaci[óo]n|casaci[óo]n)|se interpuso recurso|interpuesto recurso|estim(?:ando|ó|a)\s+(?:parcialmente\s+)?"
    r"(?:la demanda|el recurso)|desestim(?:ando|ó|a)\s+(?:la demanda|el recurso)|Audiencia Provincial.*?dict|"
    r"Juzgado de (?:Primera Instancia|lo Social|lo Mercantil).*?dict|Tribunal Superior de Justicia.*?dict|"
    r"elev(?:aron|ados) los autos|se admiti[óo] a tr[áa]mite)",
    re.I,
)

_NIVEL_BY_PREFIX = {"STS": "TS", "ATS": "TS", "SAN": "AN", "STSJ": "TSJ", "SAP": "AP", "AAP": "AP"}


@dataclass
class SentenciaParseada:
    roj: str | None = None
    ecli: str | None = None
    fecha: date | None = None
    organo: str | None = None
    ponente: str | None = None
    nivel: str | None = None
    encabezado: str = ""
    antecedentes: str = ""
    antecedentes_purgados: str = ""
    fundamentos: str = ""
    fundamentos_lista: list[tuple[str, str]] = field(default_factory=list)
    fallo: str = ""
    votos_particulares: list[str] = field(default_factory=list)


def _section_kind(heading: str) -> str:
    h = re.sub(r"\s+", "", heading.upper())
    if h.startswith("ANTECEDENTES") or h.startswith("HECHOSPROBADOS"):
        return "antecedentes"
    if h.startswith("FUNDAMENTOS"):
        return "fundamentos"
    if h.startswith("VOTO"):
        return "voto"
    return "fallo"


def purge_antecedentes(text: str) -> str:
    """Elimina los párrafos que narran la tramitación y lo resuelto por instancias previas."""
    kept = [p for p in re.split(r"\n\s*\n|\n(?=[A-ZÁÉÍÓÚ]+\.?\s*[-.–])", text) if p.strip()]
    return "\n\n".join(p.strip() for p in kept if not _PROCEDURAL_RE.search(p))


def split_fundamentos(text: str) -> list[tuple[str, str]]:
    marks = list(_FD_RE.finditer(text))
    if not marks:
        return [("1", text.strip())] if text.strip() else []
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.group("n").upper(), text[m.end() : end].strip()))
    return out


def parse_sentencia(text: str) -> SentenciaParseada:
    result = SentenciaParseada()
    if m := _ROJ_RE.search(text):
        result.roj = " ".join(m.group("roj").upper().split())
        result.nivel = _NIVEL_BY_PREFIX.get(result.roj.split()[0], "JUZGADO")
    if m := _ECLI_RE.search(text):
        result.ecli = "ECLI:" + m.group("ecli").upper()
    if m := _DATE_RE.search(text):
        result.fecha = date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
    if m := _ORGANO_RE.search(text):
        result.organo = m.group("o").strip()
    if m := _PONENTE_RE.search(text):
        result.ponente = m.group("p").strip()

    heads = list(_SECTION_RE.finditer(text))
    result.encabezado = text[: heads[0].start()].strip() if heads else text.strip()
    for i, m in enumerate(heads):
        body = text[m.end() : heads[i + 1].start() if i + 1 < len(heads) else len(text)].strip()
        kind = _section_kind(m.group("h"))
        if kind == "antecedentes":
            result.antecedentes = (result.antecedentes + "\n\n" + body).strip()
        elif kind == "fundamentos" and not result.votos_particulares:
            result.fundamentos = (result.fundamentos + "\n\n" + body).strip()
        elif kind == "voto":
            result.votos_particulares.append(body)
        elif kind == "fallo" and not result.votos_particulares and not result.fallo:
            result.fallo = body
        elif result.votos_particulares:  # secciones dentro de un voto particular
            result.votos_particulares[-1] += "\n\n" + m.group(0).strip() + "\n" + body
    result.antecedentes_purgados = purge_antecedentes(result.antecedentes)
    result.fundamentos_lista = split_fundamentos(result.fundamentos)
    return result
