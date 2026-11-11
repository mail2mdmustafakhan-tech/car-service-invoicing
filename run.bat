@echo off
REM ===========================================================================
REM  Car Service Invoicing -- start the application on Windows (no Docker)
REM ===========================================================================
REM
REM  Double-click this file, or run it from a command prompt.
REM
REM  The first run creates a private Python environment inside this folder and
REM  installs four packages into it; that takes a minute. Later runs skip
REM  straight to starting the server.
REM
REM  Nothing is installed system-wide, and deleting the .venv folder undoes it.
REM ===========================================================================

setlocal
cd /d "%~dp0"

if not defined CARSERVICE_HOST set CARSERVICE_HOST=127.0.0.1
if not defined CARSERVICE_PORT set CARSERVICE_PORT=8000

REM --- Find a working Python -------------------------------------------------
REM  Windows ships a stub called "python" that opens the Microsoft Store
REM  instead of running anything. It reports success, so it has to be checked
REM  by actually asking for a version number rather than by its exit code.
REM  The "py" launcher, installed with Python itself, is tried first because
REM  it is not shadowed by that stub.

set PYTHON=
for %%P in (py python python3) do (
    if not defined PYTHON (
        %%P -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
        if not errorlevel 1 set PYTHON=%%P
    )
)

if not defined PYTHON (
    echo.
    echo   Python 3.10 or newer was not found.
    echo.
    echo   Install it with:     winget install --id Python.Python.3.12 -e
    echo   or download it from: https://www.python.org/downloads/
    echo   ^(tick "Add Python to PATH" during installation^)
    echo.
    echo   Then CLOSE this window, open a new one, and run this file again.
    echo.
    pause
    exit /b 1
)

REM --- Set up the environment on first run -----------------------------------

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo   First run: setting up Python environment. This takes a minute...
    echo.
    %PYTHON% -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo   Could not create the Python environment in this folder.
        echo   If this folder is on OneDrive or a network drive, try copying
        echo   it somewhere local, such as C:\carservice, and running again.
        echo.
        pause
        exit /b 1
    )

    ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
    ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
    if errorlevel 1 (
        echo.
        echo   Could not install the required packages. The usual cause is no
        echo   internet connection, or a firewall blocking it. Check the
        echo   messages above, then run this file again.
        echo.
        pause
        exit /b 1
    )
    echo   Setup complete.
)

REM --- Start -----------------------------------------------------------------

echo.
echo   ================================================
echo     Car Service Invoicing is starting
echo.
echo     Open this address in your browser:
echo       http://%CARSERVICE_HOST%:%CARSERVICE_PORT%
echo.
echo     Leave this window open while you use it.
echo     Close it, or press Ctrl+C, to stop.
echo   ================================================
echo.

".venv\Scripts\python.exe" -m uvicorn app.main:app --host %CARSERVICE_HOST% --port %CARSERVICE_PORT%

REM Reached when the server stops, including when it could not start at all.
echo.
echo   The server has stopped.
echo   If it said "address already in use", something else is using port
echo   %CARSERVICE_PORT%. Start it on another port with:
echo       set CARSERVICE_PORT=8001
echo       run.bat
echo.
pause
