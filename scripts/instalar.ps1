# Instala Desemppa en este equipo: dependencias, interfaz compilada, icono y accesos directos.
# Lo llama INSTALAR_DESEMPPA.bat (doble clic). Se puede repetir sin problema (p. ej. tras actualizar el código).
#
#   powershell -ExecutionPolicy Bypass -File scripts\instalar.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\instalar.ps1 -SinAccesos   # solo dependencias y compilación
param([switch]$SinAccesos)
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

function Paso($texto) { Write-Host "`n==> $texto" -ForegroundColor Cyan }
function Falta($programa, $winget) {
    Write-Host "No encuentro $programa." -ForegroundColor Yellow
    Write-Host "Instálalo con:  winget install $winget   y vuelve a ejecutar INSTALAR_DESEMPPA.bat" -ForegroundColor Yellow
    exit 1
}

Paso "Comprobando requisitos"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { Falta "uv (gestor de Python)" "astral-sh.uv" }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Falta "Node.js" "OpenJS.NodeJS.LTS" }
Write-Host "uv y Node.js disponibles."

Paso "Instalando las dependencias de Python (uv sync)"
uv sync
if ($LASTEXITCODE -ne 0) { throw "uv sync ha fallado" }

Paso "Compilando la interfaz"
Push-Location web
npm ci --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { npm install --no-audit --no-fund }
npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "la compilación de la interfaz ha fallado" }
Pop-Location

if (-not (Test-Path "data\local\local_cache.db")) {
    Paso "Migrando datos anteriores"
    uv run python scripts\migrar_datos.py
}

Paso "Generando el icono"
uv run python scripts\generar_icono.py

if (-not $SinAccesos) {
    Paso "Creando los accesos directos"
    $pythonw = Join-Path $raiz ".venv\Scripts\pythonw.exe"
    $shell = New-Object -ComObject WScript.Shell
    $destinos = @(
        [Environment]::GetFolderPath("Desktop"),
        (Join-Path ([Environment]::GetFolderPath("Programs")) "")
    )
    foreach ($carpeta in $destinos) {
        $acceso = $shell.CreateShortcut((Join-Path $carpeta "Desemppa.lnk"))
        $acceso.TargetPath = $pythonw
        $acceso.Arguments = "`"$(Join-Path $raiz 'launcher\desemppa.pyw')`""
        $acceso.WorkingDirectory = $raiz
        $acceso.IconLocation = (Join-Path $raiz "assets\desemppa.ico")
        $acceso.Description = "Desemppa: información jurídica verificada"
        $acceso.Save()
        Write-Host "  $carpeta\Desemppa.lnk"
    }
}

Write-Host "`nListo. Abre Desemppa con el icono del Escritorio o del menú Inicio." -ForegroundColor Green
