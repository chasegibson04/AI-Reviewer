# Launchers

`claude-review-v2` ships with a common launcher core and platform wrappers.

## Core launcher

- `scripts/launch.js`

Behavior:
- Runs `dist/cli.mjs` if present.
- If `dist/` is missing and Bun exists, runs `bun run build` then launches.
- If Bun is unavailable and `dist/` is missing, prints recovery + diagnostics commands.

## macOS launchers

- `launchers/macos/claude-review-v2.command`
- `launchers/macos/claude-review-v2.sh`

Both wrappers:
- resolve project root from launcher location
- `cd` into project root
- execute `node scripts/launch.js`

## Windows launchers

- `launchers/windows/claude-review-v2.cmd`
- `launchers/windows/claude-review-v2.bat`
- `launchers/windows/claude-review-v2.ps1`

Wrappers:
- resolve project root robustly (path-space safe)
- invoke `node scripts/launch.js`
- expose quick diagnostics via PowerShell switches (`-Doctor`, `-Diagnose`) without requiring Bash

## Diagnostics after launch failure

- `bash scripts/doctor_runtime.sh`
- `bash scripts/smoke_fallback.sh`
