"""Spike: ¿por qué Gemini Flash vía `agy` devuelve respuestas vacías en el rol Magistrado y cómo evitarlo?

Causa observada en data/local/logs/iuris.log: el modelo intenta usar una herramienta («command») que el modo no
interactivo deniega, y la respuesta sale vacía. Se prueba el mismo prompt real del Magistrado (reconstruido a partir
de una consulta ya analizada) con varias variantes de argumentos y se cuenta cuántas respuestas son válidas.
NUNCA se usa `--dangerously-skip-permissions` (lo prohíbe config/settings.py).

    uv run python scripts/spike_agy_vacias.py --n 5 --variantes base plan
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from api.main import build_services  # noqa: E402
from core.errors import ProviderError  # noqa: E402
from core.llm_types import LLMRequest, LLMResult  # noqa: E402
from core.orchestrator import Orchestrator, _prompt_rol  # noqa: E402
from core.schemas import AlegatoSchema, DossierIngestaSchema  # noqa: E402

NO_HERRAMIENTAS = (
    "IMPORTANTE: no uses herramientas, comandos, ficheros ni búsquedas. Todo lo que necesitas está en este mensaje. "
    "Responde directamente con el JSON pedido.\n\n"
)
VARIANTES: dict[str, tuple[list[str], bool]] = {
    "base": ([], False),
    "plan": (["--mode", "plan"], False),
    "instruccion": ([], True),
    "plan+instruccion": (["--mode", "plan"], True),
}


def prompt_magistrado(services, consulta_id: str | None) -> tuple[str, str]:  # type: ignore[no-untyped-def]
    store = services.pipeline.store
    ids = (
        [consulta_id] if consulta_id else [c["consulta_id"] for c in store.listar(200) if c["estado"] == "CERTIFICADA"]
    )
    for cid in ids:
        c = store.get(cid)
        if c.dossier and c.debate and c.debate.get("defensa"):
            o = Orchestrator(services.pipeline)
            dossier = DossierIngestaSchema.model_validate(c.dossier)
            pregunta = c.texto_seudonimizado + "".join(
                f"\n- {a.get('pregunta', '')}: {a.get('respuesta', '')}" for a in c.aclaraciones
            )
            base = f"CONSULTA LITERAL DEL CIUDADANO (seudonimizada):\n{pregunta}\n\n" + o._dossier_texto(dossier)  # noqa: SLF001
            defensa = AlegatoSchema.model_validate(c.debate["defensa"])
            contraparte = AlegatoSchema.model_validate(c.debate["contraparte"])
            prompt = (
                base + f"\n\nALEGATO DE LA DEFENSA:\n{defensa.model_dump_json()}\n\n"
                f"ALEGATO DE LA CONTRAPARTE:\n{contraparte.model_dump_json()}"
            )
            return cid, prompt
    raise SystemExit("no hay ninguna consulta certificada con debate para reconstruir el prompt")


async def probar(n: int, variantes: list[str], consulta_id: str | None, effort: str) -> dict[str, dict[str, object]]:
    services = build_services()
    cid, prompt = prompt_magistrado(services, consulta_id)
    sistema = _prompt_rol("magistrado")
    alias = "agy_gemini_flash"
    spec = services.catalog.models[alias]
    adapter: Any = services.pipeline.router.providers[spec.provider]  # type: ignore[union-attr]
    args_originales = list(adapter.spec.args)
    print(f"Consulta {cid} · prompt de {len(sistema) + len(prompt)} caracteres · {alias} {effort}", flush=True)
    resultados: dict[str, dict[str, object]] = {}
    try:
        for v in variantes:
            extra, instruccion = VARIANTES[v]
            adapter.spec.args = [a for a in args_originales if a != "-p="] + extra + ["-p="]
            ok = vacias = otros = 0
            tiempos = []
            for i in range(n):
                t0 = time.monotonic()
                req = LLMRequest(
                    system=(NO_HERRAMIENTAS if instruccion else "") + sistema,
                    prompt=prompt,
                    effort=cast(Any, effort),
                    json_mode=True,
                )
                try:
                    texto = ""
                    async for item in adapter.stream(alias=alias, spec=spec, request=req):
                        if isinstance(item, LLMResult):
                            texto = item.text
                    if texto.strip():
                        ok += 1
                    else:
                        vacias += 1
                except ProviderError as exc:
                    if "vac" in str(exc).lower() or "no output" in str(exc).lower():
                        vacias += 1
                    else:
                        otros += 1
                    print(f"   {v} #{i + 1}: {type(exc).__name__}: {str(exc)[:160]}", flush=True)
                tiempos.append(round(time.monotonic() - t0))
                print(f"   {v} #{i + 1}: ok={ok} vacias={vacias} otros={otros} ({tiempos[-1]} s)", flush=True)
            resultados[v] = {"ok": ok, "vacias": vacias, "otros": otros, "segundos": tiempos}
    finally:
        adapter.spec.args = args_originales
        for p in services.pipeline.router.providers.values():  # type: ignore[union-attr]
            p.stop()  # type: ignore[union-attr]
    return resultados


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--variantes", nargs="+", default=["base", "plan"], choices=list(VARIANTES))
    ap.add_argument("--consulta")
    ap.add_argument("--effort", default="medium")
    a = ap.parse_args()
    res = asyncio.run(probar(a.n, a.variantes, a.consulta, a.effort))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
