"""Spike en vivo de `claude -p` a través de ClaudeWorker.

Uso:  uv run python scripts/spike_claude_live.py [--model haiku] [--repeat 1] [--record]
  --record   guarda la salida cruda stream-json en tests/fixtures/claude_stream/ok_<model>.jsonl
Requisito: el CLI debe tener sesión iniciada (ejecutar `claude` y `/login` una vez en una terminal).
Consume una cantidad mínima de la cuota de Claude Pro.
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

from config.settings import get_settings  # noqa: E402
from core.claude_worker import ClaudeWorker, build_args  # noqa: E402
from core.llm_types import LLMRequest, LLMResult  # noqa: E402

SYSTEM = "Eres un asistente conciso. Responde en español."
PROMPT = "Contexto de relleno para probar stdin largo. " * 900 + "\nResponde solo: hola mundo"  # ~40k car.


def record_raw(model: str) -> Path:
    settings = get_settings()
    assert settings.claude_sandbox_dir is not None
    settings.claude_sandbox_dir.mkdir(parents=True, exist_ok=True)
    sys_file = settings.claude_sandbox_dir / "spike_system.md"
    sys_file.write_text(SYSTEM, encoding="utf-8")
    exe = settings.claude_exe or "claude"
    out = subprocess.run(
        build_args(exe, model, "low", sys_file), input=PROMPT.encode("utf-8"), capture_output=True,
        cwd=settings.claude_sandbox_dir, timeout=180,
    )
    target = ROOT / "tests" / "fixtures" / "claude_stream" / f"ok_{model}.jsonl"
    target.write_bytes(out.stdout)
    return target


async def run(model: str, repeat: int) -> None:
    settings = get_settings()
    assert settings.claude_sandbox_dir is not None
    worker = ClaudeWorker(
        sandbox_dir=settings.claude_sandbox_dir, lock_path=settings.claude_lock_path, exe=settings.claude_exe
    )
    request = LLMRequest(system=SYSTEM, prompt=PROMPT, effort="low")
    failures = 0
    for i in range(repeat):
        t0 = time.monotonic()
        first: float | None = None
        try:
            async for item in worker.stream(alias=f"claude_{model}", cli_model=model, request=request,
                                            timeout_s=180):
                if isinstance(item, LLMResult):
                    print(f"[{i + 1}] modelo={item.model} uso={item.usage}"
                          f" coste_eq={item.coste_equivalente_usd} total={item.latencia_ms} ms"
                          f" primer_token={first and round(first, 2)} s"
                          f" texto={item.text[:60]!r}")
                elif first is None:
                    first = time.monotonic() - t0
        except Exception as exc:  # noqa: BLE001 — el spike informa y sigue
            failures += 1
            print(f"[{i + 1}] {type(exc).__name__}: {exc}")
    worker.stop()
    print(f"llamadas={repeat} fallos={failures}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    if args.record:
        print("fixture:", record_raw(args.model))
    asyncio.run(run(args.model, args.repeat))


if __name__ == "__main__":
    main()
