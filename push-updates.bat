@echo off
setlocal
cd /d "%~dp0"

echo.
echo   ======================================================
echo    Send your changes to GitHub
echo   ======================================================
echo.

where git >nul 2>&1
if errorlevel 1 goto nogit
if not exist ".git" goto norepo

echo   These are the files that have changed:
echo.
git status --short
echo.

set COUNT=0
for /f %%L in ('git status --porcelain') do set /a COUNT+=1
if %COUNT%==0 goto nothing

echo   %COUNT% file(s) to send.
echo.

set "MSG="
set /p "MSG=  Describe the change (or just press Enter): "
if "%MSG%"=="" set "MSG=Update from the workshop laptop"

echo.
echo   Preparing...
git add -A
if errorlevel 1 goto addfailed

rem --- Safety net -------------------------------------------------------
rem This repository is public. The database holds real customer names and
rem phone numbers, and anything pushed to a public repo has to be treated
rem as published for good. .gitignore already keeps it out, but a rule can
rem be edited by accident, so the contents are checked here as well. If
rem customer data has somehow been staged, nothing is sent.
git diff --cached --name-only > "%TEMP%\arc_tocommit.txt"
rem Anchored patterns, one per check: ".db" at the end of a name, anything
rem under data\, and ".env" exactly -- so .env.example, which belongs in
rem the repository, does not raise a false alarm.
findstr /i /r "\.db$" "%TEMP%\arc_tocommit.txt" >nul
if not errorlevel 1 goto dangerous
findstr /i /r "^data/" "%TEMP%\arc_tocommit.txt" >nul
if not errorlevel 1 goto dangerous
findstr /i /r "\.env$" "%TEMP%\arc_tocommit.txt" >nul
if not errorlevel 1 goto dangerous
del "%TEMP%\arc_tocommit.txt" >nul 2>&1

echo   Saving...
git commit -m "%MSG%" >nul
if errorlevel 1 goto commitfailed

echo   Sending to GitHub...
echo.
git push
if errorlevel 1 goto pushfailed

echo.
echo   ======================================================
echo    Done. Your code is on GitHub.
echo   ======================================================
echo.
echo   See it at:
echo   https://github.com/mail2mdmustafakhan-tech/car-service-invoicing
echo.
pause
exit /b 0

:nothing
echo   Nothing has changed since your last send. There is
echo   nothing to do.
echo.
pause
exit /b 0

:nogit
echo   Git is not installed on this machine, so there is no
echo   way to send anything yet.
echo.
echo   Install it from https://git-scm.com/download/win
echo   Accept every default. Then run this file again.
echo.
pause
exit /b 1

:norepo
echo   This folder is not connected to GitHub yet.
echo   Run setup-git-once.bat first, then run this file.
echo.
pause
exit /b 1

:addfailed
echo   Git could not prepare the files. Nothing was sent.
echo.
pause
exit /b 1

:dangerous
echo.
echo   ****************************************************
echo    STOPPED - nothing has been sent.
echo   ****************************************************
echo.
echo   Something that looks like your customer database was
echo   about to be published to a public repository. That is
echo   not something you can undo, so this file refuses to
echo   continue.
echo.
echo   Nothing has been sent and nothing has been saved.
echo   Show this message to Claude before trying again.
echo.
git reset >nul 2>&1
pause
exit /b 1

:commitfailed
echo   Git could not save the change. Nothing was sent.
echo.
pause
exit /b 1

:pushfailed
echo.
echo   ****************************************************
echo    Could not send to GitHub.
echo   ****************************************************
echo.
echo   Your work is saved safely on this computer either
echo   way - nothing is lost. The usual reasons are:
echo.
echo   1. GitHub asked you to sign in and the window was
echo      closed or refused. Run this file again and sign
echo      in when the browser window appears.
echo.
echo   2. It says "rejected" or "fetch first" - GitHub has
echo      something your laptop does not. Do not force it.
echo      Tell Claude and it will sort out the order.
echo.
echo   3. No internet connection.
echo.
pause
exit /b 1
