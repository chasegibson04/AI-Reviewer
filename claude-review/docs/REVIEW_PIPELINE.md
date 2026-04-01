# `claude-review` Review Pipeline

The `claude-review` pipeline is a layered system designed to provide expert-level manuscript review and editing. It builds on the `AI-Reviewer` deep run logic, optimized for a terminal-first workstation experience.

## Pipeline Overview

The pipeline is organized into **12 distinct stages**, each producing auditable JSON artifacts and visible console logs.

### Stage 1: Ingest & Source Normalization
- **Purpose:** Parse DOCX or PDF files into a structured internal representation.
- **Tasks:** Extract text via `pdf-parse` or `mammoth`.
- **Output:** `stage_01_ingest.json`.

### Stage 2: Section Mapping & Triage
- **Purpose:** Map the manuscript's structure and perform initial quality checks.
- **Tasks:** Identify Abstract, Intro, Methods, Results, Discussion using a lightweight local model.
- **Output:** `stage_02_sections.json`.

### Stage 3: Digestion & Evidence Extraction
- **Purpose:** Extract core claims, methods, and results from the manuscript.
- **Tasks:** Chunks text safely (8000 char boundaries) and loops a local model to pull core claims.
- **Output:** `stage_03_ingest.json` (contains `claims`).

### Stage 4: Terminology & Definition Review
- **Purpose:** Identify undefined terms, abbreviations, and inconsistent terminology.
- **Tasks:** Scan for first-use of acronyms and jargon via LLM prompt against chunked text.
- **Output:** `stage_04_terminology.json`.

### Stage 5: Structural Review & Flow
- **Purpose:** Evaluate the logical flow and transition quality between paragraphs and sections.
- **Tasks:** Check for weak transitions, non-sequiturs, and coherence gaps.
- **Output:** `stage_05_coherence.json`.

### Stage 6: Methods, Rigor & Skepticism
- **Purpose:** Critically evaluate the methodological soundness and potential for overclaiming.
- **Tasks:** Hostile critique of experimental design via the strongest local reasoning model (e.g. `phi4-reasoning`).
- **Output:** `stage_06_methods.json`.

### Stage 7: Figure-Table Cross-Reference Review
- **Purpose:** Ensure all figures and tables are correctly referenced and support the text.
- **Tasks:** Uses strong deterministic regex to find figure/table declarations and body mentions. Reports orphan mentions and unreferenced declarations.
- **Output:** `stage_07_figures.json`.

### Stage 8: Citation & Claim Compliance
- **Purpose:** Verify citations follow style guides.
- **Tasks:** Deterministic regex extraction of in-text citations and reference blocks. Reports dangling citations and unused references.
- **Output:** `stage_08_citations.json`.

### Stage 9: Line-Edit & Style Pass
- **Purpose:** Perform a detailed stylistic and grammatical review.
- **Tasks:** Suggest rewrites. Edits are actively routed through the `protectFrontMatter` guardrail, switching destructive edits from `tracked_change` to `abstain`.
- **Output:** `stage_09_line_edits.json`.

### Stage 10: Arbitration & Final Reconciliation
- **Purpose:** Reconcile conflicting reviews (e.g., balanced vs. hostile) into a unified plan.
- **Tasks:** Deduplicates issues based on section/type/location and sorts them by severity mapping to the strict `IssueSchema`.
- **Output:** `stage_10_arbitration.json`.

### Stage 11: Render to Comments & Suggestions (PARTIAL)
- **Purpose:** Generate the final deliverables.
- **Tasks:** Translates arbitrated issues into `manuscript_comment_manifest.json` and `manuscript_suggested_changes_manifest.json`.
- **Output:** Highly structured JSON mappings suitable for downstream renderers. Native `python-docx` rendering (physical insertion of XML tracking tags) remains stubbed.

### Stage 12: Validation Pass
- **Purpose:** Final audit of the review itself.
- **Tasks:** Validates every generated issue against the strict Zod `IssueSchema` to ensure no corrupted structures or invalid severities were produced.
- **Output:** `stage_12_validation.json` (contains validation pass boolean and schema errors if any).

---

## Validation Rules & Quality Gates
- **Front-Matter Safety:** **DO NOT** suggest edits that delete authors, affiliations, or corrupt metadata.
- **Abstention Policy:** If a fix cannot be localized or is ambiguous, the agent must **abstain** and flag it for human review rather than making a low-confidence guess.
- **Local-First Default:** All stages must attempt local model execution (Ollama) before falling back to remote providers (unless configured otherwise).
- **Network Transparency:** Any online metadata lookup (e.g., DOI verification) must be visibly logged.
