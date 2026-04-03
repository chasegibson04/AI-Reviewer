# FOLLOWUP_STATE_AUDIT
Date: 2026-04-03

## What was audited first
- Command wiring and implementation for `/project`, `/review`, `/deep-run`, `/artifacts`, `/diagnose`, `/doctor`, `/replay`, `/diff`, `/profile`.
- Profile/routing behavior in model alias resolution and runtime provider detection.
- Startup flow (`src/setup.ts`) and session-start context.
- Bridge behavior (`src/bridge/python/review_mcp_server.py`) and generated artifacts under `test_outputs/`.

## Current follow-up state
- Command surface is wired and domain-oriented.
- `/profile` is now a guided run-style selector with numbered choices and alias shortcuts.
- Startup now surfaces run-style/profile readiness and Gemma availability hints.
- `/diagnose` and `/doctor` now report profile, resolved model target, and Gemma 4 visibility.
- Review/deep-run prompts now carry explicit selected profile/mode/model target into execution guidance.

## Big-model mode status
- `one_big_model` and `full_manuscript_final_pass` are exposed in profile selection flow.
- Gemma preference behavior implemented:
  - prefer `gemma4:26b`
  - fall back to `gemma4:31b` when 26B unavailable
  - then configured/heuristic local fallback.
- Verified environment currently reports `gemma4:31b` available.

## Artifact status
- Rendered outputs include required manifests/reports/logs plus validation report.
- Run summary now records profile/mode/model target.

## Honest status
- Bridge + local profile workflow is materially usable and validated via fallback smoke path.
- Full Bun-native shell build parity remains blocked in this environment (`bun` missing).
