# Gemini Fix Validation Report

## 1. What Was Already Real
- The system successfully discovered, loaded, and parsed PDF documents from `materials/other`.
- It built local text indices, embedded chunks, and calculated token overlap scores for basic relevance filtering.
- The pipeline generated complex JSON manifests mapping paragraphs to comments.
- A functional end-to-end mechanism existed for writing tracked changes and comments directly into native DOCX files without destroying existing human comments.

## 2. What Was Overstated (The Reality Gap)
- **Scientific Verification:** The system claimed to "verify" support for assertions, but the runtime reality was that it only measured basic keyword/token overlap between a manuscript claim and a cited paper's text. If overlap was > 4%, it labeled it `support_relationship_plausible`. It lacked genuine semantic checking.
- **Evidence-Grounded Comments:** The prompts instructed the model to be grounded, but the resulting `ReviewSchema` output did not require evidence citations for its critiques. Moreover, `manuscript_annotation.py` overrode much of the LLM's output with hardcoded Python regex heuristics (e.g., matching "always" or "never") and mechanical sentence truncation.
- **Compliance Integration:** Format and standards checking produced a side artifact, but it was easily missed and not strictly integrated into the primary reviewer feedback.

## 3. What Was Fixed
- **Deep Semantic Claim Verification:** Added Stage 5b (`_verify_claims_semantically`) to the `deep-run` pipeline. It now extracts top high-priority claims, matches them to the most relevant support cards, and prompts a reasoning model (`phi4-reasoning` or `llama3.3:70b`) to explicitly classify the relationship as `supported`, `partially_supported`, `contradicted`, or `unresolved`, attaching a rationale and confidence score.
- **Evidence Bounding in ReviewSchema:** Upgraded the core Pydantic `ReviewSchema` so that `SectionComment` and `ActionItem` models now include `evidence_source` and `manuscript_quote` fields. The engine prompt now strictly mandates referencing these fields.
- **Replaced Mechanical Heuristics with Semantic Wording:** Re-wrote the fallback revision system (`_rewrite_candidate`) to split long sentences at logical boundaries (relative pronouns, semicolons) instead of mechanical word counts. Softened overclaim heuristics so the system provides nuanced suggestions ("qualify the claim to the specific experimental evidence shown") rather than rigid regex replacements.
- **Upgraded Compliance Rules:** Strengthened `build_format_compliance_report` to check for abstract length, missing critical sections (Introduction, Methods, etc.), and large unexplained jumps in citation numbering.

## 4. What Is Still Weak
- **Citation Truth vs Citation Existence:** While we added semantic claim checking for the top claims against *local support papers*, the general citation checking module (`build_citation_verification_ledger`) still only validates that a DOI exists in OpenAlex. It does not fetch the OpenAlex abstract and verify the specific claim against it.
- **Model Fallbacks on ARM:** On Mac M-series platforms, the system correctly falls back to `gemma3:27b` and `qwen3:14b`. While fast and capable, they occasionally drop strict JSON keys or fail to deeply integrate the verification context compared to `llama3.3:70b`.

## 5. What Remains Unproven
- Whether the system can autonomously catch deep methodological errors (e.g., fundamentally flawed statistical tests) without the user explicitly supplying a context pack warning about that specific error.
