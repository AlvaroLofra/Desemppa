"""Copia los datos de la app (consultas, consumo, caché del BOE…) a la nueva ubicación única `data/local/`.

Antes los datos vivían en %LOCALAPPDATA%\\iuris, y Windows redirige esa carpeta para los procesos lanzados
desde la app de Claude (…\\Packages\\Claude_…\\LocalCache\\Local\\iuris): había dos bases de datos distintas.

  uv run python scripts/migrar_datos.py            # muestra los orígenes encontrados y copia el más reciente
  uv run python scripts/migrar_datos.py --origen <carpeta>
  uv run python scripts/migrar_datos.py --listar   # solo muestra

Ejecútalo desde una terminal normal (no desde la app de Claude) para ver la carpeta real. No borra nada.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINO = ROOT / "data" / "local"


def candidatos() -> list[Path]:
    rutas = []
    if os.environ.get("LOCALAPPDATA"):
        rutas.append(Path(os.environ["LOCALAPPDATA"]) / "iuris")
    paquetes = Path.home() / "AppData" / "Local" / "Packages"
    if paquetes.exists():
        rutas += sorted(paquetes.glob("Claude_*/LocalCache/Local/iuris"))
    return [r for r in rutas if (r / "local_cache.db").exists()]


def resumen(carpeta: Path) -> str:
    db = carpeta / "local_cache.db"
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        n, ultima = con.execute("SELECT count(*), max(creado_en) FROM sesiones_consultas").fetchone()
        con.close()
    except sqlite3.Error as exc:
        return f"(no legible: {exc})"
    mtime = max(p.stat().st_mtime for p in carpeta.glob("local_cache.db*"))
    return f"{n} consultas, última {ultima}, modificada {datetime.fromtimestamp(mtime):%Y-%m-%d %H:%M}"


def copiar(origen: Path, destino: Path = DESTINO) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    db_dest = destino / "local_cache.db"
    if db_dest.exists():
        respaldo = db_dest.with_suffix(".db.antes_de_migrar")
        shutil.copy2(db_dest, respaldo)
        print(f"Base de datos existente respaldada en {respaldo}")
        for sufijo in ("", "-wal", "-shm"):
            Path(f"{db_dest}{sufijo}").unlink(missing_ok=True)
    # API de backup de SQLite: copia coherente aunque haya WAL pendiente.
    src = sqlite3.connect(f"file:{origen / 'local_cache.db'}?mode=ro", uri=True)
    dst = sqlite3.connect(db_dest)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    if (origen / "lancedb_store").exists():
        shutil.copytree(origen / "lancedb_store", destino / "lancedb_store", dirs_exist_ok=True)
    print(f"Copiado {origen} -> {destino}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--origen", type=Path)
    ap.add_argument("--listar", action="store_true")
    args = ap.parse_args()
    encontrados = candidatos()
    for c in encontrados:
        print(f"- {c}\n    {resumen(c)}")
    if args.listar:
        return 0
    origen = args.origen or (
        max(encontrados, key=lambda c: (c / "local_cache.db").stat().st_mtime) if encontrados else None
    )
    if origen is None:
        print("No se han encontrado datos antiguos: nada que migrar.")
        return 0
    copiar(origen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
