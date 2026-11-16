@echo off
REM ---------------------------------------------------------------------------
REM  Run this ONCE, the first time you use this folder. You never need it again.
REM
REM  It brings across the two folders Claude is not allowed to write to from
REM  outside your machine -- .git (your version history and the GitHub link)
REM  and .github (the automated test setup) -- from the old Update3 folder.
REM  It then stages the new work and makes one commit.
REM
REM  Nothing is deleted. The old folder is left exactly as it is.
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "OLD=D:\Mini Project\Update3\carservice-source\carservice"

if not exist "%OLD%\.git" (
  echo.
  echo  Could not find the old repository at:
  echo    %OLD%
  echo.
  echo  Nothing has been changed. Tell Claude and it will sort this out.
  echo.
  pause
  exit /b 1
)

if exist ".git" (
  echo.
  echo  This folder already has a .git -- the one-time setup has been done.
  echo  Skipping the copy and going straight to the commit.
  echo.
) else (
  echo  Copying version history...
  xcopy /E /I /H /Q /Y "%OLD%\.git" ".git" >nul
  echo  Copying test setup...
  xcopy /E /I /H /Q /Y "%OLD%\.github" ".github" >nul
)

where git >nul 2>nul
if errorlevel 1 (
  echo.
  echo  The folders are in place, but Git is not on this machine's PATH.
  echo  Open a NEW terminal window and try again.
  echo.
  pause
  exit /b 1
)

echo.
echo  Recording the new work...
git add -A
git commit -m "Add logo, estimates, invoice types, attachments, import and messaging"

echo.
echo  ---------------------------------------------------------------------
echo   Done. One command left, and it is yours to run:
echo.
echo       git push -u origin main
echo.
echo   Then double-click run.bat to start the software.
echo  ---------------------------------------------------------------------
echo.
pause
