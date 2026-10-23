"""Benchmark ciego (dossier Sprint 4). Ejecuta cada caso (original y permutado) por el pipeline real.

  uv run python -m benchmark.blind_judge [--modo eco] [--casos benchmark/cases] [--sin-permutar]

Necesita proveedores LLM operativos y consume cuota. Informe en benchmark/reports/<fecha>_<modo>.json/.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any

from benchmark.evaluator import Puntuacion, puntuar
from benchmark.permutations import permutar
from core.orchestrator import Orchestrator
from core.orchestrator import Services as PipelineServices
from core.state import Estado

HERE = Path(__file__).resolve().parent


def cargar_casos(directorio: Path) -> list[dict[str, Any]]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directorio.glob("*.json"))]


async def ejecutar_caso(pipeline: PipelineServices, caso: dict[str, Any], texto: str, modo: str) -> Puntuacion:
    store, bus = pipeline.store, pipeline.bus
    cid = store.create(texto, modo, municipio_ine=caso.get("municipio_ine"))
    orch = Orchestrator(pipeline)
    await orch.run(cid)
    if store.get(cid).estado == Estado.ESPERANDO_ACLARACION:
        respuestas = caso.get("aclaraciones") or [{"pregunta": "datos", "respuesta": "No consta."}]
        store.add_aclaraciones(cid, respuestas)
        await orch.run(cid)
    eventos = bus.history(cid)
    final = next((d for _, t, d in reversed(eventos) if t in ("final", "error")), {"estado": "ERROR"})
    guard = [d for _, t, d in eventos if t == "guardrail"]
    return puntuar(caso, final, guard)


async def ejecutar(
    pipeline: PipelineServices, casos: list[dict[str, Any]], modo: str, permutar_casos: bool
) -> list[dict[str, Any]]:
    filas: list[dict[str, Any]] = []
    for caso in casos:
        original = await ejecutar_caso(pipeline, caso, caso["consulta"], modo)
        filas.append({"variante": "original", **original.to_dict()})
        if permutar_casos:
            texto = permutar(caso["consulta"], seed=zlib.crc32(caso["id"].encode()) % 1000)
            perm = await ejecutar_caso(pipeline, caso, texto, modo)
            filas.append({"variante": "permutado", **perm.to_dict()})
    return filas


def resumir(filas: list[dict[str, Any]], modo: str) -> dict[str, Any]:
    return {
        "modo": modo,
        "ejecuciones": len(filas),
        "outcome_match": round(statistics.mean(f["outcome"] / 30 for f in filas), 3) if filas else 0,
        "total_medio": round(statistics.mean(f["total"] for f in filas), 1) if filas else 0,
        "certificadas": sum(f["estado"] == "CERTIFICADA" for f in filas),
    }


async def main(modo: str, directorio: Path, permutar_casos: bool) -> Path:
    from api.main import build_services

    services = build_services()
    assert services.pipeline is not None
    filas = await ejecutar(services.pipeline, cargar_casos(directorio), modo, permutar_casos)
    for adapter in services.providers.values():
        adapter.stop()
    out_dir = HERE / "reports"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{datetime.now():%Y%m%d_%H%M}_{modo}.json"
    resumen = resumir(filas, modo)
    out.write_text(json.dumps({"resumen": resumen, "filas": filas}, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["| caso | variante | estado | outcome | recall | alucinación | total |", "|---|---|---|---|---|---|---|"]
    md += [
        f"| {f['caso']} | {f['variante']} | {f['estado']} | {f['outcome']} | {f['recall']} | "
        f"{f['alucinacion']} | {f['total']} |"
        for f in filas
    ]
    out.with_suffix(".md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", default="eco")
    ap.add_argument("--casos", type=Path, default=HERE / "cases")
    ap.add_argument("--sin-permutar", action="store_true")
    a = ap.parse_args()
    asyncio.run(main(a.modo, a.casos, not a.sin_permutar))
