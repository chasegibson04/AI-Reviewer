# Evidence Grounding Gap Analysis

## 1. Problem: The "Null" Evidence Trap
Fresh artifact review showed that models often skip the `evidence_source` and `manuscript_quote` fields when they are nested inside objects like `SectionComment`. 

## 2. Root Causes Identified
- **Schema Volume:** The `ReviewSchema` is a monolithic 15-field object. Models lose track of optional nesting when processing large manuscripts.
- **Ambiguous Inputs:** `detailed_reviewer_comments` was a simple `list[str]`, which served as a "garbage bin" for thoughts the model didn't want to strictly ground.
- **Sync Failure:** The `cli.py` missing sync meant newly fetched citation PDFs weren't actually visible to the LLM during the review stages.

## 3. Structural Solutions Implemented
- **Structured Grounding:** Added `grounded_detailed_comments` to `ReviewSchema`. This forces the model to treat detailed critique as a structured object with mandatory `manuscript_quote` and `evidence_source` fields.
- **Direct Injection:** Modified `deep_run.py` to directly inject findings from the Semantic Claim Verification stage (Stage 5b) into the final comment manifest. This bypasses the risk of the model "forgetting" to cite evidence during the synthesis stage.
- **Mandatory Quoting:** Updated the system prompt to explicitly require at least 3 `grounded_detailed_comments` per review.
- **Sync Fix:** Added a material refresh step in `cli.py` after citation fetching to ensure the semantic verifier can see downloaded papers.

## 4. Expected Outcome
The "After" runs should show a material increase in comments that explicitly name the supporting file and quote the manuscript text, providing a clear audit trail for the author.
