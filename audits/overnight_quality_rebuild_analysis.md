# Overnight Quality Rebuild Analysis

Date: 2026-03-29

## 1. Claims vs Runtime Reality (Current Pass)

- Claimed capabilities in repo/docs: deep-run orchestration, manuscript comments + suggested changes, citation prefetch, figure critique, orchestrator QA, strict-offline safety.
- Runtime reality validated in this pass:
  - all target workflows executed on the two approved projects only
  - full test suite green (`111 passed`)
  - context-pack support in deep-run now active and auditable
  - compliance findings can be generated deterministically from context-pack constraints
  - figure critique ON/OFF benchmark completed with post-dedupe behavior

## 2. Prioritized Overnight Execution List (Applied)

1. Reassert project access guard (approved projects only, horseshoe blacklist).
2. Close benchmark gap: orchestrator ON with no context-pack.
3. Validate post-dedupe figure critique with fresh figure-ON runs.
4. Run full pytest and require all green.
5. Reconcile docs with latest runtime behavior (context-pack, compliance stage, model routing clarifications).
6. Refresh overnight benchmark artifacts for final before/after reporting.

## 3. Highest-Value Failures Targeted This Pass

- Missing benchmark separation between:
  - orchestrator ON + context OFF
  - orchestrator ON + context ON
- Figure critique noise from repeated caption-missing concerns.
- Documentation drift for deep-run/context behavior.

## 4. What Was Added/Strengthened

- `ai_reviewer/review/deep_run.py`
  - optional context-pack ingestion path with explicit `context_material_ids`
  - auto context-pack category support when IDs are omitted
  - deterministic compliance stage (`stage_10b_compliance_check.*`)
  - context-pack artifacts (`context_pack_used.json/.md`)
  - context/compliance fields included in final payload and run metadata
- `ai_reviewer/cli.py`
  - deep-run CLI support for `--context-material-ids`
- `ai_reviewer/figures/figure_review.py`
  - tiny image suppression
  - fixed caption backfill indexing behavior
  - stronger claim-vs-caption-confidence warning
- `ai_reviewer/review/engine.py`
  - dedupe/aggregation for repeated figure caption-missing concerns

## 5. Benchmarked Outcomes (See `audits/overnight_stress_matrix.*`)

Deep-run (phactor):
- baseline `20260328_175942_deep_run`: comments 13, suggested 11, applied 5
- orchestrator ON + context OFF (forced) `20260329_030921_deep_run`: comments 12, suggested 10, applied 7
- orchestrator ON + context ON `20260329_002613_deep_run`: comments 11, suggested 9, applied 7, compliance findings 1

Deep-run (miniaturization):
- baseline `20260328_182044_deep_run`: comments 8, suggested 6, applied 3
- orchestrator ON + context OFF (forced) `20260329_032854_deep_run`: comments 7, suggested 6, applied 4
- orchestrator ON + context ON `20260329_005419_deep_run`: comments 7, suggested 6, applied 5, compliance findings 1

Figure benchmark:
- phactor OFF `20260329_011532_review` vs ON post-dedupe `20260329_025056_review`: ON added figure manifest with 8 figure-linked issues; comments remained stable.
- mini OFF `20260329_013115_review` vs ON post-dedupe `20260329_025831_review`: ON added figure manifest with 5 figure-linked issues; applied suggested changes improved (5 -> 6).

## 6. Remaining Risks / Honest Limits

- Sparse-review enrichment still triggers frequently on both approved projects; base model behavior remains uneven.
- Context-pack compliance checks are deterministic and intentionally conservative; they do not yet perform full semantic policy enforcement.
- Mac Apple Silicon validation remains code/routing + compatibility-guard verified in this environment; full physical M3 overnight execution still requires on-device run.
