# Final Harsh Audit Packet

Generated at: 2026-03-28

## Scope Guard

- Horseshoe crab excluded: `true`
- Approved validation projects only:
  - `20260325163524_test-existingphactorpaper`
  - `20260327051312_miniaturization_d2b`

## Baseline vs Final (Deep-Run)

- Phactor baseline: `20260328_175942_deep_run`
  - suggested changes: `11`
  - applied: `5`
  - comments added: `13`
- Phactor final: `20260328_220607_deep_run`
  - suggested changes: `11`
  - applied: `10`
  - comments added: `13`

- Miniaturization baseline: `20260328_182044_deep_run`
  - suggested changes: `6`
  - applied: `3`
  - comments added: `8`
- Miniaturization final: `20260328_222544_deep_run`
  - suggested changes: `6`
  - applied: `6`
  - comments added: `7`

## Key Fixes Implemented

- Comment pipeline quality:
  - increased candidate coverage
  - sentence-level issue harvesting
  - generic-comment rejection
- Suggested-changes quality:
  - localized structural issues no longer globally skipped by default
  - stricter rewrite alignment checks
  - deterministic safe fallback rewrite when model output fails quality checks
- Support-material contamination controls:
  - relevance filtering for support docs in `review` and `deep-run`
  - blocked marker filtering (`BioGPT`, `OpenAI Gym`, etc.)
  - selected/skipped support provenance artifacts
- Safe online verification hardening:
  - citation query sanitization
  - explicit query policy + query audit metadata
- Docs/config reconciliation:
  - model/orchestrator defaults aligned in code and key docs

## Validation Runs

- `review --profile balanced`:
  - `20260325163524_test-existingphactorpaper` -> `20260328_211938_review`
  - `20260327051312_miniaturization_d2b` -> `20260328_212802_review`
- `deep-run`:
  - phactor -> `20260328_220607_deep_run`
  - miniaturization -> `20260328_222544_deep_run`

All above runs: output verification passed.

## Tests

- Full suite: `108 passed`
- Targeted regression tests added for:
  - support filtering
  - structure-localized rewrite path
  - citation query-policy/audit fields

## Remaining Weaknesses

- Section labeling still leaves residual `body` assignments on miniaturization.
- Sparse-review enrichment still triggers frequently (base model consistency limitation).
- Mac-specific runtime validated through tests and routing safeguards in this session, not by running these long workflows on physical Mac hardware here.
