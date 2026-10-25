"""Copia de seguridad cifrada de data/local (consultas, biblioteca, claves, caché del BOE).

La copia se cifra con DPAPI de Windows (solo se puede abrir con este usuario en este equipo) y se guarda en
data/copias/. Se conservan las 10 más recientes. La restauración NO sobrescribe nada: extrae en una carpeta nueva y
explica cómo sustituir data/local con el servidor cerrado.

    uv run python scripts/copia_seguridad.py
    uv run python scripts/copia_seguridad.py --restaurar data/copias/desemppa_20261025_1300.bak
"""

from __future__ import annotations

import argparse
import base64
import io
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from core.secure_store import decrypt, encrypt  # noqa: E402

# Lo que no se copia: procesos en marcha y espacios de trabajo temporales de los CLI.
EXCLUIR = {"sandboxes", "antigravity_cli.lock"}
CONSERVAR = 10


def crear(datos: Path, destino: Path, ahora: datetime | None = None) -> Path:
    """Crea la copia cifrada y devuelve su ruta."""
    destino.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z, tempfile.TemporaryDirectory() as tmp:
        for f in sorted(datos.rglob("*")):
            rel = f.relative_to(datos)
            if f.is_dir() or rel.parts[0] in EXCLUIR or f.suffix in (".db-wal", ".db-shm"):
                continue
            if f.suffix == ".db":
                # Copia coherente aunque el servidor esté escribiendo (API de copia de SQLite).
                copia = Path(tmp) / f.name
                origen, dst = sqlite3.connect(f), sqlite3.connect(copia)
                try:
                    origen.backup(dst)
                finally:
                    origen.close()
                    dst.close()
                z.write(copia, rel.as_posix())
            else:
                z.write(f, rel.as_posix())
    nombre = destino / f"desemppa_{(ahora or datetime.now()):%Y%m%d_%H%M%S}.bak"
    nombre.write_bytes(encrypt(base64.b64encode(buf.getvalue()).decode("ascii")))
    for vieja in sorted(destino.glob("desemppa_*.bak"))[:-CONSERVAR]:
        vieja.unlink()
    return nombre


def restaurar(copia: Path, destino: Path) -> Path:
    """Descifra y extrae la copia en `destino` (que no debe existir)."""
    if destino.exists():
        raise FileExistsError(f"{destino} ya existe: elige otra carpeta")
    contenido = base64.b64decode(decrypt(copia.read_bytes()))
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        z.extractall(destino)
    return destino


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datos", type=Path, default=ROOT / "data" / "local")
    ap.add_argument("--destino", type=Path, default=ROOT / "data" / "copias")
    ap.add_argument("--restaurar", type=Path)
    a = ap.parse_args()
    if a.restaurar:
        carpeta = restaurar(a.restaurar, ROOT / "data" / f"restaurado_{datetime.now():%Y%m%d_%H%M%S}")
        print(f"✓ Copia extraída en {carpeta}")
        print("  Para usarla: cierra Desemppa, renombra data/local (por si acaso) y pon esta carpeta en su lugar.")
        return 0
    ruta = crear(a.datos, a.destino)
    print(f"✓ Copia cifrada creada: {ruta} ({ruta.stat().st_size / 1_048_576:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
