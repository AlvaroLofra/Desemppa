"""Comprueba contra la API del BOE que todos los artículos del catálogo de submaterias existen.

uv run python scripts/verificar_catalogo.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connectors.boe_client import BOEClient, BOEError, BOERepository  # noqa: E402
from core.materias import id_norma, submaterias  # noqa: E402
from storage.database import open_database  # noqa: E402


async def main() -> int:
    repo = BOERepository(open_database(":memory:"), BOEClient())
    fallos = 0
    vistos: set[tuple[str, str]] = set()
    for sub in submaterias().values():
        for ref in sub.normas:
            for art in ref.articulos:
                key = (ref.norma, art)
                if key in vistos:
                    continue
                vistos.add(key)
                try:
                    bloque = await repo.get_articulo(id_norma(ref.norma), art)
                    n = len(bloque.versiones)
                    print(f"OK    {ref.norma:10} art. {art:6} -> {bloque.id_bloque} ({n} versiones)")
                except BOEError as exc:
                    fallos += 1
                    print(f"FALLO {ref.norma:10} art. {art:6} ({sub.clave}): {exc}")
    print(f"\n{len(vistos)} artículos comprobados, {fallos} fallos")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
