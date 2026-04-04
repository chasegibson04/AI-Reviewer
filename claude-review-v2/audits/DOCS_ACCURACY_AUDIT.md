# Docs Accuracy Audit

Date: 2026-04-04

## Scope

Audited markdown/docs under `claude-review-v2/`:
- `README.md`
- `PLAYBOOK.md`
- `docs/*`
- `src/bridge/python/BRIDGE_README.md`
- `audits/*` (as audit records)

## Findings before this pass

1. `README.md` was stale and described generic OpenClaude/open provider usage, not manuscript review v2 behavior.
2. `PLAYBOOK.md` was stale and provider-oriented, not aligned with current manuscript command/profile flow.
3. `docs/` lacked setup and launcher docs for cross-platform use.
4. docs index was missing.
5. self-containment limitations were undocumented.

## Corrections made

- Rewrote `README.md` with actual command surface, profile list, default profile, bridge/runtime behavior, artifacts, and current limitations.
- Rewrote `PLAYBOOK.md` with current operational workflow.
- Added docs:
  - `docs/INDEX.md`
  - `docs/PROJECT_STRUCTURE.md`
  - `docs/LAUNCHERS.md`
  - `docs/WINDOWS_SETUP.md`
  - `docs/MACOS_SETUP.md`
  - `docs/TROUBLESHOOTING.md`
  - `docs/SELF_CONTAINMENT_LIMITATIONS.md`
- Updated architecture and UX docs to reflect current behavior.
- Updated `src/bridge/python/BRIDGE_README.md` for current dependency/runtime contract.

## Remaining documentation risk

- Historical audit/report markdown files are retained for traceability and may describe older snapshots; they should be interpreted as dated evidence rather than current product spec.
