"""Pruebas en vivo (uv run pytest -m live). Llaman a servicios reales con prompts sintéticos.
Cada prueba se omite si su proveedor no está instalado o configurado."""

import time

import pytest

from config.settings import get_catalog, get_settings
from core.errors import NotAuthenticated
from core.gemini_client import GeminiClient
from core.llm_types import LLMRequest, LLMResult
from core.providers.registry import build_registry

pytestmark = pytest.mark.live
REQUEST = LLMRequest(system="Responde en español, en una frase.", prompt="Di solo: hola", effort="low")
# alias -> segundos máximos hasta el primer token
OBJETIVOS = {"gemini_flash": 3.0, "agy_gemini_flash": 15.0, "claude_sonnet": 10.0, "agy_claude_sonnet": 30.0}


@pytest.fixture(scope="module")
def registry():
    settings, catalog = get_settings(), get_catalog()
    reg = build_registry(
        catalog,
        settings,
        gemini=GeminiClient(settings.gemini_api_key),
        exe_overrides={"claude_cli": settings.claude_exe},
    )
    yield reg
    for adapter in reg.values():
        adapter.stop()


@pytest.mark.parametrize("alias", list(OBJETIVOS))
async def test_first_token_latency(registry, alias):
    spec = get_catalog().models[alias]
    adapter = registry.get(spec.provider)
    if adapter is None or not adapter.installed():
        pytest.skip(f"{spec.provider} no disponible")
    t0, first, result = time.monotonic(), None, None
    try:
        async for item in adapter.stream(alias=alias, spec=spec, request=REQUEST):
            if isinstance(item, LLMResult):
                result = item
            elif first is None:
                first = time.monotonic() - t0
    except NotAuthenticated:
        pytest.skip(f"{spec.provider} sin sesión iniciada")
    assert result is not None and result.text
    assert first is not None and first < OBJETIVOS[alias], f"primer token en {first:.1f} s"
