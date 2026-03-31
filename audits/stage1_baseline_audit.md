# Stage 1 Baseline Audit

Date: 2026-03-29

Scope:
- Baseline audit only
- Scope freeze only
- No broad implementation

Approved validation projects:
- `20260325163524_test-existingphactorpaper`
- `20260327051312_miniaturization_d2b`

Blacklist status:
- No horseshoe-crab project is present in the current `projects/` directory listing.
- Validation scope remains explicitly limited to the two approved projects above.

## What The System Claims To Do

From the current docs, config, and workflow descriptions, the system claims to provide:
- local-first manuscript review with `strict_offline: true` by default
- balanced review as the default single-pass path
- deep-run as a staged multi-pass path with specialist roles
- section-aware comments and suggested revisions attached to DOCX outputs
- native DOCX handling and PDF-surrogate handling
- optional stronger critique/arbitration stages using `llama3.3:70b-instruct-q4_K_M`
- optional citation retrieval with privacy-safe query shaping when not in strict offline mode

The docs are broadly aligned on these points:
- `README.md`
- `docs/ai_reviewer/WORKFLOW_MECHANICS.md`
- `docs/ai_reviewer/ARCHITECTURE.md`
- `docs/ai_reviewer/FULL_SYSTEM_REPORT_FOR_LLM.md`
- `docs/ai_reviewer/MODEL_SELECTION.md`
- `docs/ai_reviewer/orchestrator_design.md`
- `docs/ai_reviewer/PRIVACY_AUDIT.md`
- `docs/ai_reviewer/PROJECTS_AND_SLACK.md`
- `docs/ai_reviewer/SECURITY.md`
- `docs/ai_reviewer/TRAINING_MATERIALS.md`
- `docs/ai_reviewer/TROUBLESHOOTING.md`
- `docs/citation_fetch_methods.md`

## What The System Actually Does Right Now

Observed from current code and latest approved-project artifacts:

### 1. Review and deep-run both produce comments and suggested-change DOCX outputs

Evidence:
- Latest balanced review on project 1 native DOCX:
  - `projects/20260325163524_test-existingphactorpaper/runs/20260329_141227_review/001_project1_clean_native`
- Latest deep-run on project 1:
  - `projects/20260325163524_test-existingphactorpaper/runs/20260329_135834_deep_run`
- Latest balanced review on project 2:
  - `projects/20260327051312_miniaturization_d2b/runs/20260329_125225_review/001_s44160-023-00351-1`
- Latest deep-run on project 2:
  - `projects/20260327051312_miniaturization_d2b/runs/20260329_131502_deep_run`

The validation artifacts show:
- comments are attached
- suggested-change DOCX files open
- paragraph counts remain stable
- front matter and references are mostly preserved

### 2. Output quality is still below the target bar

The current artifacts show that the system works mechanically more often than before, but not well enough editorially.

Observed problems:
- balanced review reports still lead with long manuscript-summary text instead of a sharp editorial judgment
- specialist QC scores remain low
- suggested revisions still contain truncated, low-value rewrites
- section/rhetorical-role handling is improved but still brittle
- deep-run stage count is real, but depth is still shallow relative to the target ambition

### 3. Native DOCX handling exists, but trust is still incomplete

The DOCX path now records:
- source mode
- annotation state
- input/output annotation state in validation files
- existing comment counts
- suggested-block counts

This is a meaningful improvement over the earlier no-op risk, but current trust gaps remain:
- not enough end-to-end evidence on pre-annotated DOCX re-review quality
- current policy is clearer than current behavior quality
- preservation and layering are better tracked than they are editorially validated

### 4. Citation retrieval is still limited in practical depth

The system now includes fallback methods in `citation_fetcher.py`:
- `doi_open_access_apis`
- `crossref_lookup_then_oa`
- `local_project_pdf_match`
- `crossref_short_title_then_oa`

