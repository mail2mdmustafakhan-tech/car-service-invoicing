@echo off
REM Start the application on Windows without Docker.
REM
REM Double-click this file, or run it from a command prompt.
REM
REM The first run creates a local Python environment and installs the four
REM dependencies; later runs skip straight to starting the server.

cd /d "%~dp0"

if not defined CARSERVICE_HOST set CARSERVICE_HOST=127.0.0.1
if not defined CARSERVICE_PORT set CARSERVICE_PORT=8000

if not exist .venv (
    echo First run: setting up Python environment...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo Python was not found. Install it from https://www.python.org/downloads/
        echo and tick "Add Python to PATH" during installation.
        pause
        exit /b 1
    )
    .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
    .venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
    echo Done.
)

echo.
echo   Car Service Invoicing
echo   Open this address in your browser:  http://%CARSERVICE_HOST%:%CARSERVICE_PORT%
echo   Close this window to stop.
echo.

.venv\Scripts\python.exe -m uvicorn app.main:app --host %CARSERVICE_HOST% --port %CARSERVICE_PORT%
pause
