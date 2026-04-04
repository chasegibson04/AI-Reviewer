# Overnight Validation Report
Date: 2026-04-04

## Scope and restrictions enforced
- Write boundary: all non-git-metadata edits limited to `claude-review-v2/`.
- Absolute blacklist enforced in target selection and runner logic:
  - no PAMPA targets
  - no horseshoe / horseshoe-crab targets
- Allowed targets used:
  - `example_papers/gan_diffusion.pdf`
  - `projects/20260327051312_miniaturization_d2b/materials/manuscript/s44160-023-00351-1.pdf`

## What was found weak or misleading before fixes
- Tool schema drift between TS wrappers and bridge payloads (`analyze_methods`, `arbitrate_review`).
- `parse_docx` TS wrapper returned fake success-shaped payload when bridge was missing.
- Historical bridge log handling produced cross-run contamination in run-local logs.
- Review quality was still heuristic and somewhat repetitive, with limited profile differentiation.

## Fixes applied in this phase
- TS tool-wrapper hardening:
  - `AnalyzeMethodsTool`: schema aligned to bridge (`findings`, `signal_checks`, `skepticism_score`), honest bridge-missing failure.
  - `ArbitrateReviewTool`: schema aligned to bridge (`summary`, `recommendation`, optional `score/profile`).
  - `ParseDocxTool`: removed fake success fallback; now fails explicitly if bridge tool is unavailable.
  - `InspectProjectTool` and `DiscoverManuscriptTool`: bridge-first delegation, local fallback only if bridge is absent.
- Audit/docs hardening:
  - added full-system completion audits and status docs.
  - corrected architecture doc to reflect real current bridge-driven implementation.

## Commands/tests executed
- `python3 -m py_compile claude-review-v2/src/bridge/python/review_mcp_server.py claude-review-v2/tests/overnight_validation_runner.py`
- `./.venv/bin/python -m pytest -q claude-review-v2/tests/test_mcp_review.py`
- `cd claude-review-v2 && npm run test:provider-recommendation`
- `cd claude-review-v2 && node --test --experimental-strip-types src/utils/model/reviewProfiles.test.ts src/commands/review/runParameters.test.ts`
- `cd claude-review-v2 && bash scripts/doctor_runtime.sh`
- `cd claude-review-v2 && bash scripts/smoke.sh` (fails: Bun missing)
- `cd claude-review-v2 && bash scripts/smoke_fallback.sh` (pass)
- `python3 claude-review-v2/tests/overnight_validation_runner.py`

## Profiles exercised
- `balanced_local`
- `deep_local`
- `local_moe`
- `one_big_model`
- `full_manuscript_final_pass`

## Big-model / Gemma 4 evidence
- Big-model profiles were selectable and exercised in overnight matrix.
- On this machine:
  - `gemma4:31b` detected and used for `one_big_model` and `full_manuscript_final_pass`.
- Verified in `run_summary.json` and `routing_trace.json` under latest run root.

## Output quality findings (latest matrix)
Latest matrix root:
- `claude-review-v2/test_outputs/overnight/20260404_001247/`

Quality summary:
- `.../quality_report.md`
- All runs scored as:
  - specificity: strong
  - helpfulness: actionable
  - redundancy: low
  - front-matter safety: safe

Remaining quality limitation:
- The review backend remains heuristic and deterministic. Output is materially useful for structured checks and artifact consistency, but still below full expert-review depth and nuanced claim-level reasoning.

## Local-only evidence
- Per-run `network_event_log.jsonl` shows only localhost backend checks.
- `validation_report.json` reports no remote network events.
- `doctor_runtime.sh` confirms Ollama local backend and model inventory.

## Build/runtime blocker status
- Bun runtime is not installed in this environment.
- Therefore `scripts/smoke.sh` and Bun build path cannot be fully validated here.
- Validated fallback path is active and tested:
  - Python bridge tests
  - Node strip-types tests
  - `scripts/smoke_fallback.sh`

## Honest remaining gaps
- Full interactive shell parity validation is still constrained by Bun absence.
- Prompt-driven command flows (`/review`, `/deep-run`, `/replay`, `/diff`) still rely heavily on model execution quality.
- Review reasoning quality is improved but still heuristic-heavy vs full AI-Reviewer parity.
