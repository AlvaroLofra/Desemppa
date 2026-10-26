"""Informe comparativo entre dos ejecuciones de la batería (p. ej. la semana pasada frente a hoy).

Por caso: estado, comprobaciones superadas y tiempo en cada ejecución, marcando lo que empeora. Solo datos medidos.

Uso:
    uv run python benchmark/comparar_ejecuciones.py benchmark/expedientes/A benchmark/expedientes/B
    uv run python benchmark/comparar_ejecuciones.py A B --salida comparacion.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _cargar(d: Path) -> dict[str, dict[str, Any]]:
    out = {}
    for ev_f in sorted(d.glob("V*/evaluacion.json")):
        ev = json.loads(ev_f.read_text(encoding="utf-8"))
        exp_f = ev_f.parent / "expediente.json"
        res = json.loads(exp_f.read_text(encoding="utf-8"))["resultado"] if exp_f.exists() else {}
        out[ev["id"]] = {
            "estado": res.get("estado"),
            "duracion_s": res.get("duracion_s"),
            "aprobadas": ev["aprobadas"],
            "total": ev["total"],
            "fallos": [k for k, c in ev["checks"].items() if not c["ok"]],
        }
    return out


def comparar(a: Path, b: Path) -> str:
    da, db = _cargar(a), _cargar(b)
    L = [
        f"# Comparación de la batería: {a.name} → {b.name}",
        "",
        "| Caso | Antes | Después | Tiempo | Cambio |",
        "|---|---|---|---|---|",
    ]
    peor = mejor = 0
    for cid in sorted(set(da) | set(db)):
        x, y = da.get(cid), db.get(cid)
        antes = f"{x['aprobadas']}/{x['total']} {x['estado']}" if x else "—"
        despues = f"{y['aprobadas']}/{y['total']} {y['estado']}" if y else "—"
        tiempo = f"{x['duracion_s'] if x else '—'} → {y['duracion_s'] if y else '—'} s"
        cambio = ""
        if x and y:
            if y["aprobadas"] < x["aprobadas"]:
                peor += 1
                cambio = "⚠ empeora: " + ", ".join(sorted(set(y["fallos"]) - set(x["fallos"])))
            elif y["aprobadas"] > x["aprobadas"]:
                mejor += 1
                cambio = "mejora"
        L.append(f"| {cid} | {antes} | {despues} | {tiempo} | {cambio} |")

    def perfectos(d: dict[str, dict[str, Any]]) -> int:
        return sum(1 for v in d.values() if v["aprobadas"] == v["total"])

    L += [
        "",
        f"- Casos perfectos: **{perfectos(da)}/{len(da)} → {perfectos(db)}/{len(db)}**",
        f"- Empeoran: **{peor}** · Mejoran: **{mejor}**",
    ]
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("antes", type=Path)
    ap.add_argument("despues", type=Path)
    ap.add_argument("--salida", type=Path)
    args = ap.parse_args(argv)
    for d in (args.antes, args.despues):
        if not d.is_dir():
            print(f"No existe la carpeta {d}", file=sys.stderr)
            return 1
    informe = comparar(args.antes, args.despues)
    if args.salida:
        args.salida.write_text(informe, encoding="utf-8")
    sys.stdout.reconfigure(errors="replace")  # type: ignore[union-attr]
    print(informe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
