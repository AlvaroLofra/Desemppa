"""Congela como regresión los casos de una ejecución de la batería que superan todas las comprobaciones.

Copia `caso`, `hoja` y `resultado` de cada caso perfecto a `tests/golden/bateria/Vxx.json`. El test
`tests/golden/test_bateria.py` vuelve a evaluarlos sin LLM ni red: si un cambio en el evaluador, el cortafuegos o el
motor de plazos rompe un caso que antes pasaba, el test falla.

Uso:
    uv run python benchmark/congelar.py benchmark/expedientes/20261025_1900_eco
    uv run python benchmark/congelar.py <dir> --destino otra/carpeta
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINO = ROOT / "tests" / "golden" / "bateria"


def congelar(ejecucion: Path, destino: Path = DESTINO) -> list[str]:
    """Devuelve los ids congelados."""
    destino.mkdir(parents=True, exist_ok=True)
    congelados = []
    for ev_f in sorted(ejecucion.glob("V*/evaluacion.json")):
        ev = json.loads(ev_f.read_text(encoding="utf-8"))
        if ev["aprobadas"] != ev["total"]:
            continue
        exp = json.loads((ev_f.parent / "expediente.json").read_text(encoding="utf-8"))
        res = dict(exp["resultado"])
        res.pop("debate", None)  # no lo usa el evaluador y es lo más voluminoso
        datos = {"caso": exp["caso"], "hoja": exp["hoja"], "resultado": res, "origen": ejecucion.name}
        (destino / f"{ev['id']}.json").write_text(
            json.dumps(datos, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
        )
        congelados.append(ev["id"])
    return congelados


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ejecucion", type=Path)
    ap.add_argument("--destino", type=Path, default=DESTINO)
    args = ap.parse_args(argv)
    if not args.ejecucion.is_dir():
        print(f"No existe la carpeta {args.ejecucion}", file=sys.stderr)
        return 1
    ids = congelar(args.ejecucion, args.destino)
    print(f"{len(ids)} casos congelados en {args.destino}: {', '.join(ids) or '—'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
