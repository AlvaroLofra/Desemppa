from __future__ import annotations

import httpx
import pytest

from config.settings import ModelSpec, ProviderSpec, load_catalog
from core.errors import NotAuthenticated, RateLimited
from core.llm_types import LLMRequest, LLMResult, StreamChunk
from core.providers.http_adapter import AnthropicApiAdapter, ApiKeyStore, OpenAICompatibleAdapter


def test_api_key_store_roundtrip(tmp_path):
    store = ApiKeyStore(tmp_path / "keys.bin")
    assert store.get("openai_api", None) is None
    store.set("openai_api", "sk-secret-key")
    assert store.get("openai_api", None) == "sk-secret-key"
    # Nueva instancia lee de disco cifrado con DPAPI
    store2 = ApiKeyStore(tmp_path / "keys.bin")
    assert store2.get("openai_api", None) == "sk-secret-key"
    store2.set("openai_api", None)
    assert store2.get("openai_api", None) is None


async def test_openai_compatible_adapter_streams_response(tmp_path):
    store = ApiKeyStore(tmp_path / "keys.bin")
    store.set("openai_api", "sk-test")
    catalog = load_catalog()
    spec = ProviderSpec(
        tipo="api_openai",
        etiqueta="OpenAI API",
        compania="OpenAI",
        modalidad="api",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        habilitado=True,
    )
    model_spec = ModelSpec(
        etiqueta="GPT-4.1",
        provider="openai_api",
        model_id="gpt-4.1",
        efforts=["low", "medium", "high"],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer sk-test"
        return httpx.Response(
            200,
            json={
                "model": "gpt-4.1-2026",
                "choices": [{"message": {"content": "Hola mundo"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    adapter = OpenAICompatibleAdapter("openai_api", spec, store, catalog, transport=httpx.MockTransport(handler))
    items = [
        item
        async for item in adapter.stream(
            alias="openai_gpt41",
            spec=model_spec,
            request=LLMRequest(system="Eres jurista", prompt="Saluda", json_mode=True),
        )
    ]

    chunks = [i.text for i in items if isinstance(i, StreamChunk)]
    assert "".join(chunks) == "Hola mundo"
    res = items[-1]
    assert isinstance(res, LLMResult)
    assert res.text == "Hola mundo" and res.usage.input_tokens == 10 and res.usage.output_tokens == 5


async def test_anthropic_adapter_streams_and_handles_errors(tmp_path):
    store = ApiKeyStore(tmp_path / "keys.bin")
    store.set("anthropic_api", "sk-ant-test")
    catalog = load_catalog()
    spec = ProviderSpec(
        tipo="api_anthropic",
        etiqueta="Anthropic API",
        compania="Anthropic",
        modalidad="api",
        base_url="https://api.anthropic.com/v1",
        api_key_env="ANTHROPIC_API_KEY",
        habilitado=True,
    )
    model_spec = ModelSpec(
        etiqueta="Claude Sonnet API",
        provider="anthropic_api",
        model_id="claude-sonnet-4-6",
        efforts=["low", "medium", "high"],
    )

    def ok_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "sk-ant-test"
        return httpx.Response(
            200,
            json={
                "model": "claude-sonnet-4-6",
                "content": [{"type": "text", "text": "Respuesta OK"}],
                "usage": {"input_tokens": 12, "output_tokens": 4},
            },
        )

    def err_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limit exceeded")

    adapter_ok = AnthropicApiAdapter("anthropic_api", spec, store, catalog, transport=httpx.MockTransport(ok_handler))
    items = [
        item
        async for item in adapter_ok.stream(
            alias="anthropic_sonnet_api",
            spec=model_spec,
            request=LLMRequest(prompt="Hola"),
        )
    ]
    res = items[-1]
    assert isinstance(res, LLMResult)
    assert res.text == "Respuesta OK" and res.usage.input_tokens == 12 and res.usage.output_tokens == 4

    adapter_err = AnthropicApiAdapter("anthropic_api", spec, store, catalog, transport=httpx.MockTransport(err_handler))
    with pytest.raises(RateLimited):
        _ = [
            i
            async for i in adapter_err.stream(
                alias="anthropic_sonnet_api",
                spec=model_spec,
                request=LLMRequest(prompt="Hola"),
            )
        ]

    store.set("anthropic_api", None)
    with pytest.raises(NotAuthenticated):
        _ = [
            i
            async for i in adapter_err.stream(
                alias="anthropic_sonnet_api",
                spec=model_spec,
                request=LLMRequest(prompt="Hola"),
            )
        ]
