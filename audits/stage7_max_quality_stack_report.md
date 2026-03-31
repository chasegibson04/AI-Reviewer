# Stage 7 Max-Quality Stack Report

## Scope

- Stage: 7 of 10
- Focus: rigorous mode and max-quality local model routing only
- Approved projects only:
  - `20260325163524_test-existingphactorpaper`
  - `20260327051312_miniaturization_d2b`
- Real benchmark project used:
  - `20260325163524_test-existingphactorpaper`
- Benchmark manuscript:
  - `20260329_174704_137524` (`project1_clean_native.docx`)

## Routing Audit Findings

Before this stage:
- deep-run stage routing was mostly hard-coded inside `deep_run.py`
- `reconciliation` was routed to a repair-class or repair-adjacent model
- `final_arbitration` existed in the stack but was not used as a real post-reconciliation step
- no explicit `default` vs `max_quality` routing mode existed in the selector layer

After this stage:
- deep-run stage routing is selector-driven
- routing mode is explicit:
  - config: `deep_run_routing.mode`
  - env override: `AI_REVIEWER_DEEP_RUN_ROUTING_MODE`
- stage stacks are written to:
  - `deep_run_plan.json`
  - `stage_model_stack.json`
- `final_arbitration` is now a bounded post-reconciliation pass

## Current Stage Policies

### Default

- `structural_triage`: cheap small triage model
- `supporting_digest`, `manuscript_digest`, `evidence_linking`, `context_synthesis`: balanced synth model
- `high_level_review`, `adversarial_review`, `methods_verification`: strongest critique model available
- `line_edits`, `style_alignment`: balanced synth/editor model
- `reconciliation`: repair/editor fallback lane
- `final_arbitration`: strongest critique model available

### Max Quality

- `structural_triage`: cheap small triage model
- `supporting_digest`, `manuscript_digest`, `evidence_linking`, `context_synthesis`: stronger medium/large digest model (`gemma3:27b` on this machine)
- `high_level_review`, `adversarial_review`, `methods_verification`: strongest large critique model (`llama3.3:70b-instruct-q4_K_M` on this machine)
- `line_edits`, `style_alignment`: stronger editor model (`gemma3:27b` on this machine)
- `reconciliation`: stronger editor/review model (`gemma3:27b` on this machine), no longer repair-class
- `final_arbitration`: strongest large critique model (`llama3.3:70b-instruct-q4_K_M`)

## Benchmark Evidence

Primary benchmark artifacts:
- `audits/stage7_benchmark/summary.json`
- `audits/stage7_benchmark/summary.md`
- default run: `audits/stage7_benchmark/20260329_205843_default`
- max-quality run: `audits/stage7_benchmark/20260329_211731_max_quality`

### Benchmark Result Summary

- Default reconciliation QC: `3.9 / 5`
- Max-quality reconciliation QC: `3.8 / 5`
- Default warnings: `2`
- Max-quality warnings: `2`
- Default style issues surfaced: `2`
- Max-quality style issues surfaced: `6`
- Default formatting issues surfaced: `2`
- Max-quality formatting issues surfaced: `6`

### Interpretation

What improved:
- stronger `line_edits` / `style_alignment` routing produced richer editorial output
- max-quality surfaced more style/formatting problems in the same manuscript
- reconciliation is no longer routed to a repair-class lane in max-quality mode

What did not improve:
- reconciliation QC did not improve
- fallback synthesis still triggered in both runs
- final arbitration did not rescue reconciliation because schema compliance remained weak

### Decision

Broad “everything stronger everywhere” routing was rejected.

The retained max-quality policy is narrower and evidence-based:
- keep cheap structural triage cheap
- keep strongest model on critique-heavy stages
- use stronger editor/digest lanes where they actually surface more editorial material
- do not claim reconciliation/final synthesis gains until prompt/schema quality improves

## Final Arbitration Findings

The new final-arbitration stage is now active and audited, but it is not yet reliable enough to claim a quality win.

Observed failure mode on both benchmark runs:
- arbitration output returned schema-incompatible structures
- default run produced API-header-like junk
- max-quality run produced a nested `MANUSCRIPT_EVALUATION` payload instead of the required reconciliation schema

Current conclusion:
- routing is no longer the only bottleneck
- reconciliation/final-arbitration prompt/schema behavior is now the main blocker for a stronger final synthesis

## Mac Safety Findings

- embedding models are excluded from deep-run chat stage routing
- multimodal models are excluded from text-only deep-run chat stages
- Mac ARM fallback is explicit in selector logic
- if `70b` is absent on Mac ARM, max-quality falls back to available text chat models such as:
  - `qwen3:14b`
  - `gemma3:27b`
  - `mistral-small3.1:24b`
  - `phi4-reasoning:latest`

## Tests

Targeted tests added/updated:
- `tests/unit/test_selector.py`
- `tests/integration/test_deep_run.py`

Assertions now cover:
- routing mode normalization
- default deep-run routing
- max-quality routing
- Mac ARM fallback behavior
- embedding/chat separation
- deep-run stage-model artifact emission
- bounded final-arbitration artifact emission

Test commands run:
- `python -m pytest tests/unit/test_selector.py tests/integration/test_deep_run.py -q`
- `python -m pytest tests/unit/test_selector.py tests/integration/test_deep_run.py tests/integration/test_pipeline.py -q`

Result:
- `16 passed`

## Stage 7 Verdict

This stage materially improved routing clarity and auditability.

It did **not** prove that max-quality routing improves final reconciliation quality on the benchmark manuscript.

The evidence supports this narrower conclusion:
- stronger local models are worth using for critique-heavy stages and edit/style stages
- stronger local models are **not yet proven** to improve reconciliation/final synthesis under the current prompt/schema layer
- therefore max-quality mode should remain opt-in and should not be treated as a universally better final-synthesis path until reconciliation/arbitration prompts are rebuilt
