"""Huella del código del servidor: permite saber si el servidor en marcha es anterior al código en disco.

Se calcula sobre los ficheros que cambian el comportamiento del backend (Python y configuración del proyecto, sin los
ficheros personales `user_*.toml`). El lanzador la compara con la que anuncia `/api/version` y sustituye un servidor
antiguo en lugar de limitarse a abrir el navegador (causa del 404 en bucle de /api/red, 25-10-2026).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CARPETAS = ("api", "core", "connectors", "storage", "config")
EXTENSIONES = {".py", ".toml", ".yaml", ".yml", ".json", ".sql", ".md"}


def huella_codigo(raiz: Path = RAIZ) -> str:
    h = hashlib.sha256()
    for carpeta in CARPETAS:
        base = raiz / carpeta
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*")):
            if not f.is_file() or f.suffix not in EXTENSIONES or "__pycache__" in f.parts or f.name.startswith("user_"):
                continue
            h.update(f.relative_to(raiz).as_posix().encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:16]
