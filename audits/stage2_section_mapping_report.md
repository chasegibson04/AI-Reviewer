# Stage 2 Section Mapping Report

Date: 2026-03-29

Scope:
- section mapping only
- comment spread only
- no rewrite-quality rebuild beyond section/anchor dependency

Approved projects used:
- `20260325163524_test-existingphactorpaper`
- `20260327051312_miniaturization_d2b`

## What Changed

Updated file:
- `ai_reviewer/review/manuscript_annotation.py`

Targeted changes:
- tightened front-matter detection for:
  - file-slug bleed
  - affiliation/address blocks
  - `Cite This` blocks
  - email/address metadata
- tightened header/footer detection so long merged-content paragraphs are less likely to be mistaken for running headers
- removed overly broad `article` substring matching that was poisoning normal content classification
- added stronger content-based section hints for:
  - introduction/background framing
  - methods/procedure
  - results
  - discussion/conclusion
- added repair logic so substantive pre-methods paragraphs can recover into `introduction` instead of staying stuck in `front_matter`
- added round-robin comment balancing across sections instead of simple greedy accumulation

## Tests Added

Added to `tests/unit/test_suggested_changes.py`:
- `test_section_lookup_keeps_front_matter_from_poisoning_intro`
- `test_section_lookup_recovers_miniaturization_intro_transition`
- `test_section_lookup_preserves_long_body_paragraph_with_merged_page_noise`
- `test_balance_comment_entries_spreads_across_sections`

Existing relevant test retained:
- `test_section_lookup_keeps_methods_and_introduction_despite_pdf_noise`

## Before / After Summary

### Project 1 deep-run

Before:
- run: `20260329_135834_deep_run`
- section counts:
  - `body=4`
  - `front_matter=58`
  - `introduction=2`
  - `methods=12`
  - `results=45`
  - `discussion=6`
  - `conclusions=1`
- comment spread:
  - `abstract=1`
  - `methods=4`
  - `results=4`
  - `discussion=2`

After:
- run: `20260329_144913_deep_run`
- section counts:
  - `front_matter=51`
  - `header_footer=28`
  - `abstract=1`
  - `introduction=7`
  - `methods=4`
  - `results=56`
  - `discussion=7`
  - `conclusions=1`
- comment spread:
  - `abstract=1`
  - `introduction=2`
  - `methods=3`
  - `results=4`
  - `discussion=2`

Material improvements:
- the main introduction paragraph is no longer mislabeled as `methods`
- title/citation noise is moved out of active scientific sections
- comments now reach `introduction` instead of clustering only in methods/results/discussion

### Project 2 miniaturization PDF review

Before:
- run: `20260329_125225_review/001_s44160-023-00351-1`
- section counts:
  - `body=2`
  - `front_matter=64`
  - `header_footer=45`
  - `introduction=4`
  - `methods=19`
  - `results=27`
- comment spread:
  - `introduction=3`
  - `methods=4`
  - `results=4`

After:
- run: `20260329_153101_review/002_s44160-023-00351-1`
- section counts:
  - `front_matter=39`
  - `header_footer=42`
  - `introduction=44`
  - `methods=12`
  - `results=23`
  - `discussion=1`
- comment spread:
  - `introduction=3`
  - `methods=4`
  - `results=4`

Material improvements:
- `body` collapse is eliminated
- the key early miniaturization framing paragraphs now land in `introduction` instead of `body/front_matter`
- the affiliation block is returned to `front_matter`
- comment placement no longer depends on a generic `body` bucket

### Project 2 native deep-run

After:
- run: `20260329_151655_deep_run`
- section counts:
  - `front_matter=41`
  - `header_footer=32`
  - `introduction=47`
  - `methods=13`
  - `results=27`
  - `discussion=1`
- comment spread:
  - `introduction=3`
  - `methods=4`
  - `results=4`
  - `discussion=1`

Material improvements:
- native DOCX follows the same improved early-section recovery pattern as the PDF-surrogate run
- comments are now distributed across more scientific sections than before

## Concrete Paragraph-Level Evidence

### Project 1

Improved:
- paragraph `10`
  - before: `methods`
  - after: `introduction`
  - text: `Chemical synthesis is a primary bottleneck in drug development...`
- paragraph `17`
  - before: `methods`
  - after: `results`
  - text: `phactor. An interfacing script written in python is provided online.`
- paragraph `6`
  - before: `introduction`
  - after: `front_matter`
  - text: `Cite This...`

### Project 2

Improved:
- paragraph `7`
  - before: `results`
  - after: `introduction`
  - text: `Inspired by Moore’s Law of transistor miniaturization...`
- paragraph `8`
  - before: `introduction`
  - after: `front_matter`
  - text: affiliation block beginning `1Merck & Co., Inc....`
- paragraph `17`
  - before: `header_footer`
  - after: `introduction`
  - text: `The robotic liquid handlers typically used in low-volume reagent dosing...`

## Remaining Failures

The mapper is materially better, but not finished.

Remaining issues:
- miniaturization still over-absorbs some early figure/caption/picture-text blocks into `introduction`
- early pre-study bridge paragraphs in miniaturization are now mostly `introduction`, but some may really belong in a late-intro / transition / early-results bucket rather than pure introduction
- discussion recovery remains weak when the manuscript has no clean discussion heading
- header/footer counts remain high on noisy PDF-surrogate input, even though they are less harmful now than generic `body`

## Stage 2 Verdict

Stage 2 succeeded on the main scope:
- section mapping is materially improved
- project 2 no longer collapses into generic `body`
- front matter is less likely to poison active sections
- comment spread is more section-aware

Stage 2 is not the end state:
- miniaturization still needs additional refinement in early intro vs figure/caption vs transition handling
- discussion detection still needs a later focused pass

