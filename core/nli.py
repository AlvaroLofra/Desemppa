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
                    "indice": {"type": "integer"},
                    "etiqueta": {"type": "string", "enum": ["ENTAILS", "NEUTRAL", "CONTRADICTS"]},
                    "motivo": {"type": "string"},
                },
                "required": ["indice", "etiqueta"],
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
        prompt = 'Evalúa estos pares y devuelve {"resultados": [{"indice", "etiqueta", "motivo"}]}.\n\n'
        prompt += "\n\n".join(
            f"### Par {i}\nPREMISA: {premisa}\nHIPÓTESIS: {hipotesis}" for i, (premisa, hipotesis) in enumerate(pares)
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
            idx = int(r.get("indice", -1))
            if 0 <= idx < len(pares) and r.get("etiqueta") in ("ENTAILS", "NEUTRAL", "CONTRADICTS"):
                out[idx] = NLIResult(r["etiqueta"], str(r.get("motivo", "")))
        return out
