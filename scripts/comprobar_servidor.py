"""¿Hay que arrancar Desemppa? Lo usan INICIAR_DESEMPPA.bat y start.ps1 antes de lanzar uvicorn.

Códigos de salida:
  0  el puerto está libre (o se ha cerrado un servidor antiguo de este proyecto): arranca uno nuevo.
  2  ya hay un servidor de Desemppa con el código actual: solo hay que abrir el navegador.
  3  el puerto lo usa otro programa: no se toca nada.

Solo se cierra un proceso si su línea de comandos contiene la carpeta de este proyecto y `api.main:app`.

Uso:
    uv run python scripts/comprobar_servidor.py [--puerto 8000]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):  # consola de Windows con codificación antigua
    sys.stdout.reconfigure(errors="replace")

from api.version_codigo import huella_codigo  # noqa: E402


def _version_remota(puerto: int) -> dict[str, object] | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/api/version", timeout=3) as r:
            datos = json.loads(r.read().decode("utf-8"))
            return datos if isinstance(datos, dict) else None
    except (OSError, ValueError):
        return None


def _pids_escuchando(puerto: int) -> set[int]:
    salida = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, check=False).stdout
    pids = set()
    for linea in salida.splitlines():
        partes = linea.split()
        if len(partes) >= 5 and partes[3] == "LISTENING" and partes[1].endswith(f":{puerto}"):
            pids.add(int(partes[4]))
    return pids


def _procesos() -> dict[int, tuple[int, str]]:
    """{pid: (pid_padre, línea de comandos)} vía CIM de Windows."""
    cmd = (
        'Get-CimInstance Win32_Process | ForEach-Object { "$($_.ProcessId)`t$($_.ParentProcessId)`t$($_.CommandLine)" }'
    )
    salida = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, check=False
    ).stdout
    out: dict[int, tuple[int, str]] = {}
    for linea in salida.splitlines():
        partes = linea.split("\t", 2)
        if len(partes) == 3 and partes[0].isdigit() and partes[1].isdigit():
            out[int(partes[0])] = (int(partes[1]), partes[2])
    return out


def _es_nuestro(cmdline: str) -> bool:
    texto = cmdline.lower().replace("/", "\\")
    return str(ROOT).lower() in texto and "api.main:app" in texto


def _raiz_del_arbol(pid: int, procesos: dict[int, tuple[int, str]]) -> int:
    """El ancestro más alto que también es un servidor de este proyecto (uv lanza un python que lanza otro)."""
    actual = pid
    while True:
        padre = procesos.get(actual, (0, ""))[0]
        if padre and padre in procesos and _es_nuestro(procesos[padre][1]):
            actual = padre
            continue
        return actual


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--puerto", type=int, default=8000)
    args = parser.parse_args(argv)

    pids = _pids_escuchando(args.puerto)
    if not pids:
        return 0
    remota = _version_remota(args.puerto)
    actual = huella_codigo()
    if remota is not None and remota.get("servidor") == actual:
        print(f"Desemppa ya está en marcha con el código actual en http://127.0.0.1:{args.puerto}")
        return 2
    procesos = _procesos()
    nuestros = [p for p in pids if p in procesos and _es_nuestro(procesos[p][1])]
    if not nuestros:
        print(f"El puerto {args.puerto} lo está usando otro programa (PID {', '.join(map(str, sorted(pids)))}).")
        print("Ciérralo o libera el puerto y vuelve a abrir Desemppa.")
        return 3
    for pid in {_raiz_del_arbol(p, procesos) for p in nuestros}:
        print(f"Cerrando un servidor de Desemppa anterior a esta versión (PID {pid})...")
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
    for _ in range(20):
        if not _pids_escuchando(args.puerto):
            return 0
        time.sleep(0.5)
    print(f"No se ha podido liberar el puerto {args.puerto}.")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
