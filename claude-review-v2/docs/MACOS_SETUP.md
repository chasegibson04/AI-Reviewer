# macOS Setup

## Prerequisites

- Node.js 20+
- Python 3.10+
- Bun (recommended for build path)
- Ollama (local model backend)

## Quick start

From Terminal:

```bash
./launchers/macos/claude-review-v2.sh
```

Finder double-click path:
- `launchers/macos/claude-review-v2.command`

## Diagnostics

```bash
bash scripts/doctor_runtime.sh
bash scripts/smoke_fallback.sh
```

## Notes

- Launchers resolve project root relative to launcher path.
- `scripts/launch.js` auto-builds with Bun when required.
- macOS launchers prepend `$HOME/.bun/bin` to `PATH` when present so Bun works from Finder/non-login shells.
