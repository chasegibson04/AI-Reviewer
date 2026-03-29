# AI-Reviewer / PaperReviewer: Full System Report (LLM-Facing)

Date: 2026-03-28
Repository: `AI-Reviewer`
Purpose: Explain how the full system works end-to-end for another LLM/agent, including orchestrator logic, toolchain, sub-model routing, artifact flow, and the latest Rigorous-inspired integration.

## 1. System Identity and Design Boundaries

AI-Reviewer is a local-first manuscript review/editing platform with project-scoped runs and auditable artifacts.

Primary goals:
- Review manuscripts using structured profiles.
- Produce author-facing outputs, not only reports:
  - commented manuscript DOCX
  - suggested-changes DOCX (visible in-text suggestions)
- Keep run outputs traceable and verifiable.
- Stay local-first by default (`strict_offline: true`).

Non-goals:
- Not a cloud-first autonomous research agent.
- Not a single monolithic prompt script.
- Not a PDF-report-only system.

## 2. Top-Level Architecture

Main modules:
- CLI and workflow entry: `ai_reviewer/cli.py`
- Config and env overrides: `ai_reviewer/config.py`, `config/defaults.yaml`
- Provider layer (Ollama): `ai_reviewer/models/ollama_provider.py`
- Model role selection/routing: `ai_reviewer/models/selector.py`
- Standard review engine: `ai_reviewer/review/engine.py`
- Deep multi-stage workflow: `ai_reviewer/review/deep_run.py`
- Manuscript annotation + suggested changes: `ai_reviewer/review/manuscript_annotation.py`
- DOCX utilities: `ai_reviewer/tools/docx_tools.py`
- Citation prefetch stage: `ai_reviewer/review/citation_fetcher.py`
- Figure extraction/critique: `ai_reviewer/figures/figure_review.py`
- Orchestrator QA controller: `ai_reviewer/orchestrator/controller.py`
- Training guidance cache/injection: `ai_reviewer/training/cache.py`, `ai_reviewer/training/injector.py`
- Concurrency locking: `ai_reviewer/ops/locks.py`
- Output verification: `ai_reviewer/output_verifier.py`

## 3. Execution Modes / Workflows

CLI commands (core):
- `review`: per-manuscript review run with profile(s).
- `deep-run`: staged, multi-pass workflow with synthesis and manuscript annotation.
- `evaluate-paper`, `compare`, `diagnose`, `tools`, `test-models`, `benchmark`.

Relevant command paths:
- `python -m ai_reviewer.cli review ...`
- `python -m ai_reviewer.cli deep-run --project <id>`
- `python -m ai_reviewer.cli deep-run --project <id> --context-material-ids <id1,id2,...>`

## 4. Config System and Runtime Policy

Config dataclasses (`ai_reviewer/config.py`):
- `Defaults`, `Timeouts`, `RetryPolicy`, `RetrievalConfig`, `TrainingConfig`, `OrchestratorConfig`, `ConcurrencyConfig`, `FigureReviewConfig`, `CitationFetchConfig`.

Config merge order:
1. `config/defaults.yaml`
2. `config/local.yaml` (if present)
3. `config/local.override.yaml` (if present)
4. optional `--config-path`
5. environment overrides (e.g., `AI_REVIEWER_ORCHESTRATOR_MODEL`, `AI_REVIEWER_STRICT_OFFLINE`, etc.)

Important defaults in `config/defaults.yaml`:
- `strict_offline: true`
- `orchestrator.enabled: false`
- `orchestrator.model: phi4-reasoning:latest`
- `citation_fetch.enabled: true` (but runtime skipped under strict offline)
- `citation_fetch.methods: [doi_open_access_apis, crossref_lookup_then_oa]`

## 5. Provider and Model Role Safety

Provider: `OllamaProvider` (`ai_reviewer/models/ollama_provider.py`)
- Enforces local URL in strict offline mode (localhost/127.0.0.1 only).
- Uses `/api/chat` for chat and `/api/embed` for embedding.
- Hard guard: embedding-only model cannot be used for chat (`ProviderError` UNSUPPORTED).

Model role classification: `ai_reviewer/models/selector.py`
- `is_embedding_model(...)`
- `split_chat_and_embedding_models(...)`
- `infer_model_roles(...)` chooses balanced/deep/embedding/repair candidates.
- Apple Silicon-aware prioritization via `detect_platform()` (`ai_reviewer/platform.py`), but role typing still enforced (installed != valid for every role).

## 6. Standard Review Pipeline (review command)

