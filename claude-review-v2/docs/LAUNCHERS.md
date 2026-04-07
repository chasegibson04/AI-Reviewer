# Launchers

This document defines exact launcher behavior and verification checks.

## Primary Launcher: `scripts/launch.js`

Responsibilities:

- Resolve `projectRoot` as `claude-review-v2`.
- Ensure local runtime config directory is self-contained (`.runtime/.claude`).
- Evaluate dist build freshness/health.
- Select launch target (`line_repl`, `dist_cli`, or opt-in legacy handoff).
- Expose `--print-launch-plan` for explicit path verification.

Default no-arg launch target:

- `line_repl`

Opt-in legacy handoff target:

- `legacy_guided_workflow` only when:
  - no user args
  - `CLAUDE_REVIEW_ALLOW_LEGACY_GUIDED=1`
  - internal line REPL override is not forced
  - legacy launcher file exists

## macOS Wrappers

- `launchers/macos/claude-review-v2.command`
- `launchers/macos/claude-review-v2.sh`

Both wrappers:

- resolve repo path from wrapper location
- `cd` into `claude-review-v2`
- run `node scripts/launch.js`
- forward launcher args (including `--print-launch-plan`)

## Windows Wrappers

- `launchers/windows/claude-review-v2.cmd`
- `launchers/windows/claude-review-v2.bat`
- `launchers/windows/claude-review-v2.ps1`

Behavior expectations:

- path-space-safe execution
- invoke `node scripts/launch.js`
- expose doctor/diagnose shortcuts in PowerShell wrapper

## Launch Plan Verification Commands

Use these to verify no boundary escape:

```bash
node scripts/launch.js --print-launch-plan
bash launchers/macos/claude-review-v2.sh --print-launch-plan
bash launchers/macos/claude-review-v2.command --print-launch-plan
```

Expected default output fields:

- `"launchTarget": "line_repl"`
- `"legacyGuidedEnabled": false` (unless explicitly set)

Legacy behavior check:

```bash
CLAUDE_REVIEW_ALLOW_LEGACY_GUIDED=1 node scripts/launch.js --print-launch-plan
```

Expected:

- `"launchTarget": "legacy_guided_workflow"`

## Build and Dist Behavior

If `dist/cli.mjs` is missing/stale/broken:

- if Bun exists: launcher rebuilds via `bun run build`
- if Bun missing: launcher prints recovery instructions and exits non-zero

## Failure Diagnostics

- `bash scripts/doctor_runtime.sh`
- `bash scripts/smoke_fallback.sh`

These checks should run from inside `claude-review-v2`.
