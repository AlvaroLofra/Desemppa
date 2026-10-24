"""Adaptadores HTTP para APIs oficiales de las grandes compañías de IA (OpenAI, Anthropic, xAI/Grok,
DeepSeek, Mistral, OpenRouter y cualquier endpoint compatible con OpenAI Chat Completions).

Las claves pueden definirse en `.env` (variable `api_key_env` del proveedor) o guardarse desde la interfaz
web cifradas con DPAPI de Windows en `data/local/provider_keys.bin` (`ApiKeyStore`).
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx

from config.settings import Catalog, ModelSpec, ProviderSpec
from core.errors import (
    EmptyResponse,
    ModelUnavailable,
    NotAuthenticated,
    ProviderError,
    ProviderTimeout,
    RateLimited,
    UsageLimitReached,
)
from core.llm_types import LLMRequest, LLMResult, StreamChunk, Usage
from core.secure_store import decrypt, encrypt


class ApiKeyStore:
    """Almacén local cifrado con DPAPI para claves de API configuradas desde la interfaz web."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def _load(self) -> dict[str, str]:
        if not self._path.is_file():
            return {}
        try:
            raw = decrypt(self._path.read_bytes())
            data = json.loads(raw)
            return {str(k): str(v) for k, v in data.items() if isinstance(v, str) and v.strip()}
        except (OSError, ValueError, json.JSONDecodeError):
            return {}

    def get(self, provider_id: str, env_var: str | None = None) -> str | None:
        stored = self._load().get(provider_id)
        if stored:
            return stored.strip()
        if env_var:
            val = os.environ.get(env_var, "").strip()
            if val:
                return val
        return None

    def set(self, provider_id: str, api_key: str | None) -> None:
        current = self._load()
        if api_key and api_key.strip():
            current[provider_id] = api_key.strip()
        else:
            current.pop(provider_id, None)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_bytes(encrypt(json.dumps(current, ensure_ascii=False)))


def _classify_http_error(status: int, detail: str, provider: str) -> ProviderError:
    msg = f"HTTP {status} ({provider}): {detail[:300]}"
    low = detail.lower()
    if status in (401, 403) or "invalid api key" in low or "authentication" in low or "unauthorized" in low:
        return NotAuthenticated(msg, provider=provider)
    if status == 402 or "insufficient_quota" in low or "credit balance" in low or "billing" in low:
        return UsageLimitReached(msg, provider=provider)
    if status in (429, 502, 503, 529) or "rate limit" in low or "overloaded" in low:
        return RateLimited(msg, provider=provider)
    if status == 404 or "model_not_found" in low or "does not exist" in low:
        return ModelUnavailable(msg, provider=provider)
    return ProviderError(msg, provider=provider)


