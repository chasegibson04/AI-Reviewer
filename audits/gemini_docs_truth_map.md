# Gemini Docs Truth Map

Date: 2026-03-30
Project: AI-Reviewer

## 1. System Claims (What the docs say it does)
- **Local-First Review**: Uses local Ollama for all chat/embedding tasks. No cloud egress for manuscript content.
- **Project-Scoped**: Organizes work into projects with `materials/`, `runs/`, and `audits/`.
- **Deep-Run Pipeline**: A 17-stage multi-pass critique and synthesis workflow.
- **Manuscript-Embedded Deliverables**: Produces DOCX files with inline comments and tracked suggested changes.
- **Auditable Artifacts**: Generates detailed JSON/MD manifests for comments, suggestions, citations, and support materials.
- **Verification Layer**: Extracts claims, links them to citations, and checks against local support papers (`materials/other`).
- **Native DOCX Handling**: Supports re-reviewing already annotated DOCX files while preserving existing markup.

## 2. Workflows and Profiles
- **Workflows**:
    - `review`: Standard single-pass (or enriched) review.
    - `deep-run`: High-quality, multi-stage staged review.
    - `evaluate-paper`: Comparison across multiple profiles.
    - `compare`: Draft-to-draft comparison.
    - `diagnose`/`test-models`: Environment and capability checks.
- **Profiles**: `balanced` (default), `deep`, `methods`, `adversarial`, `editor`, `writing`.

## 3. Intended Outputs
- **Reports**: `review_report.md`, `final_deep_review_report.md`, `validated_review.json`.
- **DOCX**: `reviewed_manuscript_with_comments.docx`, `reviewed_manuscript_with_suggested_changes.docx`.
- **Manifests**: `manuscript_comment_manifest.json`, `manuscript_suggested_changes_manifest.json`.
- **Verification**: `support_ingest_report.json`, `assertion_ledger.json`, `citation_verification_ledger.json`, `format_compliance_report.json`.

## 4. Privacy and Offline Rules
- **Strict Offline**: Default is `true`. Blocks non-local Ollama URLs.
- **Citation Fetch**: Metadata/OA lookup is allowed even in strict offline mode, but uses sanitized, non-leaking queries.
- **Manuscript Data**: Strictly stays local. Only derived metadata (titles, DOIs) leaves for citation fetching.

## 5. Support-Material and Citation Behavior
- **Support Materials**: Located in `materials/other`. Filtered by relevance/overlap before use.
- **Citation Ingest**: Fetches metadata via Crossref/OA APIs.
- **Verification Labels**: `citation_exists`, `metadata_match_likely`, `support_relationship_not_verified`, etc.
- **Honesty**: Docs explicitly state the system does *not* yet prove full claim-to-paper verification, only "plausibility" and "linkage".

## 6. Model Routing
- **Modes**: `default` vs `max_quality`.
- **Routing**: Stronger models (e.g., `llama3.3:70b`, `phi4-reasoning`) are used for critique and arbitration; smaller models for structural triage.
- **Mac ARM**: Explicit fallbacks for Apple Silicon (e.g., `qwen3:32b`, `gemma3:27b`).

## 7. DOCX Handling
- **Comments**: Anchored to paragraphs/spans.
- **Suggestions**: Rendered as Word tracked insertions/deletions in a separate `suggested_changes` DOCX.
- **Preservation**: Existing comments and AI-suggestion blocks from prior runs are preserved and handled as "non-manuscript" text during re-review.

## 8. Docs Status (Stale, Contradictory, Vague)
- **Stale**: `ai_scientist/` is legacy code for "provenance" but still in the root. Some older docs might refer to it.
- **Contradictory**: The relationship between `strict_offline` and citation fetch was recently updated; older docs might say fetch is skipped, while newer ones say it's allowed under a sanitized policy.
- **Vague**: "Final arbitration" in `deep-run` is noted as still being "limited by schema quality" rather than model strength.
- **Unclear**: Figure review is documented as "text-only" and "adding noise", yet the `figure_off.yaml` exists, implying it's a switchable layer that is currently suboptimal.
