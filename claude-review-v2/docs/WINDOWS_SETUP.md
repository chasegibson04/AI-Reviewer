# Windows Setup

## Prerequisites

- Node.js 20+
- Python 3.10+
- Bun (recommended for build path)
- Ollama (local model backend)

## Quick start

From PowerShell in `claude-review-v2/`:

```powershell
.\launchers\windows\claude-review-v2.cmd
```

Alternative:

```powershell
powershell -ExecutionPolicy Bypass -File .\launchers\windows\claude-review-v2.ps1
```

## If launch fails

```powershell
powershell -ExecutionPolicy Bypass -File .\launchers\windows\claude-review-v2.ps1 -Doctor
powershell -ExecutionPolicy Bypass -File .\launchers\windows\claude-review-v2.ps1 -Diagnose
```

These PowerShell checks run native Windows diagnostics (Ollama reachability + bridge/tests) and do not require Bash.

## Notes

- Launchers are path-space safe.
- If Bun is missing and `dist/cli.mjs` is not built, install Bun or build on a machine with Bun and retain `dist/`.
- For local-only runs, ensure Ollama is running and models are pulled.
