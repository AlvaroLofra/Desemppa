"""Pruebas en vivo (uv run pytest -m live). Llaman a servicios reales con prompts sintéticos."""

import time

import pytest

from config.settings import get_catalog, get_settings
from core.claude_worker import ClaudeWorker
from core.gemini_client import GeminiClient
from core.llm_types import LLMRequest, LLMResult

pytestmark = pytest.mark.live
REQUEST = LLMRequest(system="Responde en español, en una frase.", prompt="Di solo: hola", effort="low")


async def _first_token_and_result(stream):
    t0, first, result = time.monotonic(), None, None
    async for item in stream:
        if isinstance(item, LLMResult):
            result = item
        elif first is None:
            first = time.monotonic() - t0
    return first, result


async def test_gemini_first_token_under_3s():
    settings = get_settings()
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY no configurada")
    alias = "gemini_flash_stable"
    client = GeminiClient(settings.gemini_api_key)
    first, result = await _first_token_and_result(
        client.stream(alias=alias, spec=get_catalog().models[alias], request=REQUEST)
    )
    assert result is not None and result.text
    assert first is not None and first < 3.0


async def test_claude_sonnet_first_token_under_10s(tmp_path):
    settings = get_settings()
    worker = ClaudeWorker(
        sandbox_dir=tmp_path / "sb", lock_path=settings.claude_lock_path, exe=settings.claude_exe
    )
    try:
        first, result = await _first_token_and_result(
            worker.stream(alias="claude_sonnet", cli_model="sonnet", request=REQUEST, timeout_s=120)
        )
    finally:
        worker.stop()
    assert result is not None and result.text
    assert first is not None and first < 10.0
