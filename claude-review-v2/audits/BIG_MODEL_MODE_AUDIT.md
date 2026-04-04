# BIG_MODEL_MODE_AUDIT
Date: 2026-04-04

## Selection surface
- Big-model profiles are selectable via `/profile`:
  - `one_big_model`
  - `full_manuscript_final_pass`
- Aliases supported: `big`, `final`, plus numeric menu selection.

## Resolution policy
- Preferred order implemented in profile resolver:
  1. `gemma4:26b` when detected
  2. `gemma4:31b` fallback
  3. configured big model / largest available local model fallback

## Runtime evidence
- Validated in overnight matrix runs (`test_outputs/overnight/20260404_000459/`).
- On this host, `gemma4:31b` was detected and used for both big-model profiles.
- Verified in each run's `run_summary.json` and `routing_trace.json`.

## Quality and tradeoffs
- Big-model profiles are operationally real and traceable.
- Output quality improvement over non-big profiles is currently modest because analysis stack is still heuristic.
- Recommendation: keep big-model mode available and optional; do not force as default yet.