High-level order in `cli.py`:
1. Resolve project/docs.
2. Acquire project lock (if enabled): `acquire_project_lock(...)`.
3. Pre-run citation fetch stage: `fetch_citations_for_documents(...)`.
4. Refresh supporting docs.
5. Training sync + guidance injection.
6. Optional orchestrator initialization.
7. `run_review(...)` per document.
8. Manuscript annotation + suggested changes: `build_annotated_manuscript_output(...)`.
9. Write manifests and validations.
10. Release lock.
11. Verify output bundle (`verify_review_run`).

Inside `run_review(...)` (`ai_reviewer/review/engine.py`):
- Builds profile-aware prompt + section policy constraints.
- Optional retrieval context embedding.
- Chat generation + parse/repair pipeline.
- Sparse-output enrichment heuristics if needed.
- Optional figure-review injection.
- Optional orchestrator stage QA and retry/rerank.
- Writes review bundle artifacts.

## 7. Deep-Run Pipeline (sub-LLM stage map)

`run_deep_run(...)` in `ai_reviewer/review/deep_run.py` executes bounded stages with stage artifacts.

Model stack (`_select_stage_models`) picks chat models only (embeddings excluded):
- `structural_triage`
- `supporting_digest`
- `manuscript_digest`
- `context_synthesis`
- `high_level_review`
- `adversarial_review`
- `methods_verification`
- `line_edits`
- `style_alignment`
- `reconciliation`
- `final_arbitration`

Stage flow summary:
- Stage 00: sync/manifests/tool availability.
- Stage 01: source parse + structural source snapshot.
- Stage 02: structural triage.
- Stage 03: supporting-paper digestion (+ cache).
- Stage 04: manuscript digestion (+ cache).
- Stage 05: context/evidence linking.
- Stage 06: context synthesis.
- Stage 07-09: specialist critique bundles (high-level, hostile, methods).
- Stage 10: line-by-line edits extraction.
- Stage 11: style alignment.
- Stage 11b: context-pack compliance check (deterministic).
- Stage 12: reconciliation synthesis.
- Stage 13: commented manuscript + suggested changes generation.
- Final: deep review report bundle + metadata.

Context-pack behavior:
- Optional inputs through `--context-material-ids`.
- If IDs are omitted, deep-run auto-selects context materials by category:
  - `style_guide`, `journal_instructions`, `reference_example`, `methods_reference`.
- Context-pack constraints are extracted and recorded in:
  - `context_pack_used.json`
  - `context_pack_used.md`
- Deterministic compliance findings are written to:
  - `stage_10b_compliance_check.json`
  - `stage_10b_compliance_check.md`

Each stage writes JSON/MD/raw artifacts in run dir for traceability.

## 8. Orchestrator: Purpose and Mechanics

Controller: `ai_reviewer/orchestrator/controller.py`

Primary responsibilities:
- Deterministic stage quality assessment (`_deterministic_stage_assessment`).
- Optional LLM adjudication if orchestrator is enabled and deterministic gate says retry.
- Retry decision via bounded budget (`OrchestratorRuntimeState`).
- Version comparison A/B and winner selection.
- Distinctness checks across stage outputs.
- Final synthesis quality check (grounding/value/priority completeness).

Important behavior:
- Default `enabled=false`; deterministic path still exists and can be used when enabled.
- `fail_open` controls whether orchestrator errors block pipeline.
- Quality signals include specificity, actionability, section coverage, placeholder detection, figure mention coverage, etc.

## 9. Tool Layer and Registry

`ToolRegistry` (`ai_reviewer/tools/registry.py`) exposes bounded utility calls:
- PDF parsing
- DOCX parsing/commented copy support
- DOI lookup helper
- availability scan

Tool availability scan + smoke tests:
- `ai_reviewer/tools/availability.py`
- `ai_reviewer/tools/smoke_tests.py`

## 10. Citation Prefetch (PaperScraper-style Integration)

Location: `ai_reviewer/review/citation_fetcher.py`

Design:
- Runs before analysis in both `review` and `deep-run` flows.
- Parses references from manuscript text.
- Tries configured methods in order:
  - `doi_open_access_apis`
  - `crossref_lookup_then_oa`
- Applies query sanitization and logs query type/length audit fields.
- Downloads OA PDFs into `projects/<id>/materials/other`.
- Writes run artifact `artifacts/citation_fetch_report.json`.
- Logs stage start/done to console/logs.

