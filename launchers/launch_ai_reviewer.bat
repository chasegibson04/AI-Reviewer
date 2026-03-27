@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
set "LOG_DIR=%REPO_ROOT%\outputs\launcher_logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%T"
set "LOG_PATH=%LOG_DIR%\launcher_bat_%STAMP%.log"

call :log "AI-Reviewer launcher (Windows .bat)"
call :log "Repo root: %REPO_ROOT%"

cd /d "%REPO_ROOT%"

where python >nul 2>nul
if errorlevel 1 (
  call :log "ERROR: Python not found on PATH. Install Python 3.10+ and retry."
  exit /b 1
)

set "VENV_DIR=%REPO_ROOT%\.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  call :log "Creating virtual environment at %VENV_DIR%"
  python -m venv "%VENV_DIR%"
)

call :log "Verifying dependencies"
"%PYTHON_EXE%" -m pip install --upgrade pip >nul 2>&1
"%PYTHON_EXE%" -m pip install -e .[dev] >nul 2>&1
if errorlevel 1 (
  call :log "ERROR: Dependency installation failed."
  exit /b 1
)

curl -sf http://127.0.0.1:11434/api/version >nul 2>nul
if errorlevel 1 (
  call :log "Ollama not reachable. Attempting safe local start: ollama serve"
  where ollama >nul 2>nul
  if not errorlevel 1 (
    start "ollama-serve" /min ollama serve
    timeout /t 3 /nobreak >nul
  )
)

curl -sf http://127.0.0.1:11434/api/version >nul 2>nul
if errorlevel 1 (
  call :log "ERROR: Ollama still unreachable at http://127.0.0.1:11434"
  call :log "Manual action: run 'ollama serve' then rerun launcher."
  exit /b 2
)

call :log "Running launcher self-check"
"%PYTHON_EXE%" -m ai_reviewer.launcher_checks >nul 2>&1

call :log "Launching guided AI-Reviewer workflow"
REM python -m ai_reviewer launch
"%PYTHON_EXE%" -m ai_reviewer launch
set "RC=%ERRORLEVEL%"
call :log "AI-Reviewer exited with code %RC%"
call :log "Launcher log: %LOG_PATH%"
if "%AI_REVIEWER_NO_PAUSE%"=="" (
  echo.
  echo Press any key to close this launcher window...
  pause >nul
)
exit /b %RC%

:log
set "MSG=%~1"
echo %MSG%
echo [%DATE% %TIME%] %MSG%>>"%LOG_PATH%"
exit /b 0
