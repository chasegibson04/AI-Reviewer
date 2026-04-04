# Cross-Platform Audit

Date: 2026-04-04

## Baseline

Before this pass:
- launch flow was Unix/Node oriented.
- no first-class Windows launcher docs or wrapper scripts.

## Additions in this pass

New launcher set:
- macOS:
  - `launchers/macos/claude-review-v2.command`
  - `launchers/macos/claude-review-v2.sh`
- Windows:
  - `launchers/windows/claude-review-v2.cmd`
  - `launchers/windows/claude-review-v2.bat`
  - `launchers/windows/claude-review-v2.ps1`
- shared core:
  - `scripts/launch.js`
  - PowerShell-native diagnostics path in `launchers/windows/claude-review-v2.ps1` (`-Doctor`, `-Diagnose`)

## Validation performed

- Shell syntax and path-resolution logic reviewed for space-safe working directories.
- macOS launcher invoked indirectly via `node scripts/launch.js` runtime checks in this environment.
- Windows launchers validated by static/script logic inspection in this environment.

## Validation limits

- Full interactive native Windows runtime was not executed in this macOS environment.
- Status: Windows is partially validated (launcher logic prepared and documented).