This is better than the earlier narrower path, but truth-checking is still mostly:
- metadata retrieval
- open-access paper discovery
- support-material selection

It is not yet a strong claim-verification system.

### 5. Manifest/report contracts are inconsistent enough to slow validation

Observed artifact inconsistency:
- `commented_docx_validation.json` reports nonzero attached comments
- `manuscript_comment_manifest.json` stores comment metadata under `comment_targets`, not a top-level `comments` list
- balanced review reports are present at top level and under `reports/`
- deep-run final report naming differs from balanced review naming

These are not fatal, but they make auditing slower and less reliable than necessary.

## Evidence From Current Approved-Project Outputs

### Project 1: `20260325163524_test-existingphactorpaper`

Latest balanced native DOCX review:
- run: `20260329_141227_review/001_project1_clean_native`
- profile/model: `balanced` / `gemma3:27b`
- duration: about `59.6s`
- validation:
  - `comment_count = 11`
  - `comments_attached = true`
  - `body_text_unchanged = true`
  - `changes_proposed = 9`
  - `changes_applied = 9`

Latest deep-run:
- run: `20260329_135834_deep_run`
- stage stack includes:
  - triage `phi4-mini:latest`
  - synthesis/digestion `mistral-small3.2:latest`
  - critique stages `llama3.3:70b-instruct-q4_K_M`
  - reconciliation `qwen2.5:7b-instruct`
- validation:
  - `comment_count = 11`
  - `comment_ranges_detected = 11`
  - `changes_proposed = 11`
  - `changes_applied = 10`
  - `structure_intact = true`

Observed quality issues in current project 1 artifacts:
- the rendered review report still reads too much like an abstract/executive summary echo
- suggested changes are structurally intact but still sparse relative to total manuscript coverage
- the rewrite generator still depends heavily on deterministic truncating fallback behavior

### Project 2: `20260327051312_miniaturization_d2b`

Latest balanced review:
- run: `20260329_125225_review/001_s44160-023-00351-1`
- profile/model: `balanced` / `gemma3:27b`
- duration: about `84.3s`
- validation:
  - `comment_count = 11`
  - `comments_attached = true`
  - `changes_proposed = 9`
  - `changes_applied = 9`

Latest deep-run:
- run: `20260329_131502_deep_run`
- validation:
  - `comment_count = 11`
  - `comment_ranges_detected = 11`
  - `changes_proposed = 11`
  - `changes_applied = 8`
  - `structure_intact = true`

Observed quality issues in current project 2 artifacts:
- manifest examples still show truncated suggested rewrites such as a sentence cut off after “available to.”
- rhetorical-role misclassification remains visible in introduction/context sentences being treated as if they were methods-compression problems
- current specialist QC remains low:
  - section specificity around `2.0`
  - rigor around `1.3` to `2.4`
  - overall around `2.06` to `2.40`

## Top 5 Output-Quality Bottlenecks

1. Rewrite generation still uses a truncation-prone deterministic fallback
- `_rewrite_candidate()` in `manuscript_annotation.py` truncates by clause count or word count.
- This directly explains broken or fake-helpful proposed edits.

2. Comment generation is still too heuristic and too sentence-pattern-driven
- `_build_sentence_level_candidates()` relies on hand-written triggers.
- This improves localization somewhat, but it is still too shallow for manuscript-wide editorial coverage.

3. Final balanced review report is still too summary-first
- `render_markdown()` renders `review.summary` as both Executive Summary and Summary.
- Current reports therefore over-amplify abstract-like summary text and under-amplify manuscript-specific judgment.

4. Specialist QC is descriptive, not gating
- `build_specialist_qc_summary()` scores the output but does not force revision loops.
- Current low scores become diagnostics, not quality gates.

5. Coverage is still comment-limited rather than screening-driven
- The current comment path emphasizes producing a bounded number of comments.
- It does not yet prove that the full manuscript was screened sentence-by-sentence before pruning.

