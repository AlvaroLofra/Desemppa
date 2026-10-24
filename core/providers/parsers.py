"""Parsers de la salida NDJSON de cada CLI. Interfaz común:

feed(line) -> StreamChunk | None   (lanza ProviderError tipado si la línea es un error final)
final: CliFinal | None             (resultado al terminar)
finish(stderr) -> None             (lanza si el proceso acabó sin resultado válido)
avisos: list[str]                  (incidencias no fatales: p. ej. intentos de usar herramientas)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from core.errors import (
    EmptyResponse,
    NotAuthenticated,
    ProviderError,
    ProviderTimeout,
    RateLimited,
    UsageLimitReached,
)
from core.llm_types import StreamChunk, Usage

_AUTH_RE = re.compile(
    r"not logged in|/login|invalid api key|authentication|oauth token|not authenticated|sign in|log in", re.I
)
_USAGE_RE = re.compile(
    r"usage limit|limit reached|out of (extra )?usage|weekly limit|session limit|quota (exceeded|exhausted)", re.I
)
_OVERLOAD_RE = re.compile(r"overloaded|rate.?limit|429|529|too many requests|resource.?exhausted", re.I)


def classify_error(message: str, provider: str) -> ProviderError:
    if _AUTH_RE.search(message):
        return NotAuthenticated(message, provider=provider)
    if _USAGE_RE.search(message):
        return UsageLimitReached(message, provider=provider)
    if _OVERLOAD_RE.search(message):
        return RateLimited(message, provider=provider)
    return ProviderError(message, provider=provider)


@dataclass
class CliFinal:
    text: str
    model: str
    usage: Usage
    total_cost_usd: float | None = None
    duration_ms: int | None = None
    num_turns: int | None = None
    raw: dict[str, Any] = field(repr=False, default_factory=dict)


class CliParser(Protocol):
    final: CliFinal | None
    avisos: list[str]

    def feed(self, line: str) -> StreamChunk | None: ...
    def finish(self, stderr: str) -> None: ...


def _loads(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None  # los CLI escriben a veces avisos sueltos
    return data if isinstance(data, dict) else None


class ClaudeStreamParser:
    """`claude -p --output-format stream-json --include-partial-messages` (CLI 2.1.x)."""

    def __init__(self, provider: str = "claude_cli") -> None:
        self.provider = provider
        self.model = ""
        self._parts: list[str] = []
        self.final: CliFinal | None = None
        self.avisos: list[str] = []

    def feed(self, line: str) -> StreamChunk | None:
        event = _loads(line)
        if event is None:
            return None
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
            result_text = str(event.get("result") or "")
            if event.get("is_error") or event.get("subtype", "success") != "success":
                raise classify_error(result_text or str(event.get("subtype")), self.provider)
            usage = event.get("usage") or {}
            self.final = CliFinal(
                text=result_text or "".join(self._parts),
                model=self.model,
                usage=Usage(input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens")),
                total_cost_usd=event.get("total_cost_usd"),
                duration_ms=event.get("duration_ms"),
                num_turns=event.get("num_turns"),
                raw=event,
            )
        return None

    def finish(self, stderr: str) -> None:
        if self.final is None:
            raise classify_error(stderr or "el CLI terminó sin evento result", self.provider)

    @property
    def streamed_text(self) -> str:
        return "".join(self._parts)


class AgyStreamParser:
    """`agy ... --output-format stream-json` (docs/spike_antigravity.md)."""

    def __init__(self, provider: str = "antigravity_cli") -> None:
        self.provider = provider
        self.model = ""
        self._parts: list[str] = []
        self.final: CliFinal | None = None
        self.avisos: list[str] = []

    def feed(self, line: str) -> StreamChunk | None:
        event = _loads(line)
        if event is None:
            return None
        kind = event.get("event")
        body = event.get(kind) if isinstance(kind, str) else None
        if not isinstance(body, dict):
            return None
        if kind == "init":
            self.model = str(body.get("model") or self.model)
        elif kind == "step_update":
            step = body.get("step_type")
            if step == "agent_response" and body.get("text_delta"):
                text = str(body["text_delta"])
                self._parts.append(text)
                return StreamChunk(text=text)
            if step == "tool" and body.get("state") == "ACTIVE":
                self.avisos.append(f"el modelo intentó usar la herramienta '{body.get('tool_name')}' (sin efecto)")
        elif kind == "result":
            status = str(body.get("status", ""))
            if status != "SUCCESS":
                raise classify_error(str(body.get("error") or body.get("response") or status), self.provider)
            structured = body.get("structured_output")
            text = (
                json.dumps(structured, ensure_ascii=False)
                if structured is not None
                else str(body.get("response") or "")
            )
            usage = body.get("usage") or {}
            self.final = CliFinal(
                text=text,
                model=self.model,
                usage=Usage(
                    input_tokens=usage.get("input_tokens"),
                    output_tokens=(usage.get("output_tokens") or 0) + (usage.get("thinking_tokens") or 0),
                ),
                duration_ms=int(float(body.get("duration_seconds") or 0) * 1000),
                num_turns=body.get("num_turns"),
                raw=body,
            )
            if body.get("denied_actions"):
                self.avisos.append("acciones de herramienta denegadas por el modo no interactivo")
        return None

    def finish(self, stderr: str) -> None:
        if "print timeout" in stderr.lower():
            raise ProviderTimeout(f"agy: tiempo agotado ({stderr.strip()[:200]})", provider=self.provider)
        if self.final is None:
            raise classify_error(stderr or "agy terminó sin evento result", self.provider)
        if not self.final.text.strip():
            denegadas = " (intentó usar una herramienta y se le denegó)" if self.final.raw.get("denied_actions") else ""
            raise EmptyResponse(
                f"agy devolvió una respuesta vacía{denegadas}. {stderr.strip()[:300]}", provider=self.provider
            )


class CodexJsonlParser:
    """`codex exec --json` — EXPERIMENTAL, sin fixtures reales todavía (Codex no está instalado).

    Eventos esperados: {"type":"item.completed","item":{"type":"agent_message","text":...}},
    {"type":"turn.completed","usage":{...}}, {"type":"error"|"turn.failed", ...}.
    """

    def __init__(self, provider: str = "codex_cli") -> None:
        self.provider = provider
        self._parts: list[str] = []
        self._usage = Usage()
        self._done = False
        self.final: CliFinal | None = None
        self.avisos: list[str] = []

    def feed(self, line: str) -> StreamChunk | None:
        event = _loads(line)
        if event is None:
            return None
        kind = str(event.get("type", ""))
        if kind in ("error", "turn.failed"):
            err = event.get("error")
            msg = err.get("message") if isinstance(err, dict) else (err or event.get("message") or kind)
            raise classify_error(str(msg), self.provider)
        if kind == "item.completed":
            item = event.get("item") or {}
            if item.get("type") in ("agent_message", "assistant_message") and item.get("text"):
                text = str(item["text"])
                self._parts.append(text)
                return StreamChunk(text=text)
        if kind == "turn.completed":
            u = event.get("usage") or {}
            self._usage = Usage(input_tokens=u.get("input_tokens"), output_tokens=u.get("output_tokens"))
            self._done = True
        return None

    def finish(self, stderr: str) -> None:
        if not self._parts:
            raise classify_error(stderr or "codex terminó sin respuesta", self.provider)
        self.final = CliFinal(text="".join(self._parts), model="", usage=self._usage)


PARSERS: dict[str, type[ClaudeStreamParser] | type[AgyStreamParser] | type[CodexJsonlParser]] = {
    "claude_stream_json": ClaudeStreamParser,
    "agy_stream_json": AgyStreamParser,
    "codex_jsonl": CodexJsonlParser,
}


def make_parser(name: str, provider: str) -> CliParser:
    if name not in PARSERS:
        raise ValueError(f"parser desconocido: {name}")
    return PARSERS[name](provider)
