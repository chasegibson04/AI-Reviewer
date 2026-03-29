# Markdown Inventory (Overnight Rebuild)

Date: 2026-03-29

## Inspected and Updated

- `README.md`
  - Updated deep-run model stack defaults to match runtime/config.
- `docs/ai_reviewer/MODEL_SELECTION.md`
  - Reconciled balanced/deep/repair/embedding defaults.
- `docs/ai_reviewer/orchestrator_design.md`
  - Reconciled default orchestrator model to `phi4-reasoning:latest`.
- `docs/ai_reviewer/WORKFLOW_MECHANICS.md`
  - Added support-material relevance filtering behavior and unsupported-addition rewrite guard note.
- `docs/ai_reviewer/FULL_SYSTEM_REPORT_FOR_LLM.md`
  - Added query-audit policy, support decontamination notes, and unsupported speculative-addition guard note.
- `audits/project_access_guard.md`
  - Refreshed sprint timestamp and scope confirmation.

## Inspected, No Changes Required

- `docs/ai_reviewer/ARCHITECTURE.md` (no conflicting defaults detected)
- `docs/ai_reviewer/PRIVACY_AUDIT.md` (policy still aligned with strict-offline behavior)
- `docs/ai_reviewer/SECURITY.md` (no conflicting defaults detected)
- `docs/ai_reviewer/TROUBLESHOOTING.md` (example model pulls remain valid examples, not defaults)
- `docs/citation_fetch_methods.md` (method order still accurate)

## Remaining Doc Debt

- Add a dedicated `SAFE_ONLINE_VERIFICATION.md` page to centralize query-policy details.
- Add a `QUALITY_GATES.md` page that maps comment/rewrite gate logic to exact artifact fields.
