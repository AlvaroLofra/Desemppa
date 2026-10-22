"""Tipos comunes de petición/respuesta para todos los proveedores LLM."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Effort = Literal["low", "medium", "high"]


class LLMRequest(BaseModel):
    system: str = ""
    prompt: str
    effort: Effort = "medium"
    response_schema: dict[str, Any] | None = None  # JSON Schema para salida estructurada (Gemini)


class StreamChunk(BaseModel):
    text: str


class Usage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMResult(BaseModel):
    text: str
    provider: Literal["gemini", "claude"]
    alias: str
    model: str  # id efectivo informado por el proveedor
    usage: Usage = Field(default_factory=Usage)
    coste_equivalente_usd: float | None = None  # Claude Pro no factura: coste orientativo del CLI
    latencia_ms: int = 0
    degradado: bool = False
    avisos: list[str] = Field(default_factory=list)
