"""Cliente Gemini API (AI Studio) con streaming, rate limiting local y backoff (dossier §1.1.2)."""

from __future__ import annotations

import asyncio
import random
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from config.settings import ModelSpec
from core.errors import ModelUnavailable, ProviderError, ProviderTimeout, RateLimited
from core.llm_types import Effort, LLMRequest, LLMResult, StreamChunk, Usage

PROVIDER = "gemini"
_RETRYABLE = {429, 500, 503}
_THINKING_LEVEL: dict[Effort, types.ThinkingLevel] = {
    "low": types.ThinkingLevel.LOW,
    "medium": types.ThinkingLevel.MEDIUM,
    "high": types.ThinkingLevel.HIGH,
}
_THINKING_BUDGET: dict[Effort, int] = {"low": 1024, "medium": 8192, "high": 24576}


_RETRY_IN_RE = re.compile(r"retry in (?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", re.I)
_RETRY_DELAY_RE = re.compile(r"'retryDelay': '(\d+)s'")


def quota_retry_seconds(message: str) -> float | None:
    """Segundos hasta que la API vuelve a aceptar peticiones según el 429 ("Please retry in 7h42m39s")."""
    if m := _RETRY_DELAY_RE.search(message):
        return float(m.group(1))
    m = _RETRY_IN_RE.search(message)
    if not m or not any(m.groups()):
        return None
    h, mi, s = (float(g) if g else 0.0 for g in m.groups())
    return h * 3600 + mi * 60 + s


class TokenBucket:
    """Bucket de `rpm` fichas que se rellena de forma continua (rpm/60 por segundo)."""

    def __init__(
        self,
        rpm: int,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.capacity = float(rpm)
        self.tokens = float(rpm)
        self.rate = rpm / 60.0
        self._clock = clock
        self._sleep = sleep
        self._last = clock()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = self._clock()
        self.tokens = min(self.capacity, self.tokens + (now - self._last) * self.rate)
        self._last = now

    async def acquire(self) -> float:
        """Consume una ficha; devuelve los segundos esperados."""
        waited = 0.0
        async with self._lock:
            self._refill()
            while self.tokens < 1:
                delay = (1 - self.tokens) / self.rate
                await self._sleep(delay)
                waited += delay
                self._refill()
            self.tokens -= 1
        return waited


class GeminiClient:
    def __init__(
        self,
        api_key: str | None,
        *,
        daily_count: Callable[[str], int] = lambda _model: 0,
        max_retries: int = 3,
        client: Any | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._api_key = api_key
        self._client = client
        self._daily_count = daily_count
        self._max_retries = max_retries
        self._sleep = sleep
        self._clock = clock
        self._buckets: dict[str, TokenBucket] = {}
        self._exhausted: dict[str, float] = {}  # model_id -> instante (clock) en que vuelve a haber cuota

    @property
    def configured(self) -> bool:
        return self._client is not None or bool(self._api_key)

    def _get_client(self) -> Any:
        if self._client is None:
            if not self._api_key:
                raise ModelUnavailable("GEMINI_API_KEY no configurada", provider=PROVIDER)
            # Sin reintentos internos del SDK: el backoff lo gobierna este cliente (y el router degrada).
            self._client = genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
            )
        return self._client

    def _bucket(self, alias: str, spec: ModelSpec) -> TokenBucket | None:
        if not spec.rpm:
            return None
        if alias not in self._buckets:
            self._buckets[alias] = TokenBucket(spec.rpm, clock=self._clock, sleep=self._sleep)
        return self._buckets[alias]

    @staticmethod
    def build_config(request: LLMRequest, *, use_budget: bool = False) -> types.GenerateContentConfig:
        thinking = (
            types.ThinkingConfig(thinking_budget=_THINKING_BUDGET[request.effort])
            if use_budget
            else types.ThinkingConfig(thinking_level=_THINKING_LEVEL[request.effort])
        )
        return types.GenerateContentConfig(
            system_instruction=request.system or None,
            thinking_config=thinking,
            response_mime_type="application/json" if request.response_schema or request.json_mode else None,
            response_json_schema=request.response_schema,
        )

    async def stream(
        self, *, alias: str, spec: ModelSpec, request: LLMRequest
    ) -> AsyncIterator[StreamChunk | LLMResult]:
        assert spec.model_id is not None
        client = self._get_client()
        until = self._exhausted.get(spec.model_id)
        if until is not None and self._clock() < until:
            raise RateLimited(f"{spec.model_id}: cuota diaria agotada", provider=PROVIDER)
        if spec.rpd and self._daily_count(spec.model_id) >= spec.rpd:
            raise RateLimited(f"límite diario local ({spec.rpd} RPD) de {spec.model_id}", provider=PROVIDER)
        bucket = self._bucket(alias, spec)
        use_budget = False
        attempt = 0
        started = self._clock()
        while True:
            if bucket is not None:
                await bucket.acquire()
            parts: list[str] = []
            usage = Usage()
            try:
                async with asyncio.timeout(spec.timeout_s):
                    response = await client.aio.models.generate_content_stream(
                        model=spec.model_id,
                        contents=request.prompt,
                        config=self.build_config(request, use_budget=use_budget),
                    )
                    async for piece in response:
                        text = piece.text or ""
                        if text:
                            parts.append(text)
                            yield StreamChunk(text=text)
                        meta = piece.usage_metadata
                        if meta is not None:
                            usage = Usage(
                                input_tokens=meta.prompt_token_count,
                                output_tokens=(meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0),
                            )
            except TimeoutError as exc:
                raise ProviderTimeout(f"{spec.model_id} superó {spec.timeout_s:.0f} s", provider=PROVIDER) from exc
            except genai_errors.APIError as exc:
                if parts:  # ya se emitió texto: no se puede reintentar de forma transparente
                    raise ProviderError(f"stream de Gemini interrumpido: {exc}", provider=PROVIDER) from exc
                code = exc.code or 0
                message = str(exc)
                if code == 400 and not use_budget and "thinking" in message.lower():
                    use_budget = True  # el modelo no admite thinking_level: probar con presupuesto
                    continue
                if code == 404:
                    raise ModelUnavailable(f"{spec.model_id}: {message}", provider=PROVIDER) from exc
                if code in (401, 403):
                    raise ModelUnavailable(f"clave Gemini rechazada: {message}", provider=PROVIDER) from exc
                retry_s = quota_retry_seconds(message)
                if code == 429 and retry_s is not None and retry_s > 60:
                    # Cuota diaria del modelo agotada: no se reintenta; se salta el modelo hasta el reinicio.
                    self._exhausted[spec.model_id] = self._clock() + retry_s
                    raise RateLimited(
                        f"{spec.model_id}: cuota diaria agotada (reinicio en {retry_s / 3600:.1f} h)",
                        provider=PROVIDER,
                        retry_after=retry_s,
                    ) from exc
                if code in _RETRYABLE and attempt < self._max_retries:
                    attempt += 1
                    await self._sleep(min(30.0, 2**attempt) + random.uniform(0, 1))
                    continue
                if code in _RETRYABLE:
                    raise RateLimited(f"{spec.model_id}: {message}", provider=PROVIDER) from exc
                raise ProviderError(f"{spec.model_id}: {message}", provider=PROVIDER) from exc
            yield LLMResult(
                text="".join(parts),
                provider="gemini",
                alias=alias,
                model=spec.model_id,
                usage=usage,
                latencia_ms=int((self._clock() - started) * 1000),
            )
            return
