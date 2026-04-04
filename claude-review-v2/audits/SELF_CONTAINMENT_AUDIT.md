# Self-Containment Audit

Date: 2026-04-04

## Baseline findings

External dependency leaks identified before fixes:
- tests referenced repo-root fixtures (`example_papers/`, `projects/...`).
- tests set `PYTHONPATH` to parent/root.
- `scripts/smoke_fallback.sh` referenced `../.venv`.
- bridge startup appended repo-root path for optional imports.

## Changes applied

1. Added internal fixtures:
- `fixtures/manuscripts/gan_diffusion.pdf`
- `fixtures/manuscripts/s44160-023-00351-1.pdf`

2. Refactored tests to in-folder paths:
- `tests/test_mcp_review.py` now parses fixture paths inside `claude-review-v2/fixtures/`.
- `tests/overnight_validation_runner.py` now targets in-folder fixtures.

3. Removed parent `PYTHONPATH` assumptions from bridge test runners.

4. Updated fallback smoke script to use in-folder venv path (`.venv/bin/python`) when available.

5. Removed bridge repo-root path injection and kept optional import fallback behavior.

## Current status

- Runtime/test fixture and harness paths are now in-bounds.
- Remaining external dependencies are system/runtime-level only (Node/Bun/Python/Ollama), documented in `docs/SELF_CONTAINMENT_LIMITATIONS.md`.
