# Stage 8 Figure / Compliance / Context-Pack Benchmark Report

## Scope

- Stage: 8 of 10
- Focus:
  - figure review
  - context-pack/compliance
  - optional-layer benchmarking only
- Approved projects only:
  - `20260325163524_test-existingphactorpaper`
  - `20260327051312_miniaturization_d2b`

Primary benchmark summary:
- `audits/stage8_optional_layer_benchmark/summary.json`

## 1. Figure-Review Audit Findings

Current implementation:
- file: `ai_reviewer/figures/figure_review.py`
- source type: PDF only
- extraction method:
  - image extraction from PDF
  - caption heuristics from page text / nearby blocks
- visual mode:
  - `text_only`
  - no multimodal/VLM understanding is actually used

Noise controls currently present:
- skips non-PDF sources
- skips tiny decorative/logo assets
- caps reviewed figures by `max_figures`
- deduplicates repeated caption-missing messages into one aggregate concern

Observed limit:
- on both approved manuscripts, most extracted figures had no reliable caption text
- the system therefore mostly emitted:
  - “caption not detected”
  - “verify caption parsing”
- this is extraction-quality noise, not strong editorial figure critique

## 2. Context-Pack / Compliance Audit Findings

Current implementation:
- file: `ai_reviewer/review/deep_run.py`
- context-pack materials come from:
  - `style_guide`
  - `journal_instructions`
  - `reference_example`
  - `methods_reference`
- compliance is deterministic, not model-based

What it can currently do:
- extract priorities from the supplied guide
- extract forbidden title words if explicitly stated
- extract simple word-count limits if explicitly stated
- extract required reporting items
- inject findings into:
  - `stage_10b_compliance_check.json`
  - final reconciliation weaknesses/actions

What it is not:
- not a general journal-compliance engine
- not a substitute for normal manuscript review
- not a strong style-transfer mechanism

## 3. Controlled Comparison Results

### Figure Review OFF vs ON

Project 1:
- OFF specialist score: `2.26`
- ON specialist score: `2.16`
- OFF figure concerns: `1`
- ON figure concerns: `2`
- new ON-only concern:
  - `6 extracted figure(s) lacked reliable caption text...`

Project 2:
- OFF specialist score: `2.17`
- ON specialist score: `1.96`
- OFF figure concerns: `0`
- ON figure concerns: `1`
- new ON-only concern:
  - `5 extracted figure(s) lacked reliable caption text...`

Judgment:
- figure review did not improve review quality on either approved manuscript
- it added extraction-failure warnings rather than strong manuscript-specific figure critique
- specialist quality scores worsened in both cases

### Context-Pack OFF vs ON

Project 1:
- OFF compliance findings: `0`
- ON compliance findings: `1`
- ON added:
  - `Context-pack required item may be missing: limitations_statement.`
- final weaknesses: `10 -> 11`
- final priority actions: `10 -> 11`

Project 2:
- OFF compliance findings: `0`
- ON compliance findings: `1`
- ON added:
  - `Context-pack required item may be missing: limitations_statement.`
- final weaknesses: `10 -> 11`
- final priority actions: `8 -> 9`

Judgment:
- context-pack/compliance added one concrete, manuscript-relevant reporting check on both projects
- it did not distort the main review in these runs
- it behaved like a bounded constraint layer, not a replacement for manuscript critique

## 4. Standards / Journal Guide Example

Guide used:
- `context_pack_sample_journal.md`

Extracted priorities:
- `claim_calibration`
- `figure_caption_quality`
- `formatting_compliance`
- `methods_reporting`

Actual useful effect in these runs:
- the only concrete deterministic finding that consistently propagated was:
  - missing or possibly missing `limitations_statement`

This is modest, but real.

## 5. Adoption / Rejection Decision

### Figure Review

Decision:
- keep available
- keep **OFF by default**
- treat as experimental/opt-in only

Reason:
- current implementation is text-only
- caption pairing is too weak on the approved PDFs
- observed output was mostly extraction-noise, not strong figure critique

### Context-Pack / Compliance

Decision:
- keep available
- keep **opt-in**
- useful when the user explicitly wants review constrained by a known guide/journal policy

Reason:
- it added a concrete reporting/compliance signal without noticeably distorting the main review
- current value is modest but legitimate
- it should remain secondary to manuscript-first review

## 6. Default Recommendation

- `figure_review.enabled`: keep default `false`
- context-pack/compliance:
  - keep available
  - do not force it as a universal default review layer
  - use it when the user provides a real standards/journal constraint or wants policy-aware review

## 7. Code / Behavior Changes

Core feature behavior:
- no core figure/compliance logic was changed in this stage

Benchmark harness added:
- `scripts/run_stage8_optional_layer_benchmark.py`

## 8. Tests

Existing relevant tests run:
- `tests/unit/test_figure_review.py`
- `tests/integration/test_pipeline.py`
- `tests/integration/test_deep_run.py`

Result:
- `9 passed`

## 9. Honest Limitations

- Figure review is still not true visual review.
- Caption extraction quality is not good enough on the approved PDFs.
- Context-pack/compliance currently catches only simple deterministic policy items.
- These optional layers are not strong enough to market as universally beneficial defaults.