Extensibility (where to add methods):
- Add a function with signature `CitationMethodContext -> CitationMethodResult`.
- Register in `REGISTERED_CITATION_METHODS`.
- Add to config `citation_fetch.methods` order.

Duplicate prevention:
- DOI cache file in project other folder: `citation_doi_cache.json`.
- Cache checked before network attempts.
- Existing local file checks also prevent duplicate download.

Strict offline interaction:
- If `strict_offline=true`, citation fetch returns `reason=strict_offline` and does not call remote endpoints.

Support-material contamination control:
- `review` and `deep-run` now filter supporting docs by lexical overlap with the manuscript.
- Known irrelevant filename markers (for example `BioGPT`, `OpenAI Gym`) are blocked from grounding context.

## 11. Training Guidance System

Training cache manager: `ai_reviewer/training/cache.py`
- Syncs training materials into parsed/takeaway cache.
- Paths normalized against `REPO_ROOT` (not CWD).
- Produces global guidance summary + per-category guidance.

Injection logic: `ai_reviewer/training/injector.py`
- Profile-to-category mapping (`PROFILE_CATEGORY_MAP`).
- Cleans noisy bullets.
- Category fallback + global fallback when sparse.
- Injected prompt block included in review/deep-run prompts.

## 12. Manuscript Annotation and Suggested Changes

Main function: `build_annotated_manuscript_output(...)` in `ai_reviewer/review/manuscript_annotation.py`

Outputs:
- Commented manuscript DOCX.
- Suggested-changes DOCX.
- `manuscript_comment_manifest.json`.
- `manuscript_suggested_changes_manifest.json`.
- validation artifacts (`commented_docx_validation.json`, `suggested_changes_validation.json`).

Suggested changes behavior (`ai_reviewer/tools/docx_tools.py`):
- Applies only `status=applied` items.
- Keeps original paragraph and appends visible marker:
  - `[Suggested change] ...`
- Structural validation ensures paragraph count parity.

Safety/quality controls in annotation layer:
- Section-role targeting heuristics.
- Dedup and paragraph clustering controls.
- Absurd-change blocking (e.g., author-list tampering patterns).
- Rewrite gating and unresolved statuses for unsafe/global-only changes.
- Unsupported-addition guard to block speculative inserted claims (for example fabricated comparative-study statements), with safe local fallback rewrite when possible.

## 13. Figure Review Pipeline (Current Capability)

Location: `ai_reviewer/figures/figure_review.py`

Current mode:
- Extracts images from PDF via PyMuPDF.
- Attempts caption extraction/pairing from page/document text.
- Produces critique based on caption + nearby text.
- Explicitly labeled `visual_mode: text_only` if no real VLM path.

Artifact:
- `figure_manifest.json` in bundle output.

Noise controls:
- Tiny decorative assets are skipped (image-area threshold).
- Repeated caption-missing messages are aggregated before they are added to review concerns.

Note:
- This is honest text/caption contextual critique unless multimodal model integration is implemented/enabled.

## 14. Concurrency, Isolation, and Recovery

Locking: `ai_reviewer/ops/locks.py`
- Project lock file: `projects/<id>/.locks/project.lock`.
- Same-project policy configurable:
  - default: concurrent same-project runs disallowed.
- Stale lock cleanup via TTL (`lock_ttl_seconds`).

Usage in CLI:
- lock acquired before heavy workflow sections.
- lock released in `finally` blocks on success/failure.
- lock info artifact written per run (`artifacts/lock_info.json`).

Isolation model:
- Each run writes to project-local run dir (`projects/<id>/runs/<run_id>_*`).
- Per-document bundles under run dir (`001_*`, etc.).
- Artifacts/manifests are run-local to avoid collisions.

## 15. Output Verification and Auditability

Verifier module: `ai_reviewer/output_verifier.py`
- `verify_review_run(...)`
- `verify_deep_run(...)`
- `verify_evaluation_run(...)`

Checks include:
- mandatory report files
- validated review JSON
- comment/suggested-change manifests
- source mode and validation artifacts
- deep-run reconciliation artifact presence
- annotated and suggested DOCX presence

This protects against "file exists but unusable" regressions.

## 16. New Rigorous-Inspired Integration (Latest)

New module:
- `ai_reviewer/review/rigorous_adapters.py`

Added capabilities:
1. Standard review specialist QC summary:
   - `specialist_counts`
   - `qc_flags` (generic/duplicate counts)
   - `category_scores_0_to_5`
   - `overall_score_0_to_5`
   - recommendations

