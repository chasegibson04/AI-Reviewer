# Troubleshooting

## `dist/cli.mjs` missing

Cause:
- Build has not run yet.

Fix:
- `bun run build`
- then relaunch via platform launcher.

## Bun not installed

Symptoms:
- launch script reports missing Bun when `dist/` is absent.

Fix:
- install Bun from https://bun.sh
- or run from an already-built checkout containing `dist/cli.mjs`.

## Ollama unreachable

Symptoms:
- `/doctor` or `/diagnose` reports backend offline.
- `scripts/doctor_runtime.sh` fails health check.

Fix:
- start Ollama (`ollama serve`)
- verify models with `ollama list`

## Gemma 4 not detected

Symptoms:
- Big-model profiles report fallback model.

Fix:
- `ollama pull gemma4:26b`
- optional: `ollama pull gemma4:31b`

## Bridge unavailable

Symptoms:
- review tools fail to delegate or bridge not connected.

Fix:
- verify Python runtime: `python3 -m py_compile src/bridge/python/review_mcp_server.py`
- run bridge tests: `python3 -m pytest -q tests/test_mcp_review.py`

## Local-only assurance

Check per-run:
- `network_event_log.jsonl` should show local backend events only for local runs.
