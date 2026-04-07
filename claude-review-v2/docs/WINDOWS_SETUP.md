# Windows Setup

This guide covers reliable Windows startup for `claude-review-v2`.

## 1) Prerequisites

Required:

- Node.js 20+
- Python 3.10+
- Ollama local service

Recommended:

- Bun (build/rebuild convenience)

Verify in PowerShell:

```powershell
node -v
python --version
ollama --version
```

## 2) Start Ollama and Pull Models

```powershell
ollama serve
ollama list
ollama pull gemma4:26b
# optional
ollama pull gemma4:31b
```

## 3) Launch Options

From `claude-review-v2` directory:

```powershell
.\launchers\windows\claude-review-v2.cmd
```

Alternative PowerShell script:

```powershell
powershell -ExecutionPolicy Bypass -File .\launchers\windows\claude-review-v2.ps1
```

## 4) Diagnostics

PowerShell wrapper shortcuts:

```powershell
powershell -ExecutionPolicy Bypass -File .\launchers\windows\claude-review-v2.ps1 -Doctor
powershell -ExecutionPolicy Bypass -File .\launchers\windows\claude-review-v2.ps1 -Diagnose
```

## 5) Verify Launch Path

Use launch-plan command from project root:

```powershell
node scripts/launch.js --print-launch-plan
```

Expected default:

- `launchTarget` is `line_repl`

## 6) Deep-Run Verification

In interactive shell:

- run `/deep-run`
- confirm prompt offers MOE vs Single-model Gemma 4
- inspect run artifacts (`run_summary.json`, `routing_trace.json`)

## 7) Notes

- Wrapper scripts are path-space-safe.
- If Bun is missing and `dist` is unavailable, either install Bun and build or run fallback diagnostics and repair first.
