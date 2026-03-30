# Suggested Changes DOCX Pipeline

## Goal

Generate a separate manuscript DOCX that layers proposed local edits on top of the source manuscript while keeping the commented manuscript output separate.

## Current Pipeline

1. Generate or load the base manuscript DOCX.
2. Build localized comment targets from the review output.
3. Group rewrite work by local span and section.
4. Skip blocked sections such as front matter, references, and unsafe heading-only targets.
5. Generate candidate span-level rewrites using local context plus the triggering comment.
6. Verify candidate rewrites for:
   - faithfulness
   - unsupported additions
   - awkward or mechanical prose
   - truncation / malformed local spans
7. If the model rewrite fails, try a bounded deterministic local fallback only when the span is safe.
8. If no safe local rewrite exists, abstain and record `skip_reason`.
9. Write the suggested-changes DOCX and validation/manifests.

## Outputs

- `*_with_suggested_changes.docx`
- `manuscript_suggested_changes_manifest.json`
- `suggested_changes_validation.json`

## Traceability

Manifest entries now record span-faithful provenance such as:
- target section
- target span
- issue groups
- rewrite strategy
- verification outcome
- applied vs skipped state

## Current Product Limitation

The output format is still visible suggestion-block markup, not native Word track changes.
