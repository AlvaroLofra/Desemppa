"""Comprueba contra el BOE cada plazo de config/plazos.yaml (texto vigente hoy, sin notas editoriales).

Cada plazo (y su variante foral) debe llevar `fuentes` con citas literales del artículo vigente (verify_quote) y su
duración tiene que aparecer en una de ellas con la unidad que usa el cómputo («veinte días», «un mes», «al año»): el
motor de plazos no puede calcular una cifra que la ley no diga.

    uv run python scripts/verificar_plazos.py
"""

from __future__ import annotations

import asyncio
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Protocol

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from config.settings import get_settings  # noqa: E402
from connectors.boe_client import _NUM_PALABRA, BOEClient, BOERepository  # noqa: E402
from connectors.boe_models import Bloque  # noqa: E402
from core.calendar_engine import PLAZOS_PATH  # noqa: E402
from core.materias import id_norma  # noqa: E402
from core.normalize import fold  # noqa: E402
from core.temporal_sync import select_version  # noqa: E402
from core.validators import verify_quote  # noqa: E402
from storage.database import open_database  # noqa: E402

_UNIDAD = {"anios_fecha_a_fecha": "anos?", "meses_fecha_a_fecha": "mes(?:es)?"}


class _Articulos(Protocol):
    async def get_articulo(self, id_norma: str, articulo: str) -> Bloque: ...


def duracion_en_citas(duracion: int, computo: str, citas: list[str]) -> bool:
    """True si alguna cita dice la duración con su unidad: «veinte días hábiles», «dos meses», «al año»."""
    palabras = [w for w, n in _NUM_PALABRA.items() if n == str(duracion)] + [str(duracion)]
    if duracion == 1:
        palabras += ["un", "al"]
    unidad = _UNIDAD.get(computo, "dias?")
    patron = re.compile(rf"\b(?:{'|'.join(map(re.escape, palabras))})\s+(?:\w+\s+)?{unidad}\b")
    return any(patron.search(fold(c).lower()) for c in citas)


def _variantes(plazos: dict[str, Any]) -> list[tuple[str, int, str, list[dict[str, str]]]]:
    """(nombre, duración, cómputo, fuentes) de cada plazo y de cada variante foral."""
    out = []
    for pid, p in plazos.items():
        out.append((pid, int(p["duracion"]), p["computo"], p.get("fuentes") or []))
        for terr, f in (p.get("foral") or {}).items():
            out.append((f"{pid} ({terr})", int(f.get("duracion", p["duracion"])), p["computo"], f.get("fuentes") or []))
    return out


async def verificar(boe: _Articulos, plazos: dict[str, Any] | None = None, hoy: date | None = None) -> list[str]:
    """Devuelve la lista de fallos (vacía si cada plazo está respaldado por su cita en el texto vigente)."""
    if plazos is None:
        plazos = yaml.safe_load(PLAZOS_PATH.read_text(encoding="utf-8"))["plazos"]
    textos: dict[tuple[str, str], str] = {}
    fallos = []
    for nombre, duracion, computo, fuentes in _variantes(plazos):
        if not fuentes:
            fallos.append(f"{nombre}: sin fuentes literales")
            continue
        for f in fuentes:
            clave = (f["norma"], str(f["articulo"]))
            if clave not in textos:
                bloque = await boe.get_articulo(id_norma(clave[0]), clave[1])
                version = select_version(bloque, hoy or date.today()).version
                textos[clave] = version.texto if version else ""
            chk = verify_quote(f["cita"], textos[clave])
            if not chk.ok:
                fallos.append(
                    f"{nombre}: «{f['cita'][:80]}…» no está en el art. {clave[1]} {clave[0]} ({chk.score:.0f} %)"
                )
        if not duracion_en_citas(duracion, computo, [f["cita"] for f in fuentes]):
            fallos.append(f"{nombre}: ninguna cita dice la duración ({duracion}, {computo})")
    return fallos


async def main() -> int:
    settings = get_settings()
    assert settings.sqlite_path is not None
    con = open_database(settings.sqlite_path)
    plazos = yaml.safe_load(PLAZOS_PATH.read_text(encoding="utf-8"))["plazos"]
    try:
        fallos = await verificar(BOERepository(con, BOEClient()), plazos)
    finally:
        con.close()
    for f in fallos:
        print(f"✗ {f}")
    total = len(_variantes(plazos))
    con_fallo = len({f.split(":")[0] for f in fallos})
    print(f"{'✓' if not fallos else '✗'} {total - con_fallo} plazos verificados de {total} contra el BOE vigente")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
