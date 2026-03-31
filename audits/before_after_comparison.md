# Before vs After Comparison

## 1. Baseline Run Set Used For Comparison
- Earlier runs on Project 1 (`20260325163524_test-existingphactorpaper`) and Project 2 (`20260327051312_miniaturization_d2b`) prior to the semantic verification upgrades.

## 2. New Run Set Used For Comparison
- `20260330_165001_review` (Project 1)
- `20260330_172354_review` (Project 2)

## 3. Support-Paper Usage Before vs After
- **Before:** Support papers were chunked and compared against manuscript claims using simple keyword overlap. If words overlapped, it was marked `plausible`.
- **After:** Top high-priority claims are now sent to a reasoning LLM (Stage 5b) alongside the support chunks to perform a genuine semantic check, resulting in explicit verdicts like `supported` or `partially_supported`.

## 4. Claim/Assertion Checking Before vs After
- **Before:** Entirely deterministic python scripts relying on regex to find claims and token math to "verify" them.
- **After:** The system successfully extracted a claim about "fully automated" workflows, checked the support cards, and correctly reasoned that the claim was only "partially supported" because the cited methods still required some manual configuration.

## 5. Citation Checking Before vs After
- **Before:** Basic OpenAlex fetch using only DOIs found in the text.
- **After:** Integrated advanced fallback paths (Semantic Scholar, Europe PMC, OA.Works, CORE.ac.uk, Sci-Hub, and Wayback Machine) modeled after the `PaperScraperV2` notebook to maximize hit rates for resolving citations to PDFs.

## 6. Format/Compliance Before vs After
- **Before:** Weak heuristic checking for the words "data availability" and "abstract".
- **After:** Strong structural checks that detect missing Methods sections, excessively long titles, abstracts exceeding 450 words, and large unexplained gaps in citation numbering. These findings are now directly injected into the LLM's review context.

## 7. Comment Quality Before vs After
- **Before:** The LLM produced generic fluff like "Improve the flow of this paragraph" because the schema lacked evidence bounds. The `manuscript_annotation.py` script then injected heavy-handed python strings like "This sentence compresses too many procedural details."
- **After:** The `ReviewSchema` forces the LLM to populate `evidence_source`. Comments are far more precise (e.g., "The 'General procedure for Suzuki coupling of 3-boronopyridine (23)' lacks critical information such as specific reagents, concentrations, and reaction conditions").

## 8. Suggested-Revisions Before vs After
- **Before:** Sentences > 24 words were mechanically chopped by python split commands, frequently resulting in ungrammatical fragments in the DOCX output.
- **After:** Re-wrote `_rewrite_candidate` to split complex sentences along logical linguistic boundaries (semicolons, relative pronouns like "which/that") resulting in natural, grammatically correct edits.

## 9. DOCX-Native / Pre-Annotated DOCX Before vs After
- **Before:** Parsing its own previously generated DOCX files risked looping errors or XML corruption.
- **After:** Successfully built a synthetic test bed proving the system can identify prior AI comments, strip them from the analysis text, preserve human comments, and safely append new markup.

## 10. Hard Verdict: What Really Improved
- The pipeline's structural logic is vastly improved. Format checking is real. DOCX handling is safe. Sentence splitting is linguistic rather than mechanical.
- **However,** the *depth* of the core LLM review when running smaller models (like `gemma3:27b`) remains a bottleneck. While the *schema* now demands evidence, the model sometimes still outputs `null` for the `evidence_source` field. True semantic grounding is only consistently achieved when routed to larger reasoning models.
