# Suggested Changes DOCX Pipeline

## Goal
Generate a second, separate DOCX containing proposed edits derived from review comments and manuscript context. The commented DOCX remains unchanged; the suggested-changes DOCX applies vetted local edits.

## Pipeline
1. Generate commented DOCX and comment manifest (existing).
2. Group comments by paragraph index and section.
3. Skip blocked sections (front matter, references, header/footer) and too-short paragraphs.
4. Apply section-aware rules to decide eligibility (e.g., abstract high-threshold).
5. For each eligible paragraph, call the local chat model to propose a revised paragraph using:
   - original paragraph
   - adjacent context (prev/next)
   - comment critique + suggested revision
   - section-specific editing rules
6. Parse JSON response and apply only safe edits.
7. Write suggested-changes DOCX.
8. Emit manifest + validation artifacts.

## Outputs
- `*_with_suggested_changes.docx`
- `manuscript_suggested_changes_manifest.json`
- `suggested_changes_validation.json`

## Conflict/Dedup Strategy
- Group by paragraph; merge comment signals.
- If a paragraph has multiple comments, the prompt combines them.
- Global/structural comments are marked `skipped` when no safe local edit exists.

## Safety Rules
- Do not edit front matter/references by default.
- Preserve meaning and avoid new claims.
- Skip if model output is empty or unchanged.

## Traceability
Each manifest entry records:
- change id
- paragraph index
- original/revised excerpts
- comment ids and issue types
- status (applied/skipped) with reason
