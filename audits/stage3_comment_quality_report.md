# Stage 3 Comment Quality Report

## Scope

- Stage: 3 of 10
- Focus: comment quality only
- Approved projects only:
  - `20260325163524_test-existingphactorpaper`
  - `20260327051312_miniaturization_d2b`
- Horseshoe crab was not inspected or used.

## Code Path Audited

- `ai_reviewer/review/manuscript_annotation.py`
  - candidate harvesting
  - span localization
  - enrichment
  - filtering
  - balancing

## Changes Made

### 1. Stronger comment revision before filtering

- Added a deterministic revision pass that rewrites raw comment entries into:
  - section-aware critiques
  - issue-aware suggestion language
  - rationale text tied to the quoted anchor and local cues
- Replaced low-value `Proposed edit:` fragments with `Suggested wording direction:` guidance in the revised comments.

### 2. Stronger generic-comment rejection

- Expanded generic-pattern rejection for comments that say little more than:
  - clarify
  - add more detail
  - improve flow
  - expand this section
  - provide more discussion
- Tightened quality checks so comments now fail if they:
  - lack a meaningful anchor
  - do not lexically connect to the anchor/paragraph
  - contain weak suggestion text
  - read like section-level filler pasted onto a local sentence

### 3. Stronger local grounding

- Comment rationale now explicitly reflects:
  - quoted sentence anchor
  - local lexical cues
  - current section
  - sentence-level vs section-level treatment
- Critiques now vary by section:
  - introduction comments emphasize framing and transition
  - methods comments emphasize condition/criterion/scope boundary
  - results comments emphasize outcome-first reporting
  - discussion comments emphasize evidence boundary and interpretation scope

### 4. Duplicate suppression

- Added deduplication keyed on:
  - paragraph
  - issue group
  - anchor signature
- This removed repeated low-value comments on near-identical method bullets.

## Tests Added

- `test_comment_quality_gate_rejects_generic_section_filler`
- `test_revise_comment_entries_makes_local_intro_comment`
- `test_revise_comment_entries_varies_by_section_style`
- `test_dedupe_comment_entries_suppresses_duplicate_anchor_issue`

## Test Runs

- `python -m pytest tests/unit/test_suggested_changes.py -q`
- `python -m pytest tests/unit/test_tools.py -q`

Result:

- `27 passed`

## Approved-Project Reruns

- Project 1 deep-run:
  - baseline: `20260329_144913_deep_run`
  - stage 3 rerun: `20260329_154847_deep_run`
- Project 2 deep-run:
  - baseline: `20260329_151655_deep_run`
  - stage 3 rerun: `20260329_160215_deep_run`

## Before/After Findings

### Project 1

- Comment count dropped from `12` to `10`.
- The drop is good here:
  - one duplicated methods comment was suppressed
  - one nonsense redundancy comment anchored to a reference entry disappeared
- Broken `Proposed edit:` fragments were replaced by anchored wording guidance.

Examples:

1. Abstract overclaim
   - Before: generic narrowing instruction plus an identical proposed edit.
   - After: asks for the tested case or measured outcome explicitly and removes the fake rewrite.

2. Introduction framing
   - Before: generic “doing too much at once” critique with a truncated proposed edit.
   - After: explicitly tells the author to separate field context from this paper’s contribution.

3. Results sentence with heavy setup
   - Before: “split the action from the purpose” plus a truncated reagent-list rewrite.
   - After: tells the author to lead with the observed result and move conditions to a follow-on sentence.

4. Discussion interpretation
   - Before: broad “state the exact outcome or narrow the scope” language.
   - After: asks for a sharper scope boundary while keeping the interpretation tied to paper-specific evidence.

5. Rejected bad comment
   - Before: paragraph 150 received a redundancy comment on a reference entry with unrelated suggested text.
   - After: that comment is gone.

### Project 2

- Comment count remained `12`, but the comments are materially stronger.
- The main improvement is quality, not quantity:
  - truncated rewrites were removed
  - section-specific guidance replaced generic critique text
  - the prior bad redundancy comment disappeared

Examples:

1. Introduction background sentence
   - Before: generic clarity note with a truncated proposed edit.
   - After: directs the author to separate field context from the manuscript-specific turn.

2. Introductory claim on efficiency/greenness
   - Before: generic “narrow the claim” phrasing.
   - After: still flags overclaim, but now asks for the tested case, condition, or readout directly.

3. Results parameter-analysis sentence
   - Before: truncated rewrite of the first clause.
   - After: tells the author to lead with the observed result and move the comparison detail later.

4. Methods dosing sentence
   - Before: “split the action from the purpose” even though this is a procedural sentence.
   - After: asks for the exact condition, criterion, or scope boundary controlling the step.

5. Rejected bad comment
   - Before: paragraph 74 got a redundancy comment that suggested unrelated text from another sentence.
   - After: that bad comment is gone and replaced by a grounded interpretation-scope critique.

## Net Judgment

- Stage 3 materially improved comment usefulness.
- The clearest wins are:
  - removal of fake `Proposed edit:` fragments from kept comments
  - stronger section-aware phrasing
  - better rationale grounding
  - duplicate suppression
  - rejection of obviously bad generic/reference-noise comments

## Remaining Weaknesses

- The revised comments are more useful, but some still lean on reusable wording patterns for:
  - overclaim calibration
  - methods scope-boundary comments
- The current system is better at producing actionable direction than line-level replacement wording.
- Rewrite quality itself is still a later-stage problem and remains intentionally out of scope for this pass.
