# Project Structure

`claude-review-v2/` is intentionally self-contained.

## Top-level layout

- `README.md`: primary user-facing overview and run instructions.
- `PLAYBOOK.md`: operational checklist for local review workflow.
- `docs/`: architecture/setup/launcher/troubleshooting docs.
- `audits/`: audit artifacts and completion status docs.
- `reports/`: validation reports and benchmark-readiness notes.
- `fixtures/`: in-bounds test manuscripts.
- `launchers/`: platform launch wrappers.
- `scripts/`: build/doctor/smoke/bootstrap/launch scripts.
- `src/`: TypeScript shell and Python bridge runtime code.
- `tests/`: bridge and validation test harnesses.
- `test_outputs/`: generated run artifacts used for validation.

## Runtime paths

- Primary launch path: `node scripts/launch.js`
- macOS wrappers: `launchers/macos/*`
- Windows wrappers: `launchers/windows/*`
- Bridge runtime: `src/bridge/python/review_mcp_server.py`

## Artifact paths

Run artifacts are expected under:
- `test_outputs/`
- `projects/` (if user creates in-folder project snapshots)
- `outputs/` (if used by specific run flows)

## Notes

- Files outside `claude-review-v2/` are not required for current test fixtures.
- Optional external Python package `ai_reviewer` can enhance parsing quality but is not required for bridge operation.