## Top 5 Truth / Verification Bottlenecks

1. Citation retrieval is not claim verification
- The current system can find papers and metadata.
- It still cannot robustly verify that a cited reference supports a specific manuscript claim.

2. Strict-offline default suppresses external verification entirely
- This is a valid privacy default.
- It also means many runs have no external evidence check at all unless explicitly configured otherwise.

3. Support-material linkage is still mostly lexical
- The current selection logic is overlap-driven.
- That is useful, but not strong evidence reasoning.

4. Deep-run methods/citation stages are distinct in name more than in proof burden
- The stage files exist, but the artifacts do not yet demonstrate strong claim-by-claim verification outputs.

5. Verification labels are still weaker than desired product semantics
- The current system does not yet consistently emit explicit categories such as:
  - citation exists
  - metadata match likely
  - support relationship plausible
  - support relationship not verified
  - needs human verification

## Top 5 DOCX-Native Bottlenecks

1. Native DOCX trust is stronger on preservation than on editorial usefulness
- The system can preserve structure and layer annotations.
- It still needs stronger proof that the new comments/revisions are useful on already annotated DOCX.

2. Visible prior suggestion blocks are handled, but re-review quality remains lightly validated
- `normalize_review_artifact_text()` removes visible suggestion markers for analysis.
- That helps prevent pollution, but it does not guarantee strong second-round editorial behavior.

3. Existing comments are counted and preserved, but duplication avoidance is still weak
- Annotation state is detected.
- The system does not yet demonstrate strong semantic deduplication against prior comments.

4. Artifact contracts for DOCX-native review are not yet uniform
- Deep-run and balanced review emit similar but not identical layouts and schemas.
- This slows validation and increases audit ambiguity.

5. Comment anchoring still needs stronger traceability and stricter validation
- Anchors are present in comment targets.
- Suggested-change manifests still need clearer span-faithfulness and easier auditability.

## Code Hotspot Findings

### `ai_reviewer/review/manuscript_annotation.py`
- This is the main output-quality hotspot.
- It currently owns:
  - source-mode detection
  - section mapping
  - sentence-level candidate harvesting
  - rewrite generation
  - rewrite verification
  - suggested-change DOCX production
- The biggest immediate weaknesses are here.

### `ai_reviewer/review/deep_run.py`
- Deep-run is genuinely staged.
- Current weakness is not “no stages.”
- Current weakness is that stage depth and stage outputs are still not strong enough to justify the target quality bar.

### `ai_reviewer/review/engine.py`
- The main single-pass review path still prioritizes schema completion and bundle rendering over deep editorial iteration.
- The report renderer also reinforces summary-heavy output.

### `ai_reviewer/tools/docx_tools.py`
- DOCX inspection and preservation are materially better than before.
- Remaining weaknesses are re-review semantics, deduplication, and clearer artifact contracts.

### `ai_reviewer/review/citation_fetcher.py`
- Retrieval fallback coverage is improved.
- Verification semantics remain shallow.

### `ai_reviewer/models/selector.py`
- Current routing is practical, but not yet explicitly optimized for a true max-quality editorial mode.
- Mac-aware routing exists, but quality-first stage routing is still conservative.

## Scope Freeze For Stages 2-10

Stage 1 conclusion:
- The next work should not start with a broad docs sweep.
- The next work should not start with general architecture refactoring.
- The next work should focus first on output-quality and rewrite correctness in `manuscript_annotation.py`, then on report synthesis/gating, then on DOCX-native re-review quality, then on verification semantics and model routing.

Frozen priority order:
1. comment quality and rewrite correctness
2. suggested-revisions DOCX fidelity
3. coverage and screening depth
4. final synthesis quality gates
5. DOCX-native and pre-annotated DOCX trust
6. verification semantics and citation/support checking
7. max-quality model routing and deep-run strengthening

