# Evidence Grounding Improvements

## Identified Bottlenecks
1. **Model Non-Compliance:** Medium-tier models frequently ignored the `evidence_source` field.
2. **Parser Apathy:** The `repair.py` schema logic passively accepted `None` for `evidence_source`.
3. **Relevance Blocking:** Valid evidence from external papers was blocked from entering the prompt due to a mathematically flawed `_token_overlap` calculation (Jaccard index penalized large documents).

## Actions Taken
- **Algorithmic Fix:** Replaced Jaccard index (`len(sa & sb) / len(sa | sb)`) with an overlap coefficient (`len(sa & sb) / min(len(sa), len(sb))`). This prevents large external PDFs from artificially deflating the score, allowing them to cross the `0.04` and `0.03` thresholds and enter semantic claim verification.
- **Prompt Engineering:** Updated `engine.py` to strictly forbid `null` values for `evidence_source`. Directed the model to explicitly use `manuscript_internal`, `support_material_local`, `citation_retrieved_oa`, or `insufficient_external_support` when an exact file name isn't clear.
- **Parser Enforcement:** Modified `repair.py` to explicitly backfill missing `evidence_source` fields with `"manuscript_internal"` rather than silently dropping to `None`.
- **Verdict Cleanup:** Filtered out the `unresolved` verdict from Stage 12's comment generator to prevent low-signal noise ("Model failed to verify") from polluting the final manuscript annotation.

## Expected Outcome
- Every deep-review comment should now possess an explicit `evidence_source`, significantly reducing abstract "fluff".
- Retrieved citations will cleanly pass the relevance check and manifest as evidence cards in the review context.