@echo off
REM ===========================================================================
REM  Double-click this when a phone or tablet cannot reach the application.
REM  It changes nothing -- it looks, and tells you which of the four usual
REM  causes is yours, and prints the address to type.
REM
REM  Leave the application running while this runs, in its own window.
REM ===========================================================================
title Car Service Invoicing - network check

if not defined CARSERVICE_PORT set CARSERVICE_PORT=8000

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\check-network.ps1" -Port %CARSERVICE_PORT%

pause
