"""Juez LLM de OTRA familia sobre los expedientes de una ejecución (benchmark/ejecutar.py).

Usa benchmark/instrucciones_verificador.md + expediente.md (autocontenido) con el modelo indicado vía la misma capa
de proveedores de la app (por defecto Claude Sonnet 5.5 en Antigravity, para juzgar respuestas de Gemini Flash).
Guarda juez.json por caso y añade al informe la comparación con la evaluación automática.

Uso:
    uv run python benchmark/juez.py benchmark/expedientes/20261025_1200_eco [--modelo agy_claude_sonnet]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from config.settings import get_settings, load_catalog  # noqa: E402
from core.gemini_client import GeminiClient  # noqa: E402
from core.llm_types import LLMRequest, LLMResult  # noqa: E402
from core.nli import extract_json  # noqa: E402
from core.providers.registry import build_registry  # noqa: E402

INSTRUCCIONES = (ROOT / "benchmark" / "instrucciones_verificador.md").read_text(encoding="utf-8")


async def juzgar(directorio: Path, modelo: str) -> int:
    catalogo, settings = load_catalog(), get_settings()
    spec = catalogo.models[modelo]
    proveedores = build_registry(
        catalogo, settings, gemini=GeminiClient(None), exe_overrides={"claude_cli": settings.claude_exe}
    )
    adapter = proveedores[spec.provider]
    filas: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    try:
        for exp in sorted(directorio.glob("V*/expediente.md")):
            caso_id = exp.parent.name
            print(f"[{caso_id}] juzgando con {modelo} ...", flush=True)
            peticion = LLMRequest(
                system=INSTRUCCIONES, prompt=exp.read_text(encoding="utf-8"), effort="medium", json_mode=True
            )
            texto = ""
            try:
                async for item in adapter.stream(alias=modelo, spec=spec, request=peticion):
                    if isinstance(item, LLMResult):
                        texto = item.text
                veredicto = extract_json(texto)
            except Exception as exc:  # un caso que falla no detiene el resto
                veredicto = {"error": f"{type(exc).__name__}: {exc}"}
            (exp.parent / "juez.json").write_text(json.dumps(veredicto, ensure_ascii=False, indent=2), encoding="utf-8")
            ev = json.loads((exp.parent / "evaluacion.json").read_text(encoding="utf-8"))
            filas.append((caso_id, veredicto, ev))
            print(
                f"    nota {veredicto.get('nota')} · respuesta {'OK' if veredicto.get('respuesta_coincide') else 'NO'}",
                flush=True,
            )
    finally:
        for p in proveedores.values():
            p.stop()
    L = [
        "",
        f"## Juez LLM ({modelo})",
        "",
        "| Caso | Nota | Respuesta | Puntos clave cubiertos | Sin respaldo | Auto | Desacuerdo |",
        "|---|---|---|---|---|---|---|",
    ]
    for caso_id, v, ev in filas:
        if "error" in v:
            L.append(f"| {caso_id} | — | — | — | — | {ev['aprobadas']}/{ev['total']} | error del juez |")
            continue
        puntos = v.get("puntos_clave", [])
        cubiertos = sum(1 for p in puntos if p.get("cubierto"))
        sin_respaldo = len(v.get("afirmaciones_sin_respaldo", []))
        auto_ok = ev["aprobadas"] == ev["total"]
        juez_ok = bool(v.get("respuesta_coincide")) and sin_respaldo == 0 and cubiertos == len(puntos)
        L.append(
            f"| {caso_id} | {v.get('nota')} | {'sí' if v.get('respuesta_coincide') else 'no'} | "
            f"{cubiertos}/{len(puntos)} | "
            f"{sin_respaldo} | {ev['aprobadas']}/{ev['total']} | {'revisar' if auto_ok != juez_ok else '—'} |"
        )
    with (directorio / "informe.md").open("a", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("directorio", type=Path)
    ap.add_argument("--modelo", default="agy_claude_sonnet")
    a = ap.parse_args()
    return asyncio.run(juzgar(a.directorio, a.modelo))


if __name__ == "__main__":
    raise SystemExit(main())
