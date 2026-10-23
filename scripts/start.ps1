# Arranca Iuris-IA en local: compila la interfaz si hace falta, abre el navegador y lanza el backend.
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\start.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path "web\dist\index.html")) {
    Write-Host "Compilando la interfaz web (solo la primera vez)..."
    Push-Location web
    npm install --no-audit --no-fund
    npm run build
    Pop-Location
}

Start-Process "http://127.0.0.1:8000"
# Sin --reload: en Windows el recargador puede forzar un event loop sin soporte de subprocesos.
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000
