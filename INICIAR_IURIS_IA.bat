@echo off
rem Lanzador de Iuris-IA (doble clic). Arranca el backend en http://127.0.0.1:8000 y abre el navegador.
cd /d "%~dp0"
title Iuris-IA

rem 1) No arrancar dos servidores a la vez: si el puerto 8000 ya está en uso, solo se abre el navegador.
netstat -ano | findstr /R /C:"127.0.0.1:8000 .*LISTENING" >nul
if %errorlevel%==0 (
    echo Iuris-IA ya se esta ejecutando en http://127.0.0.1:8000
    start "" "http://127.0.0.1:8000"
    exit /b 0
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

start "" "http://127.0.0.1:8000"
rem Sin --reload: en Windows el recargador puede forzar un event loop sin soporte de subprocesos.
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000
