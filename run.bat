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

REM --- Is something already holding the port? ---------------------------------
REM
REM  If an older copy is still running, uvicorn cannot bind, the error scrolls
REM  past in a window nobody is watching, and the browser keeps answering from
REM  the stale server -- which looks exactly like the update not working.
REM
REM  Worse: that stale process keeps reading the templates off disk while
REM  running last week's Python, so after an update it does not serve an old
REM  page, it serves a 500. Finding and stopping it is the whole fix, so this
REM  offers to do it rather than asking you to hunt through open windows.
REM
REM  Note on the quoting below: the obvious `for /f %%R in ('powershell ...')`
REM  breaks when the PowerShell contains single quotes, because cmd treats the
REM  first one as the end of the command. That is exactly how an earlier
REM  version of this check failed silently. `usebackq` with backticks keeps
REM  the two quoting worlds apart.

set "PORT_PID="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "(Get-NetTCPConnection -LocalPort %CARSERVICE_PORT% -State Listen -ErrorAction SilentlyContinue ^| Select-Object -First 1).OwningProcess" 2^>nul`) do set "PORT_PID=%%P"

REM  Fails OPEN on purpose: no PowerShell, no cmdlet, no answer -- PORT_PID
REM  stays empty and we start normally. A false alarm that refused to launch
REM  would be worse than the confusion it is meant to prevent.

REM  Written flat with labels rather than as an `if (...)` block: a variable
REM  set inside a parenthesised block cannot be read inside that same block
REM  without delayed expansion, so the process name would print empty. Labels
REM  sidestep the whole rule.

if not defined PORT_PID goto :port_is_free

set "PORT_PROC=unknown"
for /f "usebackq delims=" %%N in (`powershell -NoProfile -Command "(Get-Process -Id %PORT_PID% -ErrorAction SilentlyContinue).ProcessName" 2^>nul`) do set "PORT_PROC=%%N"

echo.
echo   ================================================
echo     Port %CARSERVICE_PORT% is already being used.
echo.
echo     Process %PORT_PID%  (%PORT_PROC%)
echo.
echo     Nearly always this is an older copy of this software
echo     that was never closed. While it is running, your
echo     browser talks to it instead of to this one -- so a
echo     new feature looks missing, or every page shows
echo     "Internal Server Error".
echo   ================================================
echo.

choice /c YN /n /m "   Stop that process and start this one?  [Y/N] "
if errorlevel 2 goto :port_left_alone

echo.
echo   Stopping process %PORT_PID%...
taskkill /PID %PORT_PID% /F >nul 2>&1
REM  A moment for Windows to release the socket.
ping -n 3 127.0.0.1 >nul
echo   Done.
goto :port_is_free

:port_left_alone
echo.
echo   Left alone. Nothing was started or stopped.
echo   To run this copy alongside it, pick a free port:
echo       set CARSERVICE_PORT=8001
echo       run.bat
echo.
pause
exit /b 1

:port_is_free

REM --- Start -----------------------------------------------------------------

REM  When serving the whole network, 0.0.0.0 is what the computer listens
REM  on -- it is not an address anybody types. Find the one they do, so the
REM  tablet's address does not have to be guessed at or looked up in Windows.
set LAN_IP=
if /i "%CARSERVICE_HOST%"=="0.0.0.0" call :find_lan_ip

echo.
echo   ================================================
echo     Car Service Invoicing is starting
echo.
if defined LAN_IP (
    echo     On this computer:
    echo       http://localhost:%CARSERVICE_PORT%
    echo.
    echo     On a tablet or phone on the same Wi-Fi:
    echo       http://%LAN_IP%:%CARSERVICE_PORT%
    echo.
    echo     Anyone on this network can open it. There is no
    echo     password. Keep it to the workshop's own Wi-Fi.
) else if /i "%CARSERVICE_HOST%"=="0.0.0.0" (
    REM  Serving the network, but this computer's own address could not be
    REM  found. 0.0.0.0 is what it listens on, not something anybody types,
    REM  so printing it here would send somebody off to type an address that
    REM  cannot work.
    echo     On this computer:
    echo       http://localhost:%CARSERVICE_PORT%
    echo.
    echo     It is open to the network, but this computer's address on it
    echo     could not be found. Run check-network.bat to see it.
) else (
    echo     Open this address in your browser:
    echo       http://%CARSERVICE_HOST%:%CARSERVICE_PORT%
    echo.
    echo     To use it from a tablet as well, run network.bat instead.
)
echo.
echo     Leave this window open while you use it.
echo     Close it, or press Ctrl+C, to stop.
echo   ================================================
echo.

".venv\Scripts\python.exe" -m uvicorn app.main:app --host %CARSERVICE_HOST% --port %CARSERVICE_PORT%

REM Reached when the server stops, including when it could not start at all.
goto :stopped

REM  Finding this computer's address, in a subroutine rather than inline.
REM  Inline, inside the `if (...)` block, `%LAN_IP: =%` was expanded when the
REM  block was parsed -- before the loop that fills it had run -- so it
REM  cleared the variable it was meant to tidy, and the window printed
REM  "http://0.0.0.0:8000", which is not an address anybody can type. Out
REM  here each line is expanded as it runs.
:find_lan_ip
for /f "usebackq delims=" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\lan-ip.ps1"`) do set LAN_IP=%%A
goto :eof

:stopped
echo.
echo   The server has stopped.
echo   If it said "address already in use", something else is using port
echo   %CARSERVICE_PORT%. Start it on another port with:
echo       set CARSERVICE_PORT=8001
echo       run.bat
echo.
pause
