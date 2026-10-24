# Arranca Desemppa en local: compila la interfaz si hace falta, lanza el backend y abre el navegador cuando /api/version responde 200.
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\start.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

# Servidor ya en marcha: con el código actual solo se abre el navegador; si es de una versión anterior se sustituye.
uv run python scripts\comprobar_servidor.py --puerto 8000
if ($LASTEXITCODE -eq 2) { Start-Process "http://127.0.0.1:8000"; exit 0 }
if ($LASTEXITCODE -eq 3) { exit 1 }

if (-not (Test-Path "web\dist\index.html")) {
    Write-Host "Compilando la interfaz web (solo la primera vez)..."
    Push-Location web
    npm install --no-audit --no-fund
    npm run build
    Pop-Location
}

Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-Command",
    "for (`$i=0; `$i -lt 60; `$i++) { try { `$r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/version' -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop; if (`$r.StatusCode -eq 200) { Start-Process 'http://127.0.0.1:8000'; break } } catch {}; Start-Sleep -Milliseconds 300 }"
)

# Sin --reload: en Windows el recargador puede forzar un event loop sin soporte de subprocesos.
# Escucha en todas las interfaces; lo que no venga de este equipo se rechaza hasta activar la red local en Ajustes.
$env:IURIS_ESCUCHA_RED = "1"
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000
