Param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$LogDir = Join-Path $RepoRoot "outputs\launcher_logs"
$null = New-Item -ItemType Directory -Path $LogDir -Force
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogDir "launcher_ps1_$Stamp.log"

function Write-Log([string]$Message) {
    $line = "[$(Get-Date -Format o)] $Message"
    Write-Host $Message
    Add-Content -Path $LogPath -Value $line
}

function Test-Ollama {
    try {
        $null = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:11434/api/version" -TimeoutSec 3
        return $true
    }
    catch {
        return $false
    }
}

Set-Location $RepoRoot
Write-Log "AI-Reviewer launcher (PowerShell)"
Write-Log "Repo root: $RepoRoot"

$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    Write-Log "ERROR: Python not found on PATH. Install Python 3.10+ and retry."
    exit 1
}

$VenvDir = Join-Path $RepoRoot ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Log "Creating virtual environment at $VenvDir"
    python -m venv $VenvDir
}

Write-Log "Verifying dependencies"
& $PythonExe -m pip install --upgrade pip *> $null
& $PythonExe -m pip install -e ".`[dev`]" *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Log "ERROR: Dependency installation failed. Re-run manually to inspect pip output."
    exit $LASTEXITCODE
}

if (-not (Test-Ollama)) {
    Write-Log "Ollama not reachable. Attempting safe local start: ollama serve"
    $OllamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($OllamaCmd) {
        Start-Process -FilePath $OllamaCmd.Source -ArgumentList "serve" -WindowStyle Minimized
        Start-Sleep -Seconds 3
    }
}

if (-not (Test-Ollama)) {
    Write-Log "ERROR: Ollama still unreachable at http://127.0.0.1:11434"
    Write-Log "Manual action: run 'ollama serve' then rerun this launcher."
    exit 2
}

Write-Log "Running launcher self-check"
& $PythonExe -m ai_reviewer.launcher_checks *> $null

Write-Log "Launching guided AI-Reviewer workflow"
& $PythonExe -m ai_reviewer launch
$code = $LASTEXITCODE
Write-Log "AI-Reviewer exited with code $code"
Write-Log "Launcher log: $LogPath"
if (-not $env:AI_REVIEWER_NO_PAUSE) {
    Write-Host ""
    Read-Host "Press Enter to close this launcher window"
}
exit $code
