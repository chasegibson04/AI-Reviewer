# DOCX-Native Analysis Note

## Scope

This note covers only native DOCX and pre-annotated DOCX handling.

## Current Behavior Before Fixes

- Source mode detection is extension-based only.
- `.docx` input is always classified as `original_docx`.
- Existing DOCX comments are counted during parsing, but they are not otherwise classified or used.
- Existing tracked-change style XML (`w:ins`, `w:del`) is not inspected.
- Existing visible AI-Reviewer suggestion blocks such as `[Suggested change] ...` are not treated as review artifacts during analysis.
- Comment and suggested-change generation operate on paragraph text as if the DOCX were clean.
- Validation confirms that the output DOCX opens and that comments exist, but it does not prove that new comments were added on top of pre-existing annotation state.

## Likely Failure Modes

### 1. False success on pre-commented DOCX

If the input DOCX already contains comments, current validation can still pass even if the run adds no meaningful new review state.

### 2. Review-artifact pollution of paragraph analysis

If the input DOCX already contains visible suggestion blocks from a prior run, those blocks are treated as ordinary paragraph text during:

- section mapping
- sentence harvesting
- comment localization
- rewrite generation

That can suppress or distort new review output.

### 3. No explicit policy for pre-annotated input

The code has no explicit product behavior for:

- collaborator comments
- editor comments
- prior AI-Reviewer comments
- prior AI-Reviewer suggested-change blocks
- mixed annotated DOCX states

### 4. No-op detection is too weak

Current artifacts do not clearly answer:

- how many comments existed before the run
- how many new comments were added
- whether old comments were preserved
- whether the run effectively did nothing

## Immediate Fix Direction

The DOCX-native path needs targeted changes in four places:

1. DOCX inspection:
   - detect existing comments
   - detect tracked-change XML
   - detect visible prior AI-Reviewer suggestion blocks
   - classify annotation state

2. Analysis normalization:
   - strip prior visible suggestion blocks from analysis text
   - keep raw DOCX content for output preservation

3. Validation:
   - distinguish existing vs new comments
   - detect silent no-op behavior on pre-annotated DOCX
   - record applied handling policy

4. Artifact clarity:
   - record source mode
   - record annotation state
   - record whether prior comments/suggestions were present
   - record whether they were preserved

