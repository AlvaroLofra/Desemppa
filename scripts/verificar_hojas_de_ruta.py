"""Comprueba contra el BOE cada cita de config/hojas_de_ruta.yaml (texto vigente hoy, sin notas editoriales).

Una cita que no aparezca literalmente (verify_quote) en el artículo vigente hace fallar el script: la hoja de ruta
no puede afirmar nada que la ley no diga.

    uv run python scripts/verificar_hojas_de_ruta.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from config.settings import get_settings  # noqa: E402
from connectors.boe_client import BOEClient, BOERepository  # noqa: E402
from core.hoja_de_ruta import cargar  # noqa: E402
from core.materias import id_norma  # noqa: E402
from core.temporal_sync import select_version  # noqa: E402
from core.validators import verify_quote  # noqa: E402
from storage.database import open_database  # noqa: E402


async def verificar(boe: BOERepository, hoy: date | None = None) -> list[str]:
    """Devuelve la lista de fallos (vacía si todas las citas están en el texto vigente)."""
    # Cada cita se comprueba contra la redacción vigente hoy y, si el paso depende de una redacción concreta
    # (`vigente_desde`), también contra la vigente en esa fecha.
    citas = {
        (b.norma, b.articulo, b.cita, paso.vigente_desde)
        for pasos in cargar().values()
        for paso in pasos
        for b in paso.base
    }
    textos: dict[tuple[str, str, date], str] = {}
    fallos = []
    for norma, articulo, cita, desde in sorted(citas, key=lambda c: (c[0], c[1], c[2], str(c[3]))):
        for fecha in {hoy or date.today(), *([desde] if desde else [])}:
            if (norma, articulo, fecha) not in textos:
                bloque = await boe.get_articulo(id_norma(norma), articulo)
                version = select_version(bloque, fecha).version
                textos[(norma, articulo, fecha)] = version.texto if version else ""
            chk = verify_quote(cita, textos[(norma, articulo, fecha)])
            if not chk.ok:
                break
        if not chk.ok:
            fallos.append(
                f"{norma} {articulo}: «{cita[:80]}…» no está en el texto vigente el {fecha} ({chk.score:.0f} %)"
            )
    return fallos


async def main() -> int:
    settings = get_settings()
    assert settings.sqlite_path is not None
    con = open_database(settings.sqlite_path)
    try:
        fallos = await verificar(BOERepository(con, BOEClient()))
    finally:
        con.close()
    for f in fallos:
        print(f"✗ {f}")
    total = sum(len(p.base) for pasos in cargar().values() for p in pasos)
    print(f"{'✓' if not fallos else '✗'} {total - len(fallos)} citas verificadas de {total} en las hojas de ruta")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
