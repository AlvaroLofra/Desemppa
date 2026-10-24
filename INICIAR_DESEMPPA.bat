@echo off
rem Lanzador de Desemppa (doble clic). Arranca el servidor y abre el navegador cuando este listo.
rem Escucha en todas las interfaces para poder compartir la app en la red local, pero las peticiones que no vienen
rem de este ordenador se rechazan hasta que actives «Compartir en la red local» en Ajustes.
cd /d "%~dp0"
title Desemppa

rem 1) Si ya hay un Desemppa con el codigo actual, solo se abre el navegador. Si el que hay es de una version
rem    anterior, se cierra y se arranca el nuevo. Si el puerto lo usa otro programa, no se toca.
uv run python scripts\comprobar_servidor.py --puerto 8000
if %errorlevel%==2 (
    start "" "http://127.0.0.1:8000"
    exit /b 0
)
if %errorlevel%==3 (
    pause
    exit /b 1
)

rem 2) Primera vez con la nueva carpeta de datos: traer las consultas de %%LOCALAPPDATA%%\iuris.
if not exist "data\local\local_cache.db" (
    echo Migrando datos anteriores a data\local ...
    uv run python scripts\migrar_datos.py
)

rem 3) Compilar la interfaz si falta.
if not exist "web\dist\index.html" (
    echo Compilando la interfaz web ^(solo la primera vez^)...
    pushd web
    call npm install --no-audit --no-fund
    call npm run build
    popd
)

rem 4) Abrir el navegador SOLO cuando el servidor responda 200 en /api/version.
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for ($i=0; $i -lt 60; $i++) { try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/version' -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop; if ($r.StatusCode -eq 200) { Start-Process 'http://127.0.0.1:8000'; break } } catch {}; Start-Sleep -Milliseconds 300 }"

rem Sin --reload: en Windows el recargador puede forzar un event loop sin soporte de subprocesos.
set IURIS_ESCUCHA_RED=1
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000
