# Root-Cause Analysis of Comment Quality Failure

## A. Why does evidence_source end up null?
- **Schema Permissiveness:** `ReviewSchema` defined `evidence_source` as `str | None = None`. The repair logic also blindly defaulted missing sources to `None`.
- **Prompt Ambiguity:** The prompt asked for `evidence_source` "(if available from verification context)", giving the model an easy out to skip it.
- **Generic Fallback:** When models omitted it, the system silently allowed it rather than forcing a fallback state.

## B. Why are some comments still generic?
- **Deduplication Overreach:** `_looks_generic_comment` in `manuscript_annotation.py` automatically discarded comments shorter than 28 characters, which inadvertently filtered out sharp, concise critiques (e.g., "Missing control.").
- **Lack of Directed Policy:** The "Section-aware policy" in the LLM prompt was too abstract. It did not explicitly instruct the model to attack specific methodological tropes like hidden human intervention or missing physical constraints (e.g., mass transfer).

## C. Why is comment density low?
- **Filtering Cascades:** The combination of strict schema dropping (if fields failed to parse perfectly) and the `_looks_generic_comment` length threshold aggressively pruned the final comment list.
- **Support Material Cap:** The hard cap of 20 support materials (`support_materials[:20]`) meant the system often ignored fetched citations, reducing the surface area for evidence-based critiques.

## D. Why do remotely fetched PDFs not truly help?
- **Flawed Relevance Math:** The `_support_relevance_score` calculated a raw Jaccard index (`len(sa & sb) / len(sa | sb)`) on the first 20,000 characters. For a large PDF, the massive denominator forced the score below the `0.04` threshold, causing the system to silently skip the paper.
- **Claim Semantic Mismatch:** Stage 5b used the same Jaccard logic against 50-word chunks, meaning overlap scores were artificially crushed by the union denominator. 

## E. Architectural Verdict
The system was relying too heavily on the model to "just do it right" in one shot, while surrounding the model with filters (Jaccard relevance, 20-file limits, length filters) that inadvertently blocked valid signals. We addressed this by adjusting the algorithms, raising the caps, and strictly enforcing fallback states in the prompt and parser.