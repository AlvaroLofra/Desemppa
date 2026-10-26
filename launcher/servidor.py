"""Lógica del lanzador de escritorio, sin interfaz gráfica (para poder probarla): preparar, arrancar, esperar y
parar el servidor de Desemppa. La usa `launcher/desemppa.pyw`."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUERTO = int(os.environ.get("DESEMPPA_PUERTO", "8000"))  # otro puerto solo para pruebas
URL = f"http://127.0.0.1:{PUERTO}"
LOG = ROOT / "data" / "local" / "servidor.log"
# Sin ventana de consola para los procesos hijos (solo existe en Windows).
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

Progreso = Callable[[str], None]


def python_consola() -> str:
    """El python.exe del entorno (no pythonw): uvicorn necesita una salida estándar a la que escribir."""
    exe = Path(sys.executable)
    consola = exe.with_name("python.exe")
    return str(consola if exe.name.lower() == "pythonw.exe" and consola.exists() else exe)


def comando_servidor(python: str | None = None, puerto: int = PUERTO) -> list[str]:
    # Sin --reload: en Windows el recargador puede forzar un event loop sin soporte de subprocesos (CLAUDE.md).
    return [python or python_consola(), "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", str(puerto)]


def entorno() -> dict[str, str]:
    # Escucha en la red local, pero api/red_local.py rechaza lo que no venga de este equipo salvo que se active.
    return {**os.environ, "IURIS_ESCUCHA_RED": "1", "PYTHONIOENCODING": "utf-8"}


def comprobar(puerto: int = PUERTO) -> int:
    """0 = arrancar uno nuevo · 2 = ya hay uno con el código actual · 3 = el puerto lo usa otro programa.
    Se ejecuta como proceso aparte sin ventana: lanza netstat y PowerShell, que abrirían una consola cada uno."""
    r = subprocess.run(
        [python_consola(), "scripts/comprobar_servidor.py", "--puerto", str(puerto)],
        cwd=ROOT,
        capture_output=True,
        check=False,
        creationflags=SIN_VENTANA,
    )
    return r.returncode


def preparar(progreso: Progreso) -> None:
    """Primera vez: migra los datos antiguos y compila la interfaz si falta (como INICIAR_DESEMPPA.bat)."""
    if not (ROOT / "data" / "local" / "local_cache.db").exists():
        progreso("Migrando tus datos anteriores…")
        subprocess.run([python_consola(), "scripts/migrar_datos.py"], cwd=ROOT, check=False, creationflags=SIN_VENTANA)
    if not (ROOT / "web" / "dist" / "index.html").exists():
        npm = shutil.which("npm")
        if npm is None:
            raise RuntimeError("Falta Node.js para compilar la interfaz. Ejecuta INSTALAR_DESEMPPA.bat.")
        progreso("Compilando la interfaz (solo la primera vez, puede tardar un minuto)…")
        for args in (["install", "--no-audit", "--no-fund"], ["run", "build"]):
            subprocess.run([npm, *args], cwd=ROOT / "web", check=True, creationflags=SIN_VENTANA)


def arrancar(puerto: int = PUERTO) -> subprocess.Popen[bytes]:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log = LOG.open("ab")
    return subprocess.Popen(
        comando_servidor(puerto=puerto),
        cwd=ROOT,
        env=entorno(),
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=SIN_VENTANA,
    )


def responde(url: str = URL, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/api/version", timeout=timeout) as r:
            return bool(r.status == 200)
    except OSError:
        return False


def esperar(url: str = URL, segundos: float = 60, proceso: subprocess.Popen[bytes] | None = None) -> bool:
    """Espera a que el servidor conteste 200 en /api/version (o a que el proceso muera)."""
    fin = time.monotonic() + segundos
    while time.monotonic() < fin:
        if responde(url):
            return True
        if proceso is not None and proceso.poll() is not None:
            return False
        time.sleep(0.3)
    return False


def detener(proceso: subprocess.Popen[bytes] | None) -> None:
    """Para el servidor que arrancó este lanzador (y sus hijos). Nunca toca uno que ya estuviera en marcha."""
    if proceso is None or proceso.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(proceso.pid), "/T", "/F"],
            capture_output=True,
            check=False,
            creationflags=SIN_VENTANA,
        )
    else:
        proceso.terminate()
    try:
        proceso.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proceso.kill()
