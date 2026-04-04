@echo off
setlocal
set SCRIPT_DIR=%~dp0
for %%I in ("%SCRIPT_DIR%..\..") do set PROJECT_ROOT=%%~fI
cd /d "%PROJECT_ROOT%"
node scripts\launch.js %*
set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" (
  echo.
  echo Launch failed. Try:
  echo   powershell -ExecutionPolicy Bypass -File .\launchers\windows\claude-review-v2.ps1 --doctor
)
exit /b %EXITCODE%