2. Deep-run reconciliation QC summary:
   - reconciliation counts
   - duplicate cross-field checks
   - generic weakness checks
   - unresolved risk note extraction
   - `reconciliation_quality_score_0_to_5`

Integration points:
- `engine.py` now writes:
  - `specialist_review_summary.json`
  - `specialist_review_summary.md`
  - and includes score fields in `run_metadata.json`
- `deep_run.py` now writes:
  - `stage_11_reconciliation_qc.json`
  - `stage_11_reconciliation_qc.md`

Intent:
- Import Rigorous strengths in bounded form (specialist/QC structure) without merging runtime architecture.

## 17. How Sub-LLMs Work in Practice

There is no hardcoded "agent process per role" model. Instead, one provider is called with different stage prompts and selected models.

Sub-LLM behavior is implemented as:
- stage-specific model selection (`deep_run model_stack`)
- stage-specific prompts and schemas
- stage artifacts per phase
- optional orchestrator retry/adjudication

Equivalent conceptual roles:
- Structural triage model
- Context synthesis model
- Critique models (balanced/adversarial/methods)
- Line-edit model
- Style model
- Reconciliation model

## 18. Privacy / Network Boundaries

Default privacy posture:
- `strict_offline: true`
- Ollama localhost only enforced by provider.
- citation fetch is bypassed in strict offline.

Potential network surfaces when not strict offline:
- citation fetch methods (Unpaywall/OpenAlex/Semantic Scholar/EuropePMC/NCBI APIs).

No hidden cloud fallback in core chat/embed path:
- review/deep-run use configured local Ollama provider.

## 19. Where to Extend Safely

A. Add new paper-download methods:
- file: `ai_reviewer/review/citation_fetcher.py`
- add method function + register in `REGISTERED_CITATION_METHODS`
- add method name to config `citation_fetch.methods`

B. Improve orchestrator policy:
- file: `ai_reviewer/orchestrator/controller.py`
- tune deterministic thresholds and retry logic

C. Improve suggested rewrite quality:
- file: `ai_reviewer/review/manuscript_annotation.py`
- improve generation/revision prompts + gating criteria

D. Add true multimodal figure review:
- file: `ai_reviewer/figures/figure_review.py`
- integrate VLM call path; keep explicit fallback labels

E. Adjust deep-run stage model routing:
- file: `ai_reviewer/review/deep_run.py`
- keep role safety: embedding models never routed to chat

## 20. Current Known Gaps (Honest)

- QC/scoring artifacts are currently mostly diagnostic; they do not yet fully gate final emission everywhere.
- Figure critique is text/caption contextual unless multimodal support is configured.
- Some output quality limitations remain model/prompt constrained, especially in weak/sparse runs.

## 21. Quick Trace: One Real Run

For `review --project <id> --profile balanced`:
1. Health/model table
2. project lock acquire
3. citation prefetch stage
4. training sync + guidance injection
5. run_review + optional orchestrator retry
6. annotated DOCX + suggested changes generation
7. validations and output verifier
8. lock release
9. run summary + stored metadata

For `deep-run --project <id>`:
1. lock acquire
2. citation prefetch
3. multi-stage deep pipeline
4. reconciliation + reconciliation QC
5. final report + commented/suggested DOCX
6. deep-run verification
7. lock release

## 22. File-Level Map (Most Important)

- `ai_reviewer/cli.py`: workflow orchestration and run lifecycle
- `ai_reviewer/review/engine.py`: standard review generation + bundle writing
- `ai_reviewer/review/deep_run.py`: staged deep-run orchestration and synthesis
- `ai_reviewer/review/manuscript_annotation.py`: comment/span/rewrite mapping and manifests
- `ai_reviewer/review/citation_fetcher.py`: pre-run OA citation download and DOI cache
- `ai_reviewer/orchestrator/controller.py`: deterministic + optional LLM QA/retry controller
- `ai_reviewer/review/rigorous_adapters.py`: new specialist/reconciliation QC scoring adapters
- `ai_reviewer/tools/docx_tools.py`: DOCX comment/suggested-changes IO + validation
- `ai_reviewer/models/selector.py`: model typing and role routing
- `ai_reviewer/models/ollama_provider.py`: provider safety and endpoint calls
- `ai_reviewer/ops/locks.py`: project lock concurrency semantics
- `ai_reviewer/output_verifier.py`: hard output integrity checks

---
This report is intentionally implementation-grounded so another LLM can reason about real control flow and extension points without reverse-engineering the full repo.
