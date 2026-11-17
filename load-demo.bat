@echo off
REM ===========================================================================
REM  Car Service Invoicing -- open the DEMO copy
REM ===========================================================================
REM
REM  Fifty customers, their cars, a BMW price list, quotes, contracts and
REM  invoices to click around in.
REM
REM  Your real records are NOT touched. The demo lives in its own file,
REM  data\demo.db, and this window runs the software against that file
REM  instead. Close the window and the demo is gone from view; delete
REM  data\demo.db and it is gone for good.
REM
REM  To get back to your real data, just use run.bat as usual.
REM ===========================================================================

setlocal
cd /d "%~dp0"

set "CARSERVICE_DB=data\demo.db"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo   Run run.bat once first -- it sets up the Python environment
    echo   that this script needs.
    echo.
    pause
    exit /b 1
)

if not exist "data\demo.db" (
    echo.
    echo   Building the demo data. This takes a few seconds...
    echo.
    ".venv\Scripts\python.exe" seed_demo.py --db "data\demo.db"
    if errorlevel 1 (
        echo.
        echo   The demo data could not be built. Nothing was changed.
        echo.
        pause
        exit /b 1
    )
) else (
    echo.
    echo   Using the demo data already in data\demo.db
    echo   Delete that file if you want a fresh copy.
)

REM  A different port from the real one on purpose, so the demo and your
REM  real records can be open side by side without one quietly standing in
REM  for the other.
if not defined CARSERVICE_PORT set CARSERVICE_PORT=8010
if not defined CARSERVICE_HOST set CARSERVICE_HOST=127.0.0.1

echo.
echo   ================================================
echo     DEMO DATA -- not your real records
echo.
echo     Open this address in your browser:
echo       http://%CARSERVICE_HOST%:%CARSERVICE_PORT%
echo.
echo     Your real data stays where it is. Use run.bat
echo     for that, on the usual address.
echo   ================================================
echo.

".venv\Scripts\python.exe" -m uvicorn app.main:app --host %CARSERVICE_HOST% --port %CARSERVICE_PORT%

echo.
echo   The demo has stopped.
echo.
pause
