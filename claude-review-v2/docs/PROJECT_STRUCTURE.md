# Project Structure

`claude-review-v2/` is the required implementation boundary for this effort.

## Top-Level Tree and Ownership

- `README.md`
  - user-facing quickstart and operational behavior.
- `PLAYBOOK.md`
  - local execution checklist.
- `docs/`
  - architecture, UX, launcher, setup, and troubleshooting docs.
- `launchers/`
  - macOS and Windows wrappers.
- `scripts/`
  - launch, doctor, smoke, provider helper scripts.
- `src/`
  - shell runtime and bridge integration code.
- `src/bridge/python/`
  - Python backend bridge and bridge docs.
- `tests/`
  - targeted unit/integration validation for shell and bridge.
- `test_outputs/`
  - generated run artifacts and validation outputs.
- `audits/` and `reports/`
  - audit records and status notes.

## Critical Runtime Files

Launcher and startup:

- `scripts/launch.js`
- `launchers/macos/claude-review-v2.command`
- `launchers/macos/claude-review-v2.sh`
- `launchers/windows/claude-review-v2.cmd`
- `launchers/windows/claude-review-v2.bat`
- `launchers/windows/claude-review-v2.ps1`

Interactive UX:

- `scripts/line-repl.js`

Model/profile config:

- `src/utils/model/reviewProfiles.ts`
- `src/commands/review/runParameters.ts`

Bridge/backend:

- `src/bridge/python/review_mcp_server.py`
- `src/bridge/python/BRIDGE_README.md`

## Runtime Storage Locations

- `.runtime/`
  - bridge-internal and launcher runtime state (including support ingest cache root).
- `test_outputs/`
  - run-specific artifacts used for validation and inspection.

## Artifact Subset Worth Checking First

When validating behavior, inspect these first:

- `run_summary.json`
- `routing_trace.json`
- `manuscript_comment_manifest.json`
- `manuscript_suggested_changes_manifest.json`
- `support_ingest_report.json`
- `support_ingest_cache_index.json`
- `citation_verification_ledger.json`
- `validation_report.json`

## Boundary Rules for This Subproject

- Keep implementation changes inside `claude-review-v2` for this track.
- Do not rely on parent repo launch/runtime internals for normal no-arg flow.
- Use bridge artifacts to prove behavior rather than only shell logs.
