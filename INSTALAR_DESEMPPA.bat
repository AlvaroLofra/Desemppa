@echo off
rem Instala Desemppa (doble clic): dependencias, interfaz, icono y accesos directos en el Escritorio y el menu Inicio.
rem Despues, abre la app con el icono «Desemppa»: ventana propia e icono junto al reloj.
cd /d "%~dp0"
title Instalar Desemppa
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\instalar.ps1"
echo.
pause
