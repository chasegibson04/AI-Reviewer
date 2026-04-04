# Overnight Validation Report
Date: 2026-04-04

## Scope and restrictions enforced
- Write boundary: only `claude-review-v2/` edited.
- Absolute blacklist enforced in runner and manual selection:
  - excluded all paths containing `pampa`
  - excluded all paths containing `horseshoe`
- Allowed targets used:
  - `example_papers/gan_diffusion.pdf`
  - `projects/20260327051312_miniaturization_d2b/materials/manuscript/s44160-023-00351-1.pdf`

## What was found weak before fixes
- `manuscript_comment_manifest.json` outputs were shallow and repetitive.
- Arbitration text was often blank due key mismatch (`arbitrated_review` vs `summary`).
- Per-run `tool_event_log.jsonl` included cross-run noise from earlier runs.
- `parse_pdf`/`parse_docx` returned only the first 4k chars, reducing section/citation detection quality.
- Overnight report target labeling was incorrect.

## Hardening changes applied
- Bridge quality and consistency:
  - Increased extracted content window from 4k to 20k chars for analysis inputs.
  - Added normalization pass for analysis text.
  - Improved section mapping and coherence/methods/citation heuristics.
  - Added profile-aware arbitration scoring (`one_big_model`/`full_manuscript_final_pass` stricter).
  - Fixed log slicing so each run writes a coherent run-local `tool_event_log.jsonl`.
  - Extended arbitration tool schema to accept `profile`.
- Overnight runner:
  - Fixed arbitration comment generation to use recommendation/summary.
  - Added per-profile focus comments so profile outputs are distinguishable.
  - Added automated output quality report generation (`quality_report.md` + `.json`).
  - Added per-run `inspect_project` call so each run has explicit localhost backend evidence.
  - Removed deprecated UTC usage warnings.

## Commands/tests executed
- Python compile:
  - `python3 -m py_compile claude-review-v2/src/bridge/python/review_mcp_server.py claude-review-v2/tests/overnight_validation_runner.py`
- Bridge integration:
  - `./.venv/bin/python -m pytest -q claude-review-v2/tests/test_mcp_review.py`
- TS tests:
  - `cd claude-review-v2 && npm run test:provider-recommendation`
  - `cd claude-review-v2 && node --test --experimental-strip-types src/utils/model/reviewProfiles.test.ts src/commands/review/runParameters.test.ts`
- Runtime diagnostics:
  - `cd claude-review-v2 && bash scripts/doctor_runtime.sh`
  - `cd claude-review-v2 && bash scripts/smoke.sh` (fails: `bun: command not found`)
  - `cd claude-review-v2 && bash scripts/smoke_fallback.sh` (pass)
- Overnight matrix (all profiles x 2 targets):
  - `python3 claude-review-v2/tests/overnight_validation_runner.py`
- Benchmark tool check (allowed target only):
  - `benchmark_project(project_id=20260327051312_miniaturization_d2b)`

## Profiles exercised
- `balanced_local`
- `deep_local`
- `local_moe`
- `one_big_model`
- `full_manuscript_final_pass`

## Gemma 4 big-model validation
- Big-model profiles resolved to `gemma4:31b` on this machine (26b not detected, 31b detected).
- Confirmed in run artifacts:
  - `run_summary.json` profile/mode/model_target fields
  - `routing_trace.json` profile/model_target fields
- Big-model paths executed successfully in overnight runs for both targets.

## Output quality observations (latest run set)
Source: `claude-review-v2/test_outputs/overnight/20260404_000459/quality_report.md`
- Specificity: strong
- Helpfulness: actionable
- Redundancy: low
- Front-matter safety: safe
- Remaining limitation: comments are still heuristic and not yet citation-span precise; quality is improved but not close to full expert peer-review depth.

## Local-only evidence
- `validation_report.json` has empty `remote_network_events` for all runs.
- Per-run `network_event_log.jsonl` shows only localhost (`ollama_healthcheck`).
- `doctor_runtime.sh` confirms local Ollama reachability and local model inventory.

## Artifact consistency checks
- `run_summary.json` counts align with manifests.
- `routing_trace.json` profile/mode/model targets match selected profiles.
- `tool_event_log.jsonl` now reflects run-local stage sequence.
- `session_transcript.md` includes run summary + findings aligned with manifests.

## Build/runtime blocker status
- Blocking issue remains: Bun is missing in this environment, so `scripts/smoke.sh`/bun build path is not executable here.
- Validated fallback path is documented and working via:
  - Python bridge tests
  - Node strip-types tests
  - `scripts/smoke_fallback.sh`

## Honest gaps
- Interactive slash-command UX (`/project`, `/review`, `/deep-run`, `/artifacts`, `/diagnose`, `/doctor`, `/replay`, `/diff`, `/profile`) was validated through command/tool logic and artifact flows, but not full TTY interactive shell playback in this environment due Bun runtime gap.
- Analysis remains heuristic and deterministic; it is useful for local validation and artifact integrity, but not equivalent to a full LLM-scored manuscript critique.