class OpenAICompatibleAdapter:
    """Adaptador para cualquier API compatible con OpenAI Chat Completions:
    OpenAI, xAI (Grok), DeepSeek, Mistral AI, OpenRouter, Perplexity, Groq, etc.
    """

    def __init__(
        self,
        provider_id: str,
        spec: ProviderSpec,
        key_store: ApiKeyStore,
        catalog: Catalog,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.id = provider_id
        self.spec = spec
        self._keys = key_store
        self._catalog = catalog
        self._transport = transport
        self._base_url = (spec.base_url or "https://api.openai.com/v1").rstrip("/")

    def _api_key(self) -> str | None:
        return self._keys.get(self.id, self.spec.api_key_env)

    def installed(self) -> bool:
        return bool(self._api_key())

    def discover_models(self, timeout_s: float = 30) -> list[str]:
        known = list(self.spec.modelos_conocidos) or sorted(
            {m.model_id for m in self._catalog.models.values() if m.provider == self.id}
        )
        key = self._api_key()
        if not key:
            return known
        try:
            with httpx.Client(timeout=timeout_s) as client:
                r = client.get(f"{self._base_url}/models", headers={"Authorization": f"Bearer {key}"})
                if r.status_code == 200:
                    data = r.json().get("data", [])
                    ids = [str(item["id"]) for item in data if isinstance(item, dict) and "id" in item]
                    return ids[:60] if ids else known
        except httpx.HTTPError:
            pass
        return known

    def stop(self) -> None:
        return None

    async def stream(
        self, *, alias: str, spec: ModelSpec, request: LLMRequest
    ) -> AsyncIterator[StreamChunk | LLMResult]:
        key = self._api_key()
        if not key:
            raise NotAuthenticated(
                f"Falta la clave de API para {self.spec.etiqueta} ({self.spec.api_key_env or self.id})",
                provider=self.id,
            )
        model = spec.resolved_id(request.effort)
        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.1}
        if request.json_mode and "reasoner" not in model.lower():
            payload["response_format"] = {"type": "json_object"}
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=spec.timeout_s, transport=self._transport) as client:
                r = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"{self.id} superó {spec.timeout_s:.0f} s", provider=self.id) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Error de red en {self.id}: {exc}", provider=self.id) from exc

        if r.status_code >= 400:
            raise _classify_http_error(r.status_code, r.text, self.id)
        body = r.json()
        choices = body.get("choices") or []
        text = str((choices[0].get("message") or {}).get("content") or "") if choices else ""
        if not text.strip():
            raise EmptyResponse(f"{self.id} devolvió una respuesta vacía", provider=self.id)
        usage_raw = body.get("usage") or {}
        yield StreamChunk(text=text)
        yield LLMResult(
            text=text,
            provider=self.id,
            alias=alias,
            model=str(body.get("model") or model),
            usage=Usage(
                input_tokens=usage_raw.get("prompt_tokens"),
                output_tokens=usage_raw.get("completion_tokens"),
            ),
            latencia_ms=int((time.monotonic() - started) * 1000),
        )


class AnthropicApiAdapter:
    """Adaptador para la API oficial de Anthropic (`https://api.anthropic.com/v1/messages`)."""

    def __init__(
        self,
        provider_id: str,
        spec: ProviderSpec,
        key_store: ApiKeyStore,
        catalog: Catalog,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.id = provider_id
        self.spec = spec
        self._keys = key_store
        self._catalog = catalog
        self._transport = transport
        self._base_url = (spec.base_url or "https://api.anthropic.com/v1").rstrip("/")

    def _api_key(self) -> str | None:
        return self._keys.get(self.id, self.spec.api_key_env)

    def installed(self) -> bool:
        return bool(self._api_key())

    def discover_models(self, timeout_s: float = 30) -> list[str]:
        return list(self.spec.modelos_conocidos) or sorted(
            {m.model_id for m in self._catalog.models.values() if m.provider == self.id}
        )

    def stop(self) -> None:
        return None

    async def stream(
        self, *, alias: str, spec: ModelSpec, request: LLMRequest
    ) -> AsyncIterator[StreamChunk | LLMResult]:
        key = self._api_key()
        if not key:
            raise NotAuthenticated(
                f"Falta la clave de API para {self.spec.etiqueta} ({self.spec.api_key_env or self.id})",
                provider=self.id,
            )
        model = spec.resolved_id(request.effort)
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": 8192,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.system:
            payload["system"] = request.system
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=spec.timeout_s, transport=self._transport) as client:
                r = await client.post(
                    f"{self._base_url}/messages",
                    headers={
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"{self.id} superó {spec.timeout_s:.0f} s", provider=self.id) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Error de red en {self.id}: {exc}", provider=self.id) from exc

        if r.status_code >= 400:
            raise _classify_http_error(r.status_code, r.text, self.id)
        body = r.json()
        blocks = body.get("content") or []
        text = "".join(str(b.get("text") or "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
        if not text.strip():
            raise EmptyResponse(f"{self.id} devolvió una respuesta vacía", provider=self.id)
        usage_raw = body.get("usage") or {}
        yield StreamChunk(text=text)
        yield LLMResult(
            text=text,
            provider=self.id,
            alias=alias,
            model=str(body.get("model") or model),
            usage=Usage(
                input_tokens=usage_raw.get("input_tokens"),
                output_tokens=usage_raw.get("output_tokens"),
            ),
            latencia_ms=int((time.monotonic() - started) * 1000),
        )
