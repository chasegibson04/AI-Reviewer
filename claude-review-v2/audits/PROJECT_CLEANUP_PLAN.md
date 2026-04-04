# Project Cleanup Plan

Date: 2026-04-04

## Objectives

1. Remove stale/incorrect docs.
2. Make fixture/test paths fully in-bounds.
3. Add explicit cross-platform launchers and setup docs.
4. Keep folder structure understandable and professional.

## Executed items

- Rewrote stale docs (`README.md`, `PLAYBOOK.md`, architecture/ux updates).
- Added docs index and setup/troubleshooting docs.
- Added internal fixtures under `fixtures/manuscripts/`.
- Refactored tests and smoke fallback script to avoid parent-level assumptions.
- Added launcher hierarchy under `launchers/`.
- Added launcher core script and delegated `bin/openclaude` to it.

## Follow-on hygiene items (optional)

- prune or archive very old historical audit snapshots if long-term maintainers want a shorter audits set.
- optionally add CI matrix for Windows + macOS launcher smoke checks.
