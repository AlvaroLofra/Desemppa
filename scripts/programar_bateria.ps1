# Programa la batería verificable cada semana en el Programador de tareas de Windows.
#
#   powershell -ExecutionPolicy Bypass -File scripts\programar_bateria.ps1                # domingos a las 03:00
#   powershell -ExecutionPolicy Bypass -File scripts\programar_bateria.ps1 -Dia Saturday -Hora 04:30
#   powershell -ExecutionPolicy Bypass -File scripts\programar_bateria.ps1 -Quitar        # borra la tarea
#
# Gasta cuota real de Antigravity (30 consultas en Eco, unos 70 minutos). Necesita Desemppa en marcha en el
# puerto 8000 a esa hora; el informe queda en benchmark\expedientes\<fecha>_eco\informe.md. Para comparar dos
# ejecuciones: uv run python benchmark\comparar_ejecuciones.py <antes> <despues>
param(
    [string]$Dia = "Sunday",
    [string]$Hora = "03:00",
    [switch]$Quitar
)
$ErrorActionPreference = "Stop"
$nombre = "Desemppa - bateria verificable"
$raiz = Split-Path -Parent $PSScriptRoot

if ($Quitar) {
    Unregister-ScheduledTask -TaskName $nombre -Confirm:$false
    Write-Host "Tarea «$nombre» eliminada."
    exit 0
}

$uv = (Get-Command uv -ErrorAction Stop).Source
$accion = New-ScheduledTaskAction -Execute $uv -Argument "run python benchmark\ejecutar.py --modo eco --casos todos --pausa 5" -WorkingDirectory $raiz
$cuando = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Dia -At $Hora
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 3)
Register-ScheduledTask -TaskName $nombre -Action $accion -Trigger $cuando -Settings $ajustes -Force | Out-Null
Write-Host "Tarea «$nombre» programada: cada $Dia a las $Hora."
