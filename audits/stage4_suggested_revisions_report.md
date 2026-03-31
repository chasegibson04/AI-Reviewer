# Stage 4 Suggested Revisions Report

## Scope

- Stage: 4 of 10
- Focus: suggested-revisions DOCX quality only
- Approved projects only:
  - `20260325163524_test-existingphactorpaper`
  - `20260327051312_miniaturization_d2b`

## Audit Summary

The previous rewrite path had three core problems:

- rewrite grouping was paragraph-level rather than span-level in practice
- fallback rewrites were too willing to rescue low-quality model output
- manifests did not make acceptance vs abstention decisions clear enough

That combination let low-trust rewrites through:

- truncated or malformed fallback edits
- assumption-heavy method rewrites
- weak paragraph-wide rewrites when only one sentence needed attention

## Changes Made

### 1. Span-grouped rewrite generation

- Rewrites are now grouped by local target span within each paragraph instead of forcing all paragraph comments into one combined rewrite request.
- Each manifest entry now records:
  - `target_paragraph_index`
  - `target_section`
  - `target_span`
  - `issue_types`
  - `rewrite_strategy`
  - `verification`

### 2. Stronger span-level rewrite checks

- Added local span checks for:
  - editorial meta text
  - incomplete phrase endings
  - punctuation incompleteness
  - unbalanced parentheses/brackets
  - scope drift
  - weak span overlap

### 3. Stronger verifier gating

- Verifier output now fails if it reports:
  - awkwardness
  - mechanical wording
  - meaning drift
  - unsupported additions
  - assumptions not present in the source
  - incomplete/truncated output
- Score thresholds are stricter for:
  - fluency
  - faithfulness
  - alignment

### 4. Safer fallback policy

- Deterministic fallback is now limited to genuinely local cases:
  - one sentence only
  - not too long
  - not overloaded with commas
  - balanced punctuation
  - not obviously truncated figure/caption spans
- If a local fallback is not safe, the system abstains.

## Tests Added

- `test_suggested_changes_rejects_awkward_rewrite_without_safe_fallback`
- `test_suggested_changes_rejects_low_faithfulness_without_fallback`
- `test_suggested_changes_rejects_unsupported_addition_without_safe_fallback`
- `test_suggested_changes_splits_multiple_local_targets_in_one_paragraph`

Existing relevant tests retained:

- global issue abstention
- rewrite repair path
- numeric-loss rejection
- markdown-heading rejection
- localized structure rewrite acceptance
- unsupported-addition fallback when safe

## Test Runs

- `python -m pytest tests/unit/test_suggested_changes.py -q`
- `python -m pytest tests/unit/test_tools.py -q`

Result:

- `31 passed`

## Approved Project Reruns Used For Final Comparison

### Project 1

- Baseline: `20260329_154847_deep_run`
- Final stage 4 run: `20260329_165523_deep_run`

### Project 2

- Baseline: `20260329_160215_deep_run`
- Final stage 4 run: `20260329_165523_deep_run`

## Before/After Findings

### Project 1

- Before:
  - `10/10` proposed rewrites applied
  - no abstention
  - weak paragraph-wide intro rewrite passed
- After:
  - `9/10` applied
  - `1` abstention
  - the bad introduction fallback was rejected with `scope_drift`

Useful rewrite examples:

1. Abstract calibration
   - Before: broad sentence preserved as a full-paragraph rewrite.
   - After: local claim calibration changed `modest to excellent` to `modest to high` and `first attempt` to `initial screen`.

2. Results sentence on Well D5
   - Before: full-paragraph rewrite existed, but provenance was weak.
   - After: anchored target span is explicit and the rewrite cleanly splits outcome from reagent detail.

3. Results sentence on array performance
   - Before: broad paragraph rewrite with no span provenance.
   - After: anchored sentence is revised to `performed better ... in the tested set`, which directly addresses the overclaim.

4. Results sentence on phactor input quality
   - Before: `served as effective input ... in our tested case`, with weak provenance.
   - After: explicit span-level claim calibration to `tested combinations`, accepted only via claim-calibration fallback.

5. Discussion interface integration sentence
   - Before: paragraph-wide rewrite only.
   - After: localized structure fallback splits the overloaded opening sentence into two shorter sentences.

Correct abstention:

- Introduction paragraph 10
  - Final skip reason: `scope_drift`
  - This is correct because the earlier fallback produced a broken, over-broad local rewrite.

### Project 2

- Before:
  - `11/12` applied
  - only `1` abstention
  - malformed or assumption-heavy rewrites still slipped through
- After:
  - `7/11` applied
  - `4` abstentions
  - fewer rewrites, but materially cleaner and more defensible

Useful rewrite examples:

1. Introductory efficiency/greenness claim
   - Before: generalized to `in our tested case`.
   - After: `increased ... in the tested set of reactions`, which is tighter and more natural.

2. Introductory solvent claim
   - Before: generic calibration.
   - After: `in our tested reactions ... favored high-boiling solvents`, which is clearly bounded to the actual study.

3. Results sentence on multistep synthesis outcome
   - Before: paragraph-wide rewrite with weaker targeting.
   - After: the revised paragraph leads with the isolated result and keeps the procedural clause afterward.

4. Discussion sentence on medicinal-chemist toolbox reactions
   - Before: general importance statement.
   - After: ties the claim to the demonstrated two-step synthesis of 21 target compounds.

5. Methods catalyst-loading sentence
   - Before: some methods rewrites were malformed or skipped.
   - After: the accepted rewrite adds a precise relation for `10 mol% relative to the aryl informer`, which is local and faithful.

Correct abstentions:

1. Paragraph 36
   - Skip reason: `unbalanced_parentheses`
   - Correct because the target span ends in malformed figure-linked syntax and is not safe for deterministic local rewrite.

2. Paragraph 82
   - Skip reason: `verifier_issue_flag`
   - Correct because the model introduced new process details such as pH and dissolution state that were not present in the source.

3. Paragraph 38
   - Skip reason: `unbalanced_parentheses`
   - Correct because the target span is truncated at `Fig.` and any local rewrite would be unreliable.

## Net Judgment

- The suggested-revisions path is more trustworthy than the stage 3 baseline.
- The strongest improvements are:
  - span-level provenance
  - stronger abstention
  - fewer malformed fallbacks
  - fewer assumption-heavy methods rewrites

This pass improved usefulness by rejecting weak rewrites rather than inflating the applied count.

## Remaining Weaknesses

- Some accepted rewrites are still paragraph-level replacements around a local sentence rather than true in-place sentence substitutions.
- British vs American spelling consistency is still not enforced in rewrite acceptance.
- A few accepted rewrites are still more explanatory than elegant.
- The DOCX rendering is still a visible suggested-block format, not true track changes.
