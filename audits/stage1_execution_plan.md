# Stage 1 Execution Plan

Date: 2026-03-29

Purpose:
- Freeze the staged execution plan for prompts 2-10
- Keep implementation focused on the bottlenecks confirmed in `stage1_baseline_audit.md`

Non-goals for later stages:
- broad repo cleanup
- broad doc sweep before behavior changes are real
- unrelated feature work
- benchmark vanity work without artifact inspection

## Staged Plan Overview

### Stage 2
Goal:
- Fix comment localization and rewrite correctness in `ai_reviewer/review/manuscript_annotation.py`

Target outcomes:
- eliminate fake-identical rewrites
- eliminate truncated rewrites from deterministic fallback behavior
- eliminate obvious wrong-sentence rewrite substitution
- improve rhetorical-role classification for intro/background vs methods/results/discussion

Primary files:
- `ai_reviewer/review/manuscript_annotation.py`
- targeted tests under `tests/unit/`

Acceptance evidence:
- before/after examples on both approved projects
- tests for identical rewrite rejection
- tests for truncated rewrite rejection
- tests for wrong-sentence anchoring regression

### Stage 3
Goal:
- Rebuild suggested-revisions DOCX fidelity around original-text span replacement

Target outcomes:
- better span-faithful replacement
- stronger manifest provenance
- clearer validation of paragraph integrity and replacement locality

Primary files:
- `ai_reviewer/review/manuscript_annotation.py`
- `ai_reviewer/tools/docx_tools.py`

Acceptance evidence:
- source paragraph preserved outside revised spans
- no paragraph drift
- no wrong-sentence replacement
- strong validation artifacts

### Stage 4
Goal:
- Increase manuscript coverage and prove screening depth

Target outcomes:
- move from sparse issue sampling toward full-manuscript screening
- distinguish screened vs flagged vs commented vs rewritten
- emit explicit coverage artifacts

Primary files:
- `ai_reviewer/review/manuscript_annotation.py`
- `ai_reviewer/review/engine.py`
- possibly new review-depth artifacts

Acceptance evidence:
- per-section screening counts
- better comment spread
- explicit uncovered sections if any remain

### Stage 5
Goal:
- Improve final balanced/deep synthesis quality and make specialist QC gating real

Target outcomes:
- reduce summary-echo behavior
- strengthen manuscript-specific editorial judgment
- use QC scores as revision/gating inputs instead of passive diagnostics only

Primary files:
- `ai_reviewer/review/engine.py`
- `ai_reviewer/review/render.py`
- `ai_reviewer/review/rigorous_adapters.py`

Acceptance evidence:
- stronger report openings
- fewer abstract-like summaries
- higher specialist QC after revision loops

### Stage 6
Goal:
- Make native DOCX and pre-annotated DOCX paths trustworthy under re-review

Target outcomes:
- validate clean native DOCX
- validate DOCX with existing comments
- validate prior AI-Reviewer commented DOCX
- validate prior suggested-change style DOCX
- avoid silent no-op and reduce duplicate review noise

Primary files:
- `ai_reviewer/tools/docx_tools.py`
- `ai_reviewer/review/manuscript_annotation.py`
- fixture-generation/testing scripts

Acceptance evidence:
- synthetic fixture matrix
- preserved prior annotations
- meaningful new comments/revisions added
- no-op detection remains false on successful runs

### Stage 7
Goal:
- Strengthen verification semantics and support/citation honesty

Target outcomes:
- explicit verification categories
- cleaner separation between retrieval and actual support judgment
- better claim-support labeling in reports/artifacts

Primary files:
- `ai_reviewer/review/citation_fetcher.py`
- deep-run/report synthesis paths
- validation/reporting artifacts

Acceptance evidence:
- artifacts explicitly distinguish:
  - metadata found
  - support plausible
  - support not verified
  - needs human verification

### Stage 8
Goal:
- Strengthen deep-run and max-quality model routing

Target outcomes:
- stronger premium-stage routing
- clearer distinction between cheap prep models and premium editorial/arbitration models
- deeper stage accounting

Primary files:
- `ai_reviewer/review/deep_run.py`
- `ai_reviewer/models/selector.py`

Acceptance evidence:
- improved stage outputs
- explicit model-routing rationale
- stronger reconciliation/final arbitration quality

### Stage 9
Goal:
- Run broad validation on approved projects only

Target outcomes:
- balanced and deep runs on both approved projects
- native DOCX scenarios validated
- before/after evidence collected across comments, rewrites, reports, and DOCX artifacts

Primary artifacts:
- run directories under the two approved projects only
- audit markdowns with concrete examples

Acceptance evidence:
- multiple concrete before/after examples
- honest remaining-failure list

### Stage 10
Goal:
- Final stabilization, test sweep, small truth-aligned doc updates, commit, and push

Target outcomes:
- targeted tests green
- full pytest green
- minimal doc updates only where behavior truly changed
- final release note honest about remaining weaknesses

Primary files:
- changed code paths only
- minimal directly affected docs only

Acceptance evidence:
- clean final test run
- final audit summary
- commit and push

## Exact Priority Order

1. `manuscript_annotation.py`
2. `engine.py` and `render.py`
3. `docx_tools.py`
4. `citation_fetcher.py`
5. `deep_run.py`
6. `models/selector.py`

Reason:
- most of the currently visible quality failures originate in comment generation, rewrite generation, and rendering choices before they become citation-routing or deep-run-orchestration problems.

## Required Evidence For Later Stages

Every later stage should collect:
- at least one exact broken example before fix
- the concrete code path changed
- the exact artifact proving improvement
- the residual weakness still remaining

Mandatory evidence themes for later stages:
- comment usefulness
- rewrite correctness
- rewrite abstention correctness
- section/rhetorical-role correctness
- DOCX-native reliability
- truth/verification honesty
- report specificity

## Scope Guard

If a proposed later change does not clearly improve one of these bottlenecks, it is out of scope:
- comment quality
- rewrite quality
- coverage/screening depth
- report quality
- DOCX-native trust
- verification semantics
- max-quality routing

