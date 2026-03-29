# Validation Testing Procedure

## 1. Purpose

This procedure is for long-run validation of manuscript review output quality after a focused code change.

It is meant to catch regressions in:

- section mapping
- comment specificity and usefulness
- comment spread and duplication
- suggested-revision usefulness and faithfulness
- final report manuscript-specificity
- artifact generation and validation completeness

Do not treat green tests or completed runs as success on their own. This procedure requires artifact reading and before/after comparison.

## 2. Allowed Projects

Approved validation projects:

- `20260325163524_test-existingphactorpaper`
- `20260327051312_miniaturization_d2b`

Explicitly blacklisted:

- `20260324221200_horseshoe_crabs1`

Rules:

- Do not open the horseshoe crab project.
- Do not parse it.
- Do not benchmark it.
- Do not use it for smoke tests, regression tests, or comparison runs.

## 3. Required Setup Checks

Run these before any validation:

1. Record `git status --short`.
2. Record current branch and commit:
   - `git branch --show-current`
   - `git rev-parse HEAD`
3. Confirm the allowed projects only:
   - `Get-ChildItem -Name projects`
4. Refresh project access guard artifacts.
5. Record Python/test environment:
   - `python --version`
   - `python -m pytest --version`
6. Record whether strict-offline or safe-online mode is intended for this validation.
7. Confirm required models are available if local model routing is part of the run.

Validation must stop if the project access rules are violated.

## 4. Required Workflow Matrix

Run exactly this minimum matrix:

### Project 1

1. Balanced review
2. Deep-run

### Project 2

1. Balanced review
2. Deep-run

Required commands:

```powershell
python -m ai_reviewer.cli review projects\20260325163524_test-existingphactorpaper\materials\manuscript\designing-chemical-reaction-arrays-using-phactor-and-chatgpt.pdf --project 20260325163524_test-existingphactorpaper --profile balanced
python -m ai_reviewer.cli deep-run --project 20260325163524_test-existingphactorpaper
python -m ai_reviewer.cli review projects\20260327051312_miniaturization_d2b\materials\manuscript\s44160-023-00351-1.pdf --project 20260327051312_miniaturization_d2b --profile balanced
python -m ai_reviewer.cli deep-run --project 20260327051312_miniaturization_d2b
```

### DOCX-native fixture generation

Generate the safe DOCX-native fixture set before any DOCX-native validation:

```powershell
python scripts\build_docx_native_fixtures.py
```

This writes:

- `audits/docx_native_fixtures/generated/fixture_manifest.json`
- clean native DOCX fixtures
- commented light/heavy DOCX fixtures
- prior AI-Reviewer commented DOCX fixtures
- prior suggested-changes DOCX fixtures

DOCX-native minimum scenarios:

1. clean native DOCX review on project 1
2. clean native DOCX deep-run on project 1
3. commented native DOCX review on project 1
4. prior AI-Reviewer commented DOCX review on project 1
5. prior suggested-changes DOCX review on project 1
6. clean native DOCX review on project 2
7. clean native DOCX deep-run on project 2
8. commented native DOCX review on project 2

For every run, record:

- run id
- command used
- profile or mode
- model stack from `run_metadata.json`
- start time
- end time
- status

## 5. Artifact Collection Checklist

For each new run, open and read:

- `final_deep_review_report.md` for deep-run
- `surrogate_manuscript_from_pdf_with_comments.docx`
- `surrogate_manuscript_from_pdf_with_suggested_changes.docx`
- `manuscript_comment_manifest.json`
- `manuscript_suggested_changes_manifest.json`
- `commented_docx_validation.json`
- `suggested_changes_validation.json`
- `section_map.json`
- `run_metadata.json`
- `source_mode.json`

Optional but useful:

- `final_deep_review_report.json`
- `post_revision_recheck.json`
- `remaining_issue_map.json`

For each run, record at minimum:

- comment count
- comments by section
- comment paragraph indices
- generic or templated comment count
- suggested change count
- applied suggested change count
- skipped or unresolved change count
- skip reasons
- section map counts
- source mode
- annotation state of the input DOCX if present
- existing comments before/after if present
- existing suggested-change blocks before/after if present

## 6. Qualitative Review Checklist

### Comments

Check:

- specificity
- usefulness
- grounding in nearby manuscript text
- section appropriateness
- severity calibration
- spread across weak sections
- duplication or near-duplication
- genericity

Red flags:

- “clarify” with no concrete help
- “improve flow” with no local diagnosis
- “add detail” with no indication of what is missing
- section-level commentary placed on the wrong paragraph
- many comments stacked onto adjacent paragraphs while other weak sections are ignored

### Suggested Revisions

Check:

- usefulness
- fluency
- faithfulness to original meaning
- naturalness
- relation to the triggering comment
- whether the rewrite actually solves the issue
- appropriate abstention when no safe local rewrite exists

Red flags:

- rewrite is generic or stilted
- rewrite adds unsupported scientific content
- rewrite is longer without becoming clearer
- rewrite does not match the triggering comment
- global conceptual issue forced into a fake local rewrite
- follow-up suggested-change blocks overwrite prior revision text destructively

### DOCX-native / Pre-Annotated DOCX

Check:

- source mode is `original_docx` for native DOCX input
- annotation state is recorded correctly
- existing comments are preserved when present
- new comments are added on top when warranted
- visible prior `[Suggested change]` blocks are not treated as normal manuscript prose during analysis
- suggested-change output does not silently no-op on pre-annotated input

No-op failure conditions:

- pre-annotated DOCX input had comments, but `new_comments_added_count == 0`
- pre-annotated suggested-change DOCX input had prior suggested blocks, but `new_suggested_change_blocks_added == 0`
- output exists but only preserves prior markup without adding meaningful new review state

### Final Reports

Check:

- manuscript-specificity
- consistency with comments
- consistency with suggested revisions
- section coverage
- absence of contamination from unrelated support material

## 7. Before/After Comparison Template

For each project fill in:

### Metadata

- baseline run id:
- new run id:
- mode:
- model stack:

### Quantitative fields

- comments before:
- comments after:
- suggested changes before:
- suggested changes after:
- applied before:
- applied after:
- generic-like comments before:
- generic-like comments after:
- section map before:
- section map after:

### Qualitative fields

- strongest improvement in section mapping:
- strongest improvement in comments:
- strongest improvement in suggested revisions:
- strongest abstention improvement:
- remaining weak example:

### Pass/fail judgment

- materially better:
- still blocked by:

Counts alone do not justify improvement. The qualitative fields are mandatory.

## 8. Pass/Fail Criteria

A run passes only if all of the following are true:

- artifacts exist
- artifacts were opened and read
- section mapping is at least as good as baseline and not more collapsed into `body`
- comments are not more generic than baseline
- suggested revisions are at least as useful as baseline
- no obvious bad forced rewrites dominate the suggested-changes DOCX

Trigger a targeted rerun if:

- a required artifact is missing
- validation JSON reports structural failure
- comments are obviously more generic than baseline
- suggested changes become sparser or less faithful
- DOCX-native runs report preserved old annotations but no new review activity

Trigger a targeted code fix if:

- section mapping still collapses meaningful content into `body`
- comments remain generic after localization
- rewrite gate is allowing clearly bad local rewrites
- abstention is failing on non-local/global issues

Block push if:

- full pytest is not green
- approved projects were not both rerun
- artifact reading was not completed
- before/after examples were not collected

## 9. Reporting Template

Use this exact report structure:

1. Project access guard results
2. Runs completed
3. Files changed in this follow-up
4. Before vs after findings on project 1
5. Before vs after findings on project 2
6. Concrete example improvements
7. Remaining weak examples
8. Tests run and results
9. Testing procedure markdown created
10. Remaining limitations
11. Exact commands I should run locally

Required evidence:

- at least 3 better comment examples per project
- at least 2 better suggested-revision examples per project
- at least 1 abstention or skip example that is better than a forced bad rewrite
- at least 1 section-mapping improvement example
- at least 1 remaining weak example

Required uncertainty wording:

- “materially better” only if artifacts support it
- “still weak” where comments or rewrites remain stiff or sparse
- “not proven” if the artifact evidence is incomplete

## 10. Common Failure Modes

- too many `body` section assignments
- front matter or PDF noise corrupting section state
- generic comments that sound like review boilerplate
- comment spread clustering on a few adjacent paragraphs
- sparse suggested changes despite visible local issues
- bad local rewrites with semantic drift
- no-op rewrites accepted as changes
- support-material contamination in final report
- validation artifacts missing even when the run completed
- tests green but outputs still weak

## 11. Commands Appendix

### Setup

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
Get-ChildItem -Name projects
python --version
python -m pytest --version
```

### Validation runs

```powershell
python -m ai_reviewer.cli review projects\20260325163524_test-existingphactorpaper\materials\manuscript\designing-chemical-reaction-arrays-using-phactor-and-chatgpt.pdf --project 20260325163524_test-existingphactorpaper --profile balanced
python -m ai_reviewer.cli deep-run --project 20260325163524_test-existingphactorpaper
python -m ai_reviewer.cli review projects\20260327051312_miniaturization_d2b\materials\manuscript\s44160-023-00351-1.pdf --project 20260327051312_miniaturization_d2b --profile balanced
python -m ai_reviewer.cli deep-run --project 20260327051312_miniaturization_d2b
```

### Tests

```powershell
python -m pytest tests/unit/test_suggested_changes.py -q
python -m pytest tests/unit/test_tools.py -q
python -m pytest tests/integration/test_pipeline.py tests/integration/test_deep_run.py -q
python -m pytest -q
```

### Artifact inspection

```powershell
Get-ChildItem projects\20260325163524_test-existingphactorpaper\runs
Get-ChildItem projects\20260327051312_miniaturization_d2b\runs
Get-Content projects\20260325163524_test-existingphactorpaper\runs\<RUN_ID>\final_deep_review_report.md
Get-Content projects\20260327051312_miniaturization_d2b\runs\<RUN_ID>\final_deep_review_report.md
Get-Content audits\docx_native_fixtures\generated\fixture_manifest.json
```

### Run comparison

Compare these files side by side between baseline and new runs:

- `section_map.json`
- `manuscript_comment_manifest.json`
- `manuscript_suggested_changes_manifest.json`
- `final_deep_review_report.md`
