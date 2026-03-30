# Stage 9 Validation Report

## Scope

Stage 9 was validation-only. No broad implementation work was done. One tiny fix was applied after validation exposed a stale test unpack in `tests/unit/test_support_filtering.py`.

Approved projects only:

- `20260325163524_test-existingphactorpaper`
- `20260327051312_miniaturization_d2b`

The horseshoe crab project was not opened or used.

## Validation Matrix Completed

### Core review and deep-run evidence

Existing stage artifacts used as baseline/final evidence:

- Stage 2 section mapping: `audits/stage2_section_mapping_report.md`
- Stage 3 comment quality: `audits/stage3_comment_quality_report.md`
- Stage 4 suggested revisions: `audits/stage4_suggested_revisions_report.md`
- Stage 5 DOCX-native matrix: `audits/stage5_docx_native_matrix/matrix_results.json`
- Stage 6 verification: `audits/stage6_validation/summary.json`
- Stage 7 max-quality benchmark: `audits/stage7_benchmark/summary.json`
- Stage 8 figure/context benchmark: `audits/stage8_optional_layer_benchmark/summary.json`

Balanced/core and deep/rigorous runs inspected for both approved projects:

- Project 1 baseline deep: `projects/20260325163524_test-existingphactorpaper/runs/20260329_135834_deep_run`
- Project 1 improved deep: `projects/20260325163524_test-existingphactorpaper/runs/20260329_165523_deep_run`
- Project 2 baseline review: `projects/20260327051312_miniaturization_d2b/runs/20260329_125225_review/001_s44160-023-00351-1`
- Project 2 baseline deep: `projects/20260327051312_miniaturization_d2b/runs/20260329_131502_deep_run`
- Project 2 improved deep: `projects/20260327051312_miniaturization_d2b/runs/20260329_165523_deep_run`

### DOCX-native scenarios

Used Stage 5 full fixture matrix evidence:

- clean native DOCX
- commented light DOCX
- commented heavy DOCX
- prior AI-commented DOCX
- prior AI-suggested DOCX

for both approved projects.

Result summary from `audits/stage5_docx_native_matrix/matrix_results.json`:

- 10 fixture cases validated
- 10/10 showed `comment_meaningful_new_state=true`
- 10/10 showed `suggested_meaningful_new_state=true`
- no silent no-op case remained in the validated matrix

### Support-material ON/OFF

Support OFF direct-input review run executed:

- `audits/stage9_validation/project1_support_off/20260329_232001_review/001_designing-chemical-reaction-arrays-using-phactor-and-chatgpt`

Evidence:

- direct input path with no `--project`
- no `support_material_filtering.json` emitted
- run still completed and produced manuscript outputs

Support ON evidence reused from project-scoped deep/review runs:

- Project 1 deep: selected 9 support files, skipped 5
- Project 2 deep: selected 2 support files, skipped 0
- explicit provenance/verification labels present in Stage 6 artifacts

### Strict-offline OFF/ON

Strict-offline ON evidence:

- Stage 6 validation artifacts with explicit offline behavior
- direct support-OFF run used `AI_REVIEWER_STRICT_OFFLINE=true`

Safe-online ON review run executed:

- `projects/20260327051312_miniaturization_d2b/runs/20260329_232001_review`

Evidence:

- `artifacts/citation_fetch_report.json` present
- query policy recorded:
  - `no_manuscript_raw_text=true`
  - `no_long_manuscript_excerpts=true`
  - `no_support_paper_full_text=true`
  - query logging limited to type and length only
- 94 references processed with metadata-only verification labels

### Figure OFF/ON

Used Stage 8 controlled benchmark:

- Project 1 OFF specialist score: `2.26`
- Project 1 ON specialist score: `2.16`
- Project 2 OFF specialist score: `2.17`
- Project 2 ON specialist score: `1.96`

Conclusion:

- figure review currently adds caption-extraction noise more often than useful critique on these approved PDFs
- keep OFF by default

