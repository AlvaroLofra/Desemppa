"""Spike en vivo de la Gemini API: modelos disponibles con la clave y una llamada en streaming.

Uso:  uv run python scripts/spike_gemini_live.py [alias]   (por defecto gemini_flash)
Solo envía un prompt sintético: nunca datos personales (dossier §1.1.4).
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google import genai  # noqa: E402

from config.settings import get_catalog, get_settings  # noqa: E402
from core.gemini_client import GeminiClient  # noqa: E402
from core.llm_types import LLMRequest, LLMResult  # noqa: E402


def list_models(api_key: str) -> list[str]:
    client = genai.Client(api_key=api_key)
    names = []
    for m in client.models.list():
        actions = m.supported_actions or []
        if "generateContent" in actions or "embedContent" in actions:
            names.append(f"{m.name}  [{', '.join(actions)}]")
    return sorted(names)


async def one_call(alias: str) -> None:
    settings, catalog = get_settings(), get_catalog()
    spec = catalog.models[alias]
    client = GeminiClient(settings.gemini_api_key)
    request = LLMRequest(system="Responde en español, en una frase.", prompt="¿Qué es un plazo de caducidad?",
                         effort="low")
    t0 = time.monotonic()
    first: float | None = None
    async for item in client.stream(alias=alias, spec=spec, request=request):
        if isinstance(item, LLMResult):
            print(f"\nmodelo={item.model} tokens={item.usage} total={item.latencia_ms} ms")
        else:
            first = first or time.monotonic() - t0
            print(item.text, end="", flush=True)
    print(f"primer token: {first:.2f} s" if first else "sin tokens")


def main() -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        print("GEMINI_API_KEY no configurada: spike omitido")
        return
    print("Modelos disponibles:")
    for name in list_models(settings.gemini_api_key):
        print("  ", name)
    asyncio.run(one_call(sys.argv[1] if len(sys.argv) > 1 else "gemini_flash"))


if __name__ == "__main__":
    main()
