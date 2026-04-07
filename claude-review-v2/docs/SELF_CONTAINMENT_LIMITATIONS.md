# Self-Containment Limitations

`claude-review-v2` is self-contained for launcher/runtime flow in this effort, with explicit practical limits.

## What Is Self-Contained

- default no-arg launcher path (`scripts/launch.js`) targets in-subproject line REPL.
- shell runtime and command flow are in `claude-review-v2/src` + `scripts/line-repl.js`.
- deep-review backend is in `src/bridge/python/review_mcp_server.py`.
- run artifacts and runtime cache paths are in-subproject (`test_outputs/`, `.runtime/`).

## Explicit External Dependencies

1. Runtime binaries:
- Node.js
- Python
- Ollama

2. Optional tooling:
- Bun for rebuild path
- `pdftotext` for cleaner PDF fallback extraction

3. Optional Python package enhancement:
- if `ai_reviewer` Python package is installed, bridge can use richer parse loaders
- if missing, bridge uses internal fallback parsers

## Optional Compatibility Escape Hatch

The only intentional parent handoff path is explicit opt-in:

- `CLAUDE_REVIEW_ALLOW_LEGACY_GUIDED=1`

Without that env var, default launch remains in-subproject.

## Non-Goals

- Perfect parity with all upstream OpenClaude modules in every environment.
- Guaranteed full-model reliability when local model backend is unhealthy.
- Replacing hardware/runtime constraints of local LLM inference.

## Practical Reliability Constraints

- Large model health depends on local Ollama process stability.
- If model probes fail, runtime can degrade to fallback/heuristic stages.
- Degraded behavior is expected to be reported explicitly in run summaries and routing traces.
