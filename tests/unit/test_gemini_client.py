from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors
from google.genai import types

from core.errors import ModelUnavailable, ProviderError, RateLimited
from core.gemini_client import GeminiClient, TokenBucket
from core.llm_types import LLMRequest, LLMResult, StreamChunk


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def _api_error(code, message="boom", cls=genai_errors.APIError):
    return cls(code, {"error": {"code": code, "message": message, "status": "X"}})


def _piece(text, usage=None):
    return SimpleNamespace(text=text, usage_metadata=usage)


class FakeModels:
    """Cada elemento de `script` es una excepción (se lanza al llamar) o una lista de piezas."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    async def generate_content_stream(self, *, model, contents, config):
        self.calls.append((model, contents, config))
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step

        async def gen():
            for p in step:
                if isinstance(p, Exception):
                    raise p
                yield p

        return gen()


def _client(script, clock, **kw):
    models = FakeModels(script)
    fake = SimpleNamespace(aio=SimpleNamespace(models=models))
    return GeminiClient(None, client=fake, sleep=clock.sleep, clock=clock, **kw), models


async def _collect(client, catalog, alias="gemini_flash", effort="low", schema=None):
    req = LLMRequest(system="sys", prompt="p", effort=effort, response_schema=schema)
    return [i async for i in client.stream(alias=alias, spec=catalog.models[alias], request=req)]


async def test_gemini_rate_limiter_token_bucket():
    clock = FakeClock()
    bucket = TokenBucket(6, clock=clock, sleep=clock.sleep)  # 6 rpm = 1 ficha cada 10 s
    for _ in range(6):
        assert await bucket.acquire() == 0
    waited = await bucket.acquire()
    assert waited == pytest.approx(10.0)
    clock.now += 25  # rellena 2,5 fichas
    assert await bucket.acquire() == 0
    assert await bucket.acquire() == 0
    assert await bucket.acquire() == pytest.approx(5.0)


async def test_stream_yields_chunks_and_usage(catalog):
    clock = FakeClock()
    usage = SimpleNamespace(prompt_token_count=10, candidates_token_count=4, thoughts_token_count=6)
    client, models = _client([[_piece("ho"), _piece("la", usage)]], clock)
    items = await _collect(client, catalog, effort="high", schema={"type": "object"})
    assert [i.text for i in items if isinstance(i, StreamChunk)] == ["ho", "la"]
    result = items[-1]
    assert isinstance(result, LLMResult) and result.text == "hola"
    assert result.usage.input_tokens == 10 and result.usage.output_tokens == 10
    config = models.calls[0][2]
    assert config.thinking_config.thinking_level == types.ThinkingLevel.HIGH
    assert config.response_mime_type == "application/json"
    assert config.system_instruction == "sys"


async def test_gemini_429_backoff(catalog):
    clock = FakeClock()
    client, models = _client([_api_error(429), _api_error(503), [_piece("ok")]], clock)
    items = await _collect(client, catalog)
    assert items[-1].text == "ok"
    assert len(models.calls) == 3
    assert len(clock.sleeps) == 2 and clock.sleeps[1] > clock.sleeps[0]


async def test_gemini_429_exhausted_raises_rate_limited(catalog):
    clock = FakeClock()
    client, _ = _client([_api_error(429)] * 4, clock, max_retries=3)
    with pytest.raises(RateLimited):
        await _collect(client, catalog)


async def test_404_is_model_unavailable(catalog):
    client, _ = _client([_api_error(404, "not found")], FakeClock())
    with pytest.raises(ModelUnavailable):
        await _collect(client, catalog)


async def test_thinking_level_rejected_falls_back_to_budget(catalog):
    client, models = _client(
        [_api_error(400, "thinking_level is not supported"), [_piece("ok")]], FakeClock()
    )
    await _collect(client, catalog, effort="medium")
    assert models.calls[1][2].thinking_config.thinking_budget == 8192


async def test_error_after_first_token_not_retried(catalog):
    client, models = _client([[_piece("a"), _api_error(503)]], FakeClock())
    with pytest.raises(ProviderError):
        await _collect(client, catalog)
    assert len(models.calls) == 1


async def test_daily_limit_blocks_before_calling(catalog):
    spec = catalog.models["gemini_flash"]
    client, models = _client([], FakeClock(), daily_count=lambda _m: spec.rpd)
    with pytest.raises(RateLimited, match="RPD"):
        await _collect(client, catalog)
    assert models.calls == []


async def test_no_key_is_model_unavailable(catalog):
    client = GeminiClient(None)
    assert not client.configured
    with pytest.raises(ModelUnavailable):
        await _collect(client, catalog)
