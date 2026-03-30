# Validation Testing Procedure

## 1. Purpose

This procedure is for long-run validation of manuscript review quality after a focused change. It is written to be executable by a weaker agent without relying on judgment shortcuts.

A run does not pass because files exist, counts increased, or tests are green. It passes only if the artifacts were opened, compared, and judged against the qualitative checklist below.

## 2. Allowed Projects And Blacklist

Approved validation projects only:

- `20260325163524_test-existingphactorpaper`
- `20260327051312_miniaturization_d2b`

Explicit blacklist:

- `20260324221200_horseshoe_crabs1`

Hard rules:

- Do not open the horseshoe crab project.
- Do not parse it.
- Do not benchmark it.
- Do not use it for smoke tests, fixtures, or comparisons.
- Validation stops immediately if this rule is violated.

## 3. Required Setup Checks

Run and record these before any validation:

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
Get-ChildItem -Name projects
python --version
python -m pytest --version
```

Then confirm:

- only the two approved projects are used for validation
- whether `strict_offline` or safe-online is intended
- which local models are available

Refresh or inspect project guard artifacts:

- `audits/project_access_guard.md`
- `audits/project_access_guard.json`

## 4. Required Validation Matrix

Run at least this matrix.

### 4.1 Balanced/core mode

```powershell
python -m ai_reviewer.cli review projects\20260325163524_test-existingphactorpaper\materials\manuscript\designing-chemical-reaction-arrays-using-phactor-and-chatgpt.pdf --project 20260325163524_test-existingphactorpaper --profile balanced
python -m ai_reviewer.cli review projects\20260327051312_miniaturization_d2b\materials\manuscript\s44160-023-00351-1.pdf --project 20260327051312_miniaturization_d2b --profile balanced
```

### 4.2 Deep/rigorous mode

```powershell
python -m ai_reviewer.cli deep-run --project 20260325163524_test-existingphactorpaper
python -m ai_reviewer.cli deep-run --project 20260327051312_miniaturization_d2b
```

### 4.3 DOCX-native fixture generation

```powershell
python scripts\build_docx_native_fixtures.py
Get-Content audits\docx_native_fixtures\generated\fixture_manifest.json
```

### 4.4 DOCX-native scenarios

Minimum cases:

- project 1 clean native DOCX review
- project 1 prior AI-commented DOCX review
- project 1 prior AI-suggested DOCX review
- project 2 clean native DOCX review
- project 2 commented heavy DOCX review
- project 2 prior AI-suggested DOCX review

Exact commands:

```powershell
python -m ai_reviewer.cli review audits\docx_native_fixtures\generated\20260325163524_test-existingphactorpaper\project1_clean_native.docx --project 20260325163524_test-existingphactorpaper --profile balanced
python -m ai_reviewer.cli review audits\docx_native_fixtures\generated\20260325163524_test-existingphactorpaper\project1_prior_ai_commented.docx --project 20260325163524_test-existingphactorpaper --profile balanced
python -m ai_reviewer.cli review audits\docx_native_fixtures\generated\20260325163524_test-existingphactorpaper\project1_prior_ai_suggested.docx --project 20260325163524_test-existingphactorpaper --profile balanced
python -m ai_reviewer.cli review audits\docx_native_fixtures\generated\20260327051312_miniaturization_d2b\project2_clean_native.docx --project 20260327051312_miniaturization_d2b --profile balanced
python -m ai_reviewer.cli review audits\docx_native_fixtures\generated\20260327051312_miniaturization_d2b\project2_commented_heavy.docx --project 20260327051312_miniaturization_d2b --profile balanced
python -m ai_reviewer.cli review audits\docx_native_fixtures\generated\20260327051312_miniaturization_d2b\project2_prior_ai_suggested.docx --project 20260327051312_miniaturization_d2b --profile balanced
```

### 4.5 Support-material OFF/ON

Support OFF direct-input lane:

```powershell
$env:AI_REVIEWER_STRICT_OFFLINE='true'
python -m ai_reviewer.cli review projects\20260325163524_test-existingphactorpaper\materials\manuscript\designing-chemical-reaction-arrays-using-phactor-and-chatgpt.pdf --profile balanced --output-dir audits\stage9_validation\project1_support_off
```

Expected result:

- run completes
- no `support_material_filtering.json` is emitted because no project support context is attached

Support ON project-scoped lane:

```powershell
python -m ai_reviewer.cli review projects\20260327051312_miniaturization_d2b\materials\manuscript\s44160-023-00351-1.pdf --project 20260327051312_miniaturization_d2b --profile balanced
```

Expected result:

- `support_material_filtering.json` exists
- selected support items carry provenance/verification labels

### 4.6 Strict-offline OFF/ON

Strict-offline ON check:

```powershell
$env:AI_REVIEWER_STRICT_OFFLINE='true'
python -m ai_reviewer.cli review projects\20260325163524_test-existingphactorpaper\materials\manuscript\designing-chemical-reaction-arrays-using-phactor-and-chatgpt.pdf --project 20260325163524_test-existingphactorpaper --profile balanced
```

Expected result:

- citation fetch is skipped or labeled offline-only
- no network-backed citation stage runs

Safe-online ON check:

```powershell
$env:AI_REVIEWER_STRICT_OFFLINE='false'
python -m ai_reviewer.cli review projects\20260327051312_miniaturization_d2b\materials\manuscript\s44160-023-00351-1.pdf --project 20260327051312_miniaturization_d2b --profile balanced
```

Expected result:

- `artifacts/citation_fetch_report.json` exists
- query policy declares:
  - no raw manuscript text
  - no long excerpts
  - no support-paper full text
  - query logging limited to type and length

### 4.7 Figure OFF/ON benchmark

```powershell
python scripts\run_stage8_optional_layer_benchmark.py
Get-Content audits\stage8_optional_layer_benchmark\summary.json
```

Expected interpretation:

- do not assume figure ON is better
- compare score and concern quality

### 4.8 Context-pack OFF/ON benchmark

Use the same benchmark script output.

Expected interpretation:

- context pack is useful only if it adds concrete compliance findings without distorting the rest of the review

### 4.9 Max-quality routing benchmark

```powershell
python scripts\run_stage7_max_quality_benchmark.py
Get-Content audits\stage7_benchmark\summary.json
```

Expected interpretation:

- do not claim max-quality is better unless benchmark evidence supports it

## 5. Required Artifact Checklist

For every new run, open and read:

- `review_report.md` or `final_deep_review_report.md`
- `manuscript_comment_manifest.json`
- `manuscript_suggested_changes_manifest.json`
- `commented_docx_validation.json`
- `suggested_changes_validation.json`
- `section_map.json`
- `run_metadata.json`
- `source_mode.json`

When present, also read:

- `support_material_filtering.json`
- `internal_consistency_checks.json`
- `artifacts/citation_fetch_report.json`
- `stage_model_stack.json`
- `deep_run_plan.json`

For DOCX-native runs, also inspect:

- `existing_comments_before`
- `existing_comments_after`
- `new_ai_reviewer_comments_added_count`
- `new_suggested_change_blocks_added`
- `meaningful_new_review_state`
- `silent_noop_suspected`

## 6. Qualitative Checklist

### 6.1 Section mapping

Check:

- meaningful content is not collapsed into `body`
- front matter or publisher noise does not poison later sections
- introduction vs methods vs results vs discussion are plausibly separated

Red flags:

- large `body` bucket on miniaturization
- intro framing treated as methods
- discussion absent because headers/noise hijacked state

### 6.2 Comments

Check:

- specific local diagnosis
- grounded in the anchor sentence or paragraph
- author-helpful revision direction
- section-appropriate tone
- reduced duplication

Red flags:

- `clarify` without local diagnosis
- `improve flow` without saying what is overloaded
- repeated template phrasing across many comments
- wrong-paragraph or wrong-section complaints

### 6.3 Suggested revisions

Check:

- faithful to the local span
- natural English
- solves the triggering issue
- abstains when the issue is too global or the span is unsafe

Red flags:

- truncated rewrite
- unsupported addition
- broader or different sentence rewritten than the anchor
- visible low-quality fallback text accepted as a rewrite

### 6.4 DOCX-native / pre-annotated DOCX

Check:

- source mode is `original_docx`
- old comments are preserved
- visible prior suggestion blocks are not analyzed as manuscript prose
- new review state is added when warranted
- re-review does not silently no-op

Treat as regression if:

- pre-annotated input preserves old markup but adds no meaningful new state
- `silent_noop_suspected=true` without an explicit safe abstention reason

### 6.5 Final reports

Check:

- report is manuscript-specific, not generic memo filler
- weaknesses align with comments and revisions
- context-pack or support materials do not distort the main review
- fallback synthesis warnings are surfaced honestly

## 7. Pass/Fail Criteria

A validation pass requires all of the following:

- approved-project-only rule held
- required matrix lanes were run or explicitly covered by prior stage artifacts
- artifacts were opened and read, not just generated
- full pytest is green
- before/after examples were collected for both projects
- DOCX-native matrix shows meaningful new review state
- safe-online artifacts show no manuscript-text leakage

Trigger a targeted rerun if:

- a required artifact is missing
- a validation JSON reports structural failure
- comments become more generic than baseline
- suggested changes become more sparse or less faithful
- DOCX-native runs show preserved old markup but no new state

Trigger a tiny code fix only if:

- validation exposes a concrete, narrow regression
- the fix is required to complete the matrix or keep tests green

Block push if:

- full pytest is not green
- approved projects were not both validated
- artifact reading was not completed
- remaining weaknesses are hidden instead of stated

## 8. Reporting Template

Use this exact structure:

1. Project access guard results
2. Validation matrix run
3. Before vs after findings on project 1
4. Before vs after findings on project 2
5. Concrete example improvements
6. Remaining weak examples
7. Tests run and results
8. Testing procedure markdown created/updated
9. Exact commands I should run locally

Required evidence:

- at least 3 comment improvements total
- at least 3 rewrite improvements total
- at least 1 correct abstention example
- at least 1 section-mapping improvement example per project
- at least 1 remaining weak example per project if weakness remains

Required wording discipline:

- use `materially better` only when artifact evidence supports it
- use `still weak` where synthesis/report quality remains generic
- use `not proven` if a lane was not actually run

## 9. Common Failure Modes

- section map collapses into `body`
- front matter or PDF noise flips active section
- comments are generic even when anchored
- suggested rewrites are truncated or drift semantically
- pre-annotated DOCX preserves old markup but adds nothing new
- support-material influence looks authoritative without real verification
- figure review adds parser noise instead of critique
- max-quality routing is claimed better without benchmark support
- final synthesis falls back silently
- tests are green but output quality is still weak

## 10. Commands Appendix

### Setup

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
Get-ChildItem -Name projects
python --version
python -m pytest --version
```

### Full test suite

```powershell
python -m pytest -q
```

### Key benchmark/report artifacts

```powershell
Get-Content audits\stage5_docx_native_matrix\matrix_results.json
Get-Content audits\stage6_validation\summary.json
Get-Content audits\stage7_benchmark\summary.json
Get-Content audits\stage8_optional_layer_benchmark\summary.json
Get-Content audits\stage9_validation_report.md
```

### Side-by-side comparison targets

Compare these between baseline and improved runs:

- `section_map.json`
- `manuscript_comment_manifest.json`
- `manuscript_suggested_changes_manifest.json`
- `review_report.md` or `final_deep_review_report.md`
- `commented_docx_validation.json`
- `suggested_changes_validation.json`
