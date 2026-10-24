"""Micro-validador NLI (G5): ¿la afirmación se deduce de la cita verificada? Familia cruzada, T=0 implícita."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from core.llm_types import LLMRequest, LLMResult
from core.router import ModelRouter

Label = Literal["ENTAILS", "NEUTRAL", "CONTRADICTS"]

SYSTEM = (
    "Eres un verificador de inferencia lógica (NLI) para textos jurídicos españoles. Para cada par "
    "(premisa, hipótesis) decide: ENTAILS si la premisa, leída literalmente, implica la hipótesis; "
    "CONTRADICTS si la premisa la contradice; NEUTRAL si no la implica ni la contradice. No uses conocimiento "
    "externo: solo la premisa. Responde únicamente con el JSON pedido."
)
SCHEMA = {
    "type": "object",
    "properties": {
        "resultados": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "etiqueta": {"type": "string", "enum": ["ENTAILS", "NEUTRAL", "CONTRADICTS"]},
                    "motivo": {"type": "string"},
                },
                "required": ["id", "etiqueta"],
            },
        }
    },
    "required": ["resultados"],
}


@dataclass
class NLIResult:
    label: Label
    motivo: str = ""


def extract_json(text: str) -> dict[str, object]:
    """Tolera ```json ... ``` y texto alrededor (salida de Claude CLI sin structured output)."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("la respuesta no contiene JSON")
    return dict(json.loads(text[start : end + 1]))


class NLIChecker:
    def __init__(self, router: ModelRouter, profile: str) -> None:
        self._router = router
        self._profile = profile

    async def check(self, pares: list[tuple[str, str]], *, consulta_id: str | None = None) -> list[NLIResult]:
        if not pares:
            return []
        # Identificadores de texto («P0», «P1»…) que el verificador debe repetir: con índices numéricos un modelo
        # que cuente desde 1 desplazaba todas las etiquetas (falso CONTRADICTS visto en vivo el 25-10-2026).
        prompt = (
            'Evalúa estos pares y devuelve {"resultados": [{"id": "P0", "etiqueta": "...", "motivo": "..."}]}, '
            "un resultado por par, copiando su id exacto.\n\n"
        )
        prompt += "\n\n".join(
            f"### Par P{i}\nPREMISA: {premisa}\nHIPÓTESIS: {hipotesis}" for i, (premisa, hipotesis) in enumerate(pares)
        )
        request = LLMRequest(system=SYSTEM, prompt=prompt, response_schema=SCHEMA)
        text = ""
        async for item in self._router.stream(
            self._profile, "nli", request, fase="guardarrailes", consulta_id=consulta_id
        ):
            if isinstance(item, LLMResult):
                text = item.text
        data = extract_json(text)
        out: list[NLIResult] = [NLIResult("NEUTRAL", "sin evaluar") for _ in pares]
        resultados = data.get("resultados", [])
        for r in resultados if isinstance(resultados, list) else []:
            if not isinstance(r, dict):
                continue
            idx = _indice(r, "P")
            if 0 <= idx < len(pares) and r.get("etiqueta") in ("ENTAILS", "NEUTRAL", "CONTRADICTS"):
                out[idx] = NLIResult(r["etiqueta"], str(r.get("motivo", "")))
        return out


SYSTEM_HECHOS = (
    "Eres un verificador de hechos para un asistente jurídico. Recibes los HECHOS que contó el ciudadano y FRASES de "
    "la respuesta que se le va a dar. Marca solo las frases que afirman como ocurrido un hecho concreto del caso "
    "(qué pasó, qué hizo, dijo, alegó u ofreció alguna persona o empresa, fechas, importes) que NO consta en los "
    "HECHOS. No marques explicaciones de la ley, valoraciones, consejos ni riesgos en condicional. "
    "Responde únicamente con el JSON pedido."
)


async def hechos_no_constatados(
    router: ModelRouter, profile: str, frases: list[str], hechos: str, *, consulta_id: str | None = None
) -> list[str]:
    """Devuelve las frases que atribuyen al caso hechos que el ciudadano no ha contado."""
    if not frases:
        return []
    prompt = (
        'Devuelve {"no_constatados": [{"id": "F0", "motivo": "..."}]} copiando el id exacto de cada frase marcada '
        "(lista vacía si todas son correctas).\n\n"
        f"HECHOS DEL CIUDADANO:\n{hechos[:6000]}\n\n" + "\n".join(f"### Frase F{i}: {f}" for i, f in enumerate(frases))
    )
    text = ""
    async for item in router.stream(
        profile,
        "nli",
        LLMRequest(system=SYSTEM_HECHOS, prompt=prompt, json_mode=True),
        fase="guardarrailes",
        consulta_id=consulta_id,
    ):
        if isinstance(item, LLMResult):
            text = item.text
    data = extract_json(text)
    marcadas = data.get("no_constatados", [])
    out: list[str] = []
    for r in marcadas if isinstance(marcadas, list) else []:
        idx = _indice(r, "F") if isinstance(r, dict) else -1
        if 0 <= idx < len(frases):
            out.append(frases[idx])
    return list(dict.fromkeys(out))


def _indice(r: dict[str, object], prefijo: str) -> int:
    """«P3» -> 3. Acepta también el formato antiguo {"indice": 3}."""
    ident = str(r.get("id", ""))
    if ident.startswith(prefijo) and ident[1:].isdigit():
        return int(ident[1:])
    valor = r.get("indice")
    return valor if isinstance(valor, int) else -1
