# Launcher and Bootstrap Audit

Date: 2026-04-04

## Previous state

- `bin/openclaude` only checked for `dist/cli.mjs` and exited with generic build message.
- no common launcher abstraction.
- no platform wrapper set.

## Current state

Launcher core:
- `scripts/launch.js`

Behavior:
- if `dist/cli.mjs` exists: launch immediately
- if `dist` missing and Bun available: run `bun run build` then launch
- if Bun unavailable: print explicit recovery and diagnostics commands

Wrapper integration:
- `bin/openclaude` now delegates to `scripts/launch.js`
- macOS and Windows wrappers call `node scripts/launch.js` from resolved project root

## Open items

- Runtime build still depends on Bun for first-time build when `dist` is missing.
- This is documented rather than hidden.
