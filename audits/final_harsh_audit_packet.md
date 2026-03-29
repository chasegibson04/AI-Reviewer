# Final Harsh Audit Packet

Generated at: 2026-03-29

## Scope Guard

- Horseshoe crab excluded: `true`
- Approved validation projects only:
  - `20260325163524_test-existingphactorpaper`
  - `20260327051312_miniaturization_d2b`

## Baseline vs Current (Deep-Run)

- Phactor baseline: `20260328_175942_deep_run`
  - suggested changes: `11`
  - applied: `5`
  - comments added: `13`
- Phactor current (orchestrator ON, context OFF forced): `20260329_030921_deep_run`
  - suggested changes: `10`
  - applied: `7`
  - comments added: `12`
- Phactor current (orchestrator ON, context ON): `20260329_002613_deep_run`
  - suggested changes: `9`
  - applied: `7`
  - comments added: `11`
  - compliance findings: `1`

- Miniaturization baseline: `20260328_182044_deep_run`
  - suggested changes: `6`
  - applied: `3`
  - comments added: `8`
- Miniaturization current (orchestrator ON, context OFF forced): `20260329_032854_deep_run`
  - suggested changes: `6`
  - applied: `4`
  - comments added: `7`
- Miniaturization current (orchestrator ON, context ON): `20260329_005419_deep_run`
  - suggested changes: `6`
  - applied: `5`
  - comments added: `7`
  - compliance findings: `1`

## Key Fixes Implemented

- Comment pipeline quality:
  - increased candidate coverage
  - sentence-level issue harvesting
  - generic-comment rejection
- Suggested-changes quality:
  - localized structural issues no longer globally skipped by default
  - stricter rewrite alignment checks
  - deterministic safe fallback rewrite when model output fails quality checks
  - explicit blocking/fallback for unsupported speculative additions (e.g., fabricated comparative-study claims)
- Support-material contamination controls:
  - relevance filtering for support docs in `review` and `deep-run`
  - blocked marker filtering (`BioGPT`, `OpenAI Gym`, etc.)
  - selected/skipped support provenance artifacts
- Safe online verification hardening:
  - citation query sanitization
  - explicit query policy + query audit metadata
- Docs/config reconciliation:
  - model/orchestrator defaults aligned in code and key docs
- Optional context-pack support:
  - deep-run accepts `--context-material-ids`
  - context-pack constraints are extracted and audited in run artifacts
  - deterministic compliance checks are merged into reconciliation priorities
- Figure critique quality:
  - tiny/decorative images skipped
  - repeated caption-missing concerns are aggregated in review output

## Validation Runs (Current Pass)

- `review --profile balanced`:
  - phactor figure ON post-dedupe -> `20260329_025056_review`
  - mini figure ON post-dedupe -> `20260329_025831_review`
- `deep-run`:
  - phactor orchestrator ON + context OFF forced -> `20260329_030921_deep_run`
  - miniaturization orchestrator ON + context OFF forced -> `20260329_032854_deep_run`
  - context ON runs:
    - phactor -> `20260329_002613_deep_run`
    - miniaturization -> `20260329_005419_deep_run`

All above runs: output verification passed.

## Tests

- Full suite: `111 passed`
- Targeted regression tests added for:
  - support filtering
  - structure-localized rewrite path
  - citation query-policy/audit fields
  - deep-run context-pack material usage + compliance artifact presence
  - figure concern aggregation behavior

## Remaining Weaknesses

- Section labeling still leaves residual `body` assignments on miniaturization.
- Sparse-review enrichment still triggers frequently (base model consistency limitation).
- Mac-specific runtime validated through routing guards/tests in this session; full physical M3 long-run execution is still a remaining external validation step.