### Context-pack OFF/ON

Used Stage 8 controlled benchmark:

- both projects gained one concrete compliance finding with context pack ON:
  - `Context-pack required item may be missing: limitations_statement.`
- finding propagated into final weaknesses/actions without distorting the rest of the review

Conclusion:

- useful as opt-in, not as default

## Before vs After Summary

### Project 1

Section mapping:

- before: `body=4`, `introduction=2`, `methods=12`, `results=45`
- after: `body=0`, `introduction=7`, `methods=4`, `results=53`

Comments:

- before: 11 comments with issue mix including redundant methods comments
- after: 10 comments, with redundant methods/reference filler removed and more specific framing/results comments

Suggested revisions:

- before: broad fallbacks could still apply broken local rewrites
- after: 10 proposed, 9 applied, 1 correctly skipped for `scope_drift`

Final report quality:

- still fallback-generated and still too generic in places
- but now grounded in better section mapping, stronger comments, and stricter rewrite abstention

### Project 2

Section mapping:

- before: `body=2`, `front_matter=64`, `introduction=4`, `methods=19`, `results=27`
- after: `body=0`, `front_matter=39`, `introduction=44`, `methods=12`, `results=23`, `discussion=1`

Comments:

- before: 11 comments dominated by generic clarity phrasing
- after: 11 comments with better overclaim detection and methods/result-localized diagnostics

Suggested revisions:

- before: weak/truncated fallbacks still leaked through
- after: 11 proposed, 7 applied, 4 skipped; malformed spans now abstain instead of forcing junk

Final report quality:

- still fallback-generated and still too general at synthesis level
- compliance/context-pack layer adds one concrete requirement without obvious distortion

## Concrete Example Improvements

### Comments

Project 1:

- before: `This sentence compresses too many procedural details into one unit.`
- after: `This sentence is carrying both background and the paper-specific turn.`

Project 1:

- before: `This sentence compresses too many procedural details into one unit.`
- after: `This results sentence mixes the outcome with too much setup detail.`

Project 2:

- before: `With reaction miniaturization..., less starting material is needed...` was treated as generic clarity/procedural compression
- after: early miniaturization framing is mapped into introduction and comments target scope/claim framing instead of fake procedure compression

Project 2:

- before: methods comments read like generic flow edits
- after: `This methods sentence names the action but not the exact interpretive boundary the reader needs.`

### Suggested revisions

Project 1:

- one prior bad intro fallback is now skipped with `scope_drift`
- accepted rewrites remain local and tracked by target section/span strategy

Project 2:

- malformed `Fig.`-truncated targets now skip with `unbalanced_parentheses`
- unsupported method assumptions now skip instead of being applied

## Remaining Weak Examples

- Balanced review reports are still too generic and memo-like, especially in direct PDF runs.
- Deep-run final synthesis still depends on deterministic fallback because reconciliation/final arbitration schema compliance is weak.
- Comment manifests across older/newer runs are not schema-uniform enough for fast audit automation.
- Figure review remains text-only and is not currently a quality win on the approved PDFs.
- Suggested-revision DOCX is still visible suggestion-block markup, not native Word track changes.

## Full Pytest Evidence

Executed:

```powershell
python -m pytest -q
```

Result:

- `147 passed in 84.03s`

Tiny fix required after validation:

- `tests/unit/test_support_filtering.py` updated to match current 3-tuple return from `_filter_support_docs_for_grounding()`.

## Artifacts To Read First

- `audits/stage5_docx_native_matrix/matrix_results.json`
- `audits/stage6_validation/summary.json`
- `audits/stage7_benchmark/summary.json`
- `audits/stage8_optional_layer_benchmark/summary.json`
- `audits/stage9_validation/project1_support_off/20260329_232001_review/001_designing-chemical-reaction-arrays-using-phactor-and-chatgpt/review_report.md`
- `projects/20260327051312_miniaturization_d2b/runs/20260329_232001_review/artifacts/citation_fetch_report.json`
