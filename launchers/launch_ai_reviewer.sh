#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT=""
if [ "${1:-}" != "" ]; then
  REPO_ROOT="$1"
else
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi
LOG_DIR="$REPO_ROOT/outputs/launcher_logs"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_PATH="$LOG_DIR/launcher_sh_${STAMP}.log"

log() {
  echo "$1"
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" >> "$LOG_PATH"
}

augment_path_for_macos() {
  if [ "$(uname -s)" = "Darwin" ]; then
    export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
  fi
}

detect_macos_arch() {
  if [ "$(uname -s)" = "Darwin" ]; then
    local arch
    arch="$(uname -m)"
    if [ "$arch" = "arm64" ]; then
      log "Detected macOS Apple Silicon ($arch)."
    else
      log "Detected macOS architecture: $arch."
      log "Warning: Apple Silicon-native install is recommended for best performance."
    fi
  fi
}

test_ollama() {
  if command -v curl >/dev/null 2>&1; then
    curl -sf "http://127.0.0.1:11434/api/version" >/dev/null 2>&1
    return $?
  fi
  "$PYTHON_EXE" - <<'PY' >/dev/null 2>&1
import sys, urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:11434/api/version", timeout=2) as r:
        sys.exit(0 if r.status == 200 else 1)
except Exception:
    sys.exit(1)
PY
}

if [ ! -f "$REPO_ROOT/pyproject.toml" ]; then
  log "ERROR: repo root not found at $REPO_ROOT"
  log "Expected to find pyproject.toml. Ensure the launcher resides inside the AI-Reviewer repo."
  exit 1
fi

cd "$REPO_ROOT"
log "AI-Reviewer launcher (.sh/.command)"
log "Repo root: $REPO_ROOT"
augment_path_for_macos
detect_macos_arch

if ! command -v python3 >/dev/null 2>&1; then
  log "ERROR: python3 not found on PATH. Install Python 3.10+ (brew install python) and retry."
  exit 1
fi

VENV_DIR="$REPO_ROOT/.venv"
PYTHON_EXE="$VENV_DIR/bin/python"
if [ ! -x "$PYTHON_EXE" ]; then
  log "Creating virtual environment at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

log "Verifying dependencies"
if ! "$PYTHON_EXE" -m pip install --upgrade pip >> "$LOG_PATH" 2>&1; then
  log "ERROR: pip upgrade failed. See $LOG_PATH"
  exit 1
fi
if ! "$PYTHON_EXE" -m pip install -e ".[dev]" >> "$LOG_PATH" 2>&1; then
  log "ERROR: dependency install failed. See $LOG_PATH"
  exit 1
fi

if ! test_ollama; then
  log "Ollama not reachable. Attempting safe local start: ollama serve"
  if command -v ollama >/dev/null 2>&1; then
    nohup ollama serve >/dev/null 2>&1 &
    sleep 3
  fi
fi

if ! test_ollama; then
  log "ERROR: Ollama still unreachable at http://127.0.0.1:11434"
  log "Manual action: run 'ollama serve' (or open Ollama app) then rerun launcher."
  exit 2
fi

log "Running launcher self-check"
"$PYTHON_EXE" -m ai_reviewer.launcher_checks >/dev/null 2>&1 || true

log "Launching guided AI-Reviewer workflow"
"$PYTHON_EXE" -m ai_reviewer launch
RC=$?
log "AI-Reviewer exited with code $RC"
log "Launcher log: $LOG_PATH"
exit "$RC"
