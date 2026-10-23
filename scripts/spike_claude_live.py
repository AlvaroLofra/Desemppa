"""Spike en vivo de un proveedor CLI (Claude Code, Antigravity, Codex…) a través de su adaptador.

Uso:  uv run python scripts/spike_claude_live.py [--alias claude_haiku] [--repeat 1] [--record]
  --alias   alias de config/models.toml (p. ej. claude_haiku, agy_gemini_flash)
  --record  guarda la salida cruda en tests/fixtures/<proveedor>_stream/ok_<alias>.jsonl
Requisito: el CLI debe tener sesión iniciada. Consume una cantidad mínima de la cuota de la suscripción.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import ModelSpec, get_catalog, get_settings  # noqa: E402
from core.gemini_client import GeminiClient  # noqa: E402
from core.llm_types import LLMRequest, LLMResult  # noqa: E402
from core.providers.cli_adapter import CliAdapter  # noqa: E402
from core.providers.registry import build_registry  # noqa: E402

SYSTEM = "Eres un asistente conciso. Responde en español."
PROMPT = "Contexto de relleno para probar stdin largo. " * 900 + "\nResponde solo: hola mundo"  # ~40k car.


def adapter_for(alias: str) -> tuple[CliAdapter, ModelSpec]:
    settings, catalog = get_settings(), get_catalog()
    spec = catalog.models[alias]
    registry = build_registry(
        catalog, settings, gemini=GeminiClient(None), exe_overrides={"claude_cli": settings.claude_exe}
    )
    adapter = registry[spec.provider]
    if not isinstance(adapter, CliAdapter):
        raise SystemExit(f"{alias} no usa un proveedor CLI")
    return adapter, spec


def record_raw(alias: str) -> Path:
    adapter, spec = adapter_for(alias)
    request = LLMRequest(system=SYSTEM, prompt=PROMPT, effort="low")
    args, stdin, temps = adapter.build_call(spec.resolved_id("low"), request, spec.timeout_s)
    out = subprocess.run(args, input=stdin.encode("utf-8"), capture_output=True, timeout=300, cwd=adapter._sandbox)  # noqa: SLF001
    for t in temps:
        t.unlink(missing_ok=True)
    carpeta = {"claude_cli": "claude_stream", "antigravity_cli": "agy_stream"}.get(adapter.id, f"{adapter.id}_stream")
    target = ROOT / "tests" / "fixtures" / carpeta / f"ok_{alias}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(out.stdout)
    return target


async def run(alias: str, repeat: int) -> None:
    adapter, spec = adapter_for(alias)
    request = LLMRequest(system=SYSTEM, prompt=PROMPT, effort="low")
    failures = 0
    for i in range(repeat):
        t0 = time.monotonic()
        first: float | None = None
        try:
            async for item in adapter.stream(alias=alias, spec=spec, request=request):
                if isinstance(item, LLMResult):
                    print(
                        f"[{i + 1}] modelo={item.model} uso={item.usage} total={item.latencia_ms} ms "
                        f"primer_token={first and round(first, 2)} s texto={item.text[:60]!r}"
                    )
                elif first is None:
                    first = time.monotonic() - t0
        except Exception as exc:  # noqa: BLE001 — el spike informa y sigue
            failures += 1
            print(f"[{i + 1}] {type(exc).__name__}: {exc}")
    adapter.stop()
    print(f"llamadas={repeat} fallos={failures}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alias", default="claude_haiku")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    if args.record:
        print("fixture:", record_raw(args.alias))
    asyncio.run(run(args.alias, args.repeat))


if __name__ == "__main__":
    main()
