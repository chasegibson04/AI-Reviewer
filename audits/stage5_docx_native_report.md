# Stage 5 DOCX-Native Report

## Scope

- native DOCX and pre-annotated DOCX reliability only
- approved projects only: `20260325163524_test-existingphactorpaper`, `20260327051312_miniaturization_d2b`

## DOCX-native findings

- `original_docx` source mode detection is working for clean native, commented, and prior AI-annotated DOCX.
- Existing DOCX comments and visible `[Suggested change]` blocks are detected and preserved.
- Visible suggested-change blocks are stripped from analysis text before paragraph scoring and comment localization.
- Validation now distinguishes preserved prior markup from meaningful new review state.
- The key regression fixed in this stage was silent pass-through on pre-annotated input: pre-annotated input is now flagged as suspicious when no new AI review state is added.

## Intended behavior for pre-annotated DOCX

- preserve existing DOCX comments
- preserve visible suggested-change blocks
- strip visible suggested-change blocks from analysis text
- add new AI-Reviewer comments on top rather than replacing old ones
- append new suggested changes as follow-up blocks when prior suggested blocks already exist
- do not yet dedupe semantically against prior comments
- do not yet summarize prior comments as model context
- flag pre-annotated runs as `silent_noop_suspected` when no meaningful new review state is added

## Synthetic DOCX fixtures

- Fixture manifest: `audits/docx_native_fixtures/generated/fixture_manifest.json`
- 20260325163524_test-existingphactorpaper: `clean_native`, `commented_light`, `commented_heavy`, `prior_ai_commented`, `prior_ai_suggested`
- 20260327051312_miniaturization_d2b: `clean_native`, `commented_light`, `commented_heavy`, `prior_ai_commented`, `prior_ai_suggested`

## Validation matrix summary

- `20260325163524_test-existingphactorpaper` / `clean_native`: annotation=`clean_native_docx`, new_ai_comments=`20`, comment_noop=`False`, new_suggested_blocks=`4`, suggested_noop=`False`
- `20260325163524_test-existingphactorpaper` / `commented_light`: annotation=`docx_with_existing_comments`, new_ai_comments=`20`, comment_noop=`False`, new_suggested_blocks=`4`, suggested_noop=`False`
- `20260325163524_test-existingphactorpaper` / `commented_heavy`: annotation=`docx_with_existing_comments`, new_ai_comments=`20`, comment_noop=`False`, new_suggested_blocks=`4`, suggested_noop=`False`
- `20260325163524_test-existingphactorpaper` / `prior_ai_commented`: annotation=`prior_ai_reviewer_annotated_docx`, new_ai_comments=`20`, comment_noop=`False`, new_suggested_blocks=`4`, suggested_noop=`False`
- `20260325163524_test-existingphactorpaper` / `prior_ai_suggested`: annotation=`prior_ai_reviewer_annotated_docx`, new_ai_comments=`20`, comment_noop=`False`, new_suggested_blocks=`2`, suggested_noop=`False`
- `20260327051312_miniaturization_d2b` / `clean_native`: annotation=`clean_native_docx`, new_ai_comments=`22`, comment_noop=`False`, new_suggested_blocks=`1`, suggested_noop=`False`
- `20260327051312_miniaturization_d2b` / `commented_light`: annotation=`docx_with_existing_comments`, new_ai_comments=`22`, comment_noop=`False`, new_suggested_blocks=`1`, suggested_noop=`False`
- `20260327051312_miniaturization_d2b` / `commented_heavy`: annotation=`docx_with_existing_comments`, new_ai_comments=`22`, comment_noop=`False`, new_suggested_blocks=`1`, suggested_noop=`False`
- `20260327051312_miniaturization_d2b` / `prior_ai_commented`: annotation=`prior_ai_reviewer_annotated_docx`, new_ai_comments=`22`, comment_noop=`False`, new_suggested_blocks=`1`, suggested_noop=`False`
- `20260327051312_miniaturization_d2b` / `prior_ai_suggested`: annotation=`prior_ai_reviewer_annotated_docx`, new_ai_comments=`22`, comment_noop=`False`, new_suggested_blocks=`1`, suggested_noop=`False`

## Material fixes

- Native DOCX validation now records `new_ai_reviewer_comments_added_count` and `meaningful_new_review_state`.
- Suggested-change validation now records `new_suggested_change_blocks_added` and `meaningful_new_review_state`.
- Pre-annotated policy is emitted into `source_mode.json` and returned from the annotation builder.
- Fixture generation now prefers real managed native DOCX instead of surrogate base DOCX for `clean_native`.
- Heading detection now recognizes plain DOCX section headings like `Discussion`, which prevents fallback comments from being anchored to heading paragraphs.
- Suggested-change generation can now use deterministic span-faithful fallback when no rewrite provider is present and the target is still safely rewriteable.
- Unit coverage now distinguishes two valid pre-suggested outcomes: follow-up suggestion added when safe, and explicit no-op suspicion when no safe local rewrite exists.

## Remaining weaknesses

- Semantic deduplication against prior human comments is still disabled, so re-review can add overlapping comments.
- Suggested-change output is still visible block markup, not native Word track changes.
- Very short pre-suggested sentences may still correctly abstain, so some pre-suggested inputs will remain `silent_noop_suspected` unless a safe local rewrite exists.
- The direct Stage 5 matrix used the real parser and annotation builder rather than the full model-driven review stack, because the goal here was DOCX-native path reliability, not review quality.