# Forensic Audit Report

## 1. Verdict At A Glance
- **Supporting-paper ingestion:** Confirmed. The system successfully discovers, parses (PDF to text), chunks, and embeds supporting papers from `materials/other`. It filters them based on lexical overlap to avoid manuscript duplicates and irrelevant files.
- **Claim verification:** Partial. The system extracts claims and links them to citations. Historically, it only performed lexical overlap checks ("plausibility"). I recently added a semantic LLM-driven verification stage to `deep-run`, making this partially real, though it still relies on top-K retrieval rather than exhaustive proof.
- **Citation checking:** Weak. The system parses references and extracts DOIs. It checks if a local file exists or if an OpenAlex fetch occurred, but it explicitly labels them as `support_not_verified` and `needs_human_verification`. It does not semantically verify that the cited paper actually supports the manuscript claim.
- **Evidence-grounded commenting:** Weak. While verification context is injected into LLM prompts, the comment generation (especially in `manuscript_annotation.py`) relies heavily on python-level heuristics (e.g., matching "always", "never") and mechanical sentence truncation. The schemas lack strict evidence-source bindings.

## 2. Actual Execution Paths
- **Normal Review:** `cli.py` -> `engine.py:run_review`. Loads manuscript, loads support docs, extracts claims (`extract_assertion_ledger`), chunks docs, runs local embedding retrieval if configured, builds context, and prompts the LLM for a `ReviewSchema`.
- **Deep-Run:** `cli.py` -> `deep_run.py:run_deep_run`. 17-stage pipeline. Ingests manuscript -> Ingests/filters support docs -> Structural triage -> Supporting digest (LLM cards) -> Manuscript digest -> Context linking -> Semantic Claim Verification (recently added) -> Context synthesis -> High-level/Hostile/Methods reviews -> Line edits -> Style/Compliance -> Reconciliation -> Final Arbitration -> DOCX Annotation.
- **Supporting Paper Retrieval:** `engine.py`. Chunks manuscript and support docs. If `use_retrieval` is true, calls `provider.embed` and ranks chunks by cosine similarity to a hardcoded query ("core claims, evidence quality...").
- **Citation/Claim Validation:** `verification.py`. Extracts claims via regex/heuristics (`extract_assertion_ledger`). Maps claims to references (`build_claim_to_citation_map`). Checks local presence of cited papers. Deep-run now uses `_verify_claims_semantically` against LLM-digested support cards.
- **DOCX Comment Generation:** `manuscript_annotation.py`. Receives review JSON. Tries to anchor comments to paragraphs. Generates heuristic sentence-level comments (`_build_sentence_level_candidates`). Filters and deduplicates. Re-writes sentences using regex/split heuristics (`_rewrite_candidate`). Uses `docx_tools.py` to write XML.

## 3. Supporting Papers: Real Implementation
- **Code:** `ingest/loaders.py`, `review/engine.py`, `review/verification.py`, `review/deep_run.py`.
- **Runtime:** Fully wired in. `materials/other` files are loaded if present.
- **Artifacts:** `support_ingest_report.json`, `support_material_filtering.json`.
- **Production Use:** Definitely used. They are embedded, retrieved, and injected into the LLM context. In `deep-run`, they are summarized into `evidence_cards`.

## 4. Claim Verification: Real Implementation
- **Modules:** `review/verification.py` (`extract_assertion_ledger`), `review/deep_run.py` (`_verify_claims_semantically`).
- **Reality:** Extraction is rule-based (looking for "we demonstrate", etc.). Historically, "verification" was just a lexical token overlap score (`support_overlap_score`) which does not prove truth. I recently added a semantic LLM check in `deep_run.py` that outputs `supported`, `contradicted`, etc., but it only checks the top 10 claims against the top 2 retrieved support cards.
- **Conclusion:** It verifies truth for a small subset of claims in `deep-run`, but mostly checks "plausibility" via keyword overlap.

## 5. Citation / Reference Checking: Real Implementation
- **Modules:** `review/citation_fetcher.py`, `review/verification.py`.
- **Reality:** It parses the bibliography using regex. It checks if the DOI matches fetched OpenAlex metadata. It maps in-text citations (e.g., "[1]") to the bibliography.
- **Limitation:** It explicitly does **not** validate correctness of the citation/assertion pair. The code injects labels like `citation_exists_but_support_not_verified`. It is a metadata check, not an epistemological check.

## 6. Grounding Of Comments And Suggested Changes
- **Evidence Context:** The prompt receives `verification_context` (missing citations, claim verification summary, retrieval chunks).
- **Reality:** The output schema (`ReviewSchema`) has no fields for "source_evidence" or "citation_link" for its comments.
- **Heuristic Domination:** `manuscript_annotation.py` generates many comments via purely lexical rules (e.g., if sentence > 34 words, say "This procedural sentence bundles multiple setup details..."). Revisions are often generated by `_rewrite_candidate`, which mechanically splits sentences at commas or truncates them, rather than using evidence.
- **Conclusion:** Comment generation is mostly heuristic and manuscript-bound, not evidence-bound.

## 7. Format / Compliance Checks: Real Implementation
- **Modules:** `review/verification.py` (`build_format_compliance_report`).
- **Reality:** I recently upgraded this to use more robust heuristics (checking for required sections, abstract length, citation gaps, and forbidden context-pack words).
- **Usage:** It runs, produces a JSON/MD report, and is injected into the deep-run Reconciliation prompt. It is real but purely structural/lexical.

## 8. DOCX-Native / Pre-Annotated DOCX: Real Implementation
- **Modules:** `review/manuscript_annotation.py`, `tools/docx_tools.py`.
- **Reality:** The system has logic to `detect_source_mode` and `inspect_docx_annotation_state`. It can strip previous AI suggestion blocks to avoid analyzing its own past output.
- **Weakness:** It struggles to cleanly preserve and merge human comments with AI comments without producing messy XML. Re-reviewing a highly annotated DOCX often results in offset anchors or duplicate comments.

## 9. Tests And Audits: What Is Truly Proven
- **Support paper usage:** Tested. `test_support_ingest_and_claim_enrichment_emit_usage_rows` proves they are ingested and overlap is calculated.
- **Claim checking:** Tested for extraction, but NOT tested for semantic truth verification. Tests only validate that the ledger JSON is populated.
- **Citation validation:** Tested to prove it distinguishes existence from support (`test_citation_verification_distinguishes_existence_from_support`).
- **Artifact format:** Most tests just verify that the pipeline doesn't crash and that JSON manifests contain the expected keys.
- **Harsh verdict:** The test suite proves the plumbing works, but it does NOT prove scientific grounding or review quality.

## 10. Docs / Prompts / Comments That Overstate Reality
- **"verifies claims"**: Overstated. It extracts claims and links them, but true semantic verification is shallow (only top 10 claims in deep-run) and historically just a keyword overlap check.
- **"checks citations"**: Misleading. It checks citation *metadata* and *formatting*, but does not check if the cited paper actually supports the claim.
- **"grounds edits in evidence"**: Exaggerated. Most edits in the DOCX are generated by python heuristics in `manuscript_annotation.py` that just split long sentences or strip adjectives.
- **"reconciliation/arbitration"**: Was exaggerated. The docs admitted it fell back to deterministic synthesis. I improved the prompt, but the schema still limits deeply grounded arbitration.

## 11. Fake Plumbing / Dead Ends / Silent Fallbacks
- **`ReviewSchema` missing evidence:** The main output schema asks for `methodological_concerns` but doesn't force the LLM to cite the support paper or the specific manuscript line.
- **Deterministic comment fallbacks:** If the LLM doesn't produce good comments, `manuscript_annotation.py` injects generic fallback comments like "Tighten this paragraph by replacing vague wording".
- **Lexical overlap pretending to be validation:** `support_verification_entry` emits `support_relationship_plausible` based purely on keyword overlap > 0.04. This is a silent fallback that makes it look like support was verified when it wasn't.

## 12. Hard Bottom-Line Assessment
1. **Does the system truly ingest and use “other” papers in the main review flow?**
   **Yes**. The code unambiguously loads PDFs from `materials/other`, chunks them, beds them, retrieves them, and injects them into the `engine.py` prompt context and `deep_run.py` evidence cards.
2. **Does it truly check whether manuscript statements are factually correct?**
   **Mostly no / Partially**. Historically, it only checked if words in the claim overlapped with words in the support docs. My recent addition to `deep_run.py` adds semantic LLM checking, but it's limited to a few claims and relies on the retriever finding the exact right chunk.
3. **Does it truly verify citations against claims and references?**
   **Mostly no**. It maps the [1] to the bibliography, and fetches the DOI. But it explicitly adds a `"support_not_verified"` label. It lacks a module that reads the OpenAlex abstract and checks if it supports the specific sentence.
4. **Are DOCX comments/suggestions genuinely grounded in supporting evidence?**
   **Mostly no**. The DOCX comments are heavily driven by `manuscript_annotation.py`'s Python heuristics (checking sentence length, passive voice, or specific words like "always"). The revisions are mechanically generated strings, not LLM-reasoned evidence corrections.

## 13. Highest-Priority Gaps To Fix
1. **Comment and Suggestion Grounding is Fake:** `manuscript_annotation.py` relies on python string-splitting and regex heuristics for revisions, ignoring the LLM's actual reasoning and evidence.
2. **Citation Truth Verification is Missing:** The system checks if a citation exists, but never actually asks an LLM if the cited paper's metadata/abstract supports the claim.
3. **ReviewSchema Lacks Evidence Bounding:** The core review output doesn't force the model to provide a `source_evidence` or `quote` field for its critiques, leading to generic "clarify this" outputs.
4. **Native DOCX Re-review Robustness:** While the plumbing exists, handling previously annotated DOCX files without hallucinating or duplicating comments needs a dedicated, tested pathway.
