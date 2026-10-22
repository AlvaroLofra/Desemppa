"""Parser de la salida `claude -p --output-format stream-json [--include-partial-messages]`.

Formato observado con el CLI 2.1.291 (ver tests/fixtures/claude_stream/):
  {"type":"system","subtype":"init","model":...}            -> modelo efectivo
  {"type":"stream_event","event":{"type":"content_block_delta","delta":{"type":"text_delta","text":...}}}
  {"type":"assistant","message":{...}}                     -> mensaje completo (no se re-emite)
  {"type":"result","is_error":bool,"result":str,"usage":{...},"total_cost_usd":float,...}
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from core.errors import NotAuthenticated, ProviderError, RateLimited, UsageLimitReached
from core.llm_types import StreamChunk, Usage

PROVIDER = "claude"

# Patrones de error del CLI. Los de "usage limit" no se pueden provocar a voluntad: revisar
# la primera vez que aparezca el mensaje real (docs/spike_entorno_fase0.md).
_AUTH_RE = re.compile(r"not logged in|/login|invalid api key|authentication|oauth token", re.I)
_USAGE_RE = re.compile(r"usage limit|limit reached|out of (extra )?usage|weekly limit|session limit", re.I)
_OVERLOAD_RE = re.compile(r"overloaded|rate.?limit|429|529|too many requests", re.I)


@dataclass
class ClaudeFinal:
    text: str
    model: str
    usage: Usage
    total_cost_usd: float | None
    duration_ms: int | None
    num_turns: int | None
    raw: dict[str, Any] = field(repr=False, default_factory=dict)


def classify_error(message: str) -> ProviderError:
    if _AUTH_RE.search(message):
        return NotAuthenticated(message, provider=PROVIDER)
    if _USAGE_RE.search(message):
        return UsageLimitReached(message, provider=PROVIDER)
    if _OVERLOAD_RE.search(message):
        return RateLimited(message, provider=PROVIDER)
    return ProviderError(message, provider=PROVIDER)


class StreamJsonParser:
    def __init__(self) -> None:
        self.model = ""
        self._parts: list[str] = []
        self.final: ClaudeFinal | None = None

    def feed(self, line: str) -> StreamChunk | None:
        """Procesa una línea. Devuelve un chunk de texto si la línea lo contiene; lanza si es un error."""
        line = line.strip()
        if not line:
            return None
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return None  # el CLI puede escribir avisos sueltos; se ignoran
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            self.model = event.get("model") or self.model
        elif kind == "stream_event":
            inner = event.get("event") or {}
            delta = inner.get("delta") or {}
            if inner.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                text = delta.get("text") or ""
                if text:
                    self._parts.append(text)
                    return StreamChunk(text=text)
        elif kind == "result":
            self._on_result(event)
        return None

    def _on_result(self, event: dict[str, Any]) -> None:
        result_text = str(event.get("result") or "")
        if event.get("is_error") or event.get("subtype", "success") != "success":
            raise classify_error(result_text or str(event.get("subtype")))
        usage = event.get("usage") or {}
        self.final = ClaudeFinal(
            text=result_text or "".join(self._parts),
            model=self.model,
            usage=Usage(input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens")),
            total_cost_usd=event.get("total_cost_usd"),
            duration_ms=event.get("duration_ms"),
            num_turns=event.get("num_turns"),
            raw=event,
        )

    @property
    def streamed_text(self) -> str:
        return "".join(self._parts)
