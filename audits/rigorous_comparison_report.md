# Rigorous vs AI-Reviewer Comparison Report

Date: 2026-03-28  
Scope: Inspection + comparative analysis only (no integration/merge code changes from Rigorous into AI-Reviewer).

## 1) Executive Summary

`rigorous-main` is an API-first, OpenAI-centric, multi-agent review reporter that produces JSON category outputs and a polished PDF report.  
AI-Reviewer is a project-scoped, local-first editorial workflow system with run traceability, orchestrated multi-stage review options, and author-facing DOCX deliverables (comments + suggested changes).

Bottom line:
- Rigorous is stronger in **explicit reviewer-role decomposition** and **report narrative packaging**.
- AI-Reviewer is stronger in **local/privacy posture**, **operational robustness**, **artifact traceability**, and **manuscript-embedded revision deliverables**.
- Direct merge does not make sense. The best path is **concept borrowing** (specialist role patterns + QC schemas) adapted to AI-Reviewer architecture.

## 2) Project Access Guard

Approved validation projects:
- `20260325163524_test-existingphactorpaper`
- `20260327051312_miniaturization_d2b`

Blacklisted:
- `20260324221200_horseshoe_crabs1`

Guard reference:
- `audits/project_access_guard.md`

No horseshoe-crab project content was inspected.

## 3) What Was Inspected in `rigorous-main`

### Top-level
- `rigorous-main/README.md`
- `rigorous-main/Agent1_Peer_Review/README.md`
- `rigorous-main/Agent2_Outlet_Fit/README.md`
- `rigorous-main/.env.example`

### Agent1 core implementation
- Entry scripts:
  - `run_local_aipeer_review.py`
  - `run_analysis.py`
  - `run_quality_control.py`
  - `run_executive_summary.py`
- Core:
  - `src/core/config.py`
  - `src/core/base_agent.py`
  - `src/core/report_template.py`
- Controller/orchestration:
  - `src/reviewer_agents/controller_agent.py`
- QC/synthesis:
  - `src/reviewer_agents/quality/quality_control_agent.py`
  - `src/reviewer_agents/executive_summary_agent.py`
- Parsing/output:
  - `src/utils/pdf_parser.py`
  - `src/utils/combine_results.py`
  - `pdf_generator.py`
- Example config:
  - `manuscript.json`

### Inventory findings
- Specialized agents (from code): section 10, rigor 7, writing 7, quality 1, executive/controller 2 top-level.
- Requirements file present, no lockfile.
- No test suite found in repo (`0` test files detected by `test*.py` scan).

## 4) What Was Inspected in AI-Reviewer

### Product and docs
- `README.md`
- `docs/ai_reviewer/WORKFLOW_MECHANICS.md`
- `docs/ai_reviewer/SECURITY.md`
- `docs/ai_reviewer/PRIVACY_AUDIT.md`

### Core runtime and config
- `ai_reviewer/cli.py`
- `ai_reviewer/config.py`
- `config/defaults.yaml`
- `ai_reviewer/models/selector.py`
- `ai_reviewer/models/ollama_provider.py`

### Review stack
- `ai_reviewer/review/engine.py`
- `ai_reviewer/review/deep_run.py`
- `ai_reviewer/review/manuscript_annotation.py`
- `ai_reviewer/review/citation_fetcher.py`
- `ai_reviewer/orchestrator/controller.py`

### Operational/quality footprint
- tests directories + full test suite structure
- project/run storage and lock handling via CLI + ops modules

Inventory snapshot:
- `ai_reviewer/*.py` files: 58
- `tests/*.py` files: 57

## 5) High-Level System Summaries

### A) Rigorous (what it is)
- Problem target: comprehensive peer-review style feedback as structured reports.
- Entry point: `run_local_aipeer_review.py`.
- Main flow:
  1. Parse manuscript PDF.
  2. Run 24 specialist agents + controller.
  3. Combine outputs into section/rigor/writing JSONs.
  4. Run quality-control agent over category outputs + manuscript text.
  5. Run executive-summary agent.
  6. Generate PDF report.
- Main outputs:
  - per-agent JSON
  - combined category JSON
  - quality control JSON
  - executive summary JSON
  - final PDF report.
- Assumptions:
  - OpenAI API key expected.
  - Cloud/API-first runtime.
  - PDF-input-centric.
  - Report-centric deliverables, not inline manuscript editing.

### B) AI-Reviewer (what it is)
- Problem target: local-first manuscript review/editing workflows with repeatable project artifacts.
- Entry points: `ai-reviewer` CLI workflows (`review`, `deep-run`, `compare`, `evaluate-paper`, project commands).
- Main flow (review/deep-run):
  1. Project/material sync.
  2. Pre-run citation fetch (configurable methods).
  3. Guidance injection.
  4. Review/deep staged analysis with optional orchestrator QA.
  5. Author-facing outputs: commented DOCX + suggested-changes DOCX + manifests + validation.
- Main outputs:
  - structured review report files (`.json/.md/.txt/.docx`)
  - comment/suggested-change manifests + validations
  - run metadata/debug logs
  - deep-run stage artifacts.
- Assumptions:
  - local Ollama first.
  - strict-offline enabled by default.
  - project-local persistence and auditability.

## 6) Architecture Comparison (Direct)

## 6.1 Decomposition and orchestration
- Rigorous:
  - Hard-coded specialist army (S1–S10, R1–R7, W1–W7).
  - Sequential script pipeline.
  - Controller + QC + executive summary.
- AI-Reviewer:
  - Profile-based review + deep-run staged pipeline.
  - Optional orchestrator QA/retry.
  - Project-scoped CLI workflows, lock/recovery semantics.

Verdict:
- Rigorous cleaner in explicit reviewer-role taxonomy.
- AI-Reviewer stronger in production workflow orchestration and operational guardrails.

## 6.2 Prompt architecture and output schemas
- Rigorous:
  - Each agent embeds large in-code prompts requesting detailed JSON with suggestions.
  - QC agent re-requests structured JSON per category.
- AI-Reviewer:
  - Profile prompts + schema validation/repair + deterministic quality gates/manifests.
  - Richer artifact-level validation path.

Verdict:
- Rigorous stronger in role-specific prompt specialization density.
- AI-Reviewer stronger in output validation and artifact integrity checks.

## 6.3 Deliverables and author usability
- Rigorous:
  - High-quality consolidated PDF report.
  - No native commented manuscript DOCX pipeline.
- AI-Reviewer:
  - Commented manuscript DOCX.
  - Suggested-changes DOCX with visible suggested edits.
  - Per-change provenance/validation.

Verdict:
- AI-Reviewer clearly stronger for revision-ready, manuscript-embedded deliverables.

## 6.4 Privacy/provider assumptions
- Rigorous:
  - `OPENAI_API_KEY` required by core config/base agent.
  - Manuscript text sent to API by design.
- AI-Reviewer:
  - strict offline and localhost Ollama constraints by default.
  - explicit controls for online citation fetch stage.

Verdict:
- Philosophically and operationally different; direct import of Rigorous runtime would break local-first posture.

## 6.5 Testing/evaluation
- Rigorous:
  - No evident automated test suite.
- AI-Reviewer:
  - extensive unit/integration/smoke tests.

Verdict:
- AI-Reviewer materially stronger in regression safety.

## 7) Output/Deliverable Comparison

Rigorous strongest outputs:
- modular category JSON review layers
- polished PDF narrative report
- explicit category score framing.

AI-Reviewer strongest outputs:
- project-local run traceability + metadata
- commented DOCX + suggested-changes DOCX
- validation artifacts for DOCX/comment integrity
- deep-run stage files and orchestrator logs.

Best fit by use case:
- "Editor-style narrative report only": Rigorous has strong structure.
- "Author revising manuscript in place": AI-Reviewer is better aligned.

## 8) Provider/Privacy/Local-First Compatibility

Rigorous compatibility risks if imported directly:
- hard OpenAI dependency in base agent/config.
- no strict local/offline equivalent guard layer.
- cloud-first behavior for manuscript content.

Safe adaptation zone:
- role taxonomies, QC question structure, and scoring schemas
- **not** provider/runtime code.

## 9) Quality-Control and Multi-Agent Pattern Comparison

Rigorous likely quality advantages:
- explicit specialist decomposition across section/rigor/writing.
- explicit second-pass QC and third-pass executive synthesis.

Rigorous weaknesses:
- heavy repeated prompting over full text (cost/latency).
- likely overlap/redundancy across agents.
- no robust deterministic gate layer and no rich test coverage evidence.

AI-Reviewer likely quality advantages:
- deterministic checks + manifests + validations.
- stronger run-level observability and failure handling.

AI-Reviewer likely quality gap vs Rigorous:
- less explicit specialist identity per review dimension in default single-pass profiles (unless deep-run configured aggressively).

## 10) Section Awareness and Manuscript Intelligence

Rigorous:
- strong explicit section agent taxonomy (S1–S10).
- references/supplementary treated as distinct review objects.

AI-Reviewer:
- section mapping + role-based filtering + targeting logic, but quality varies by run/model/profile.
- stronger inline edit pipeline but still quality-sensitive to model and gating.

Likely borrowable source of strength:
- Rigorous-style explicit per-section rubric prompts + QC reconciliation schema.

## 11) Extensibility and Integration Feasibility

Feasibility options:
1. Inspiration-only: **high feasibility, low risk**
2. Prompt/schema donor: **high feasibility, medium risk**
3. Standalone benchmark comparator: **medium feasibility, medium risk**
4. Optional adapter subsystem: **low-medium feasibility, higher complexity**
5. Direct merge: **low feasibility, high risk** (not recommended)

Most realistic:
- Prompt/schema donor + benchmark comparator.

## 12) Sandbox/Runtime Comparison (Stage B)

Attempted:
- `python rigorous-main/Agent1_Peer_Review/run_local_aipeer_review.py`

Observed:
- immediate failure before analysis due to missing dependency:
  - `ModuleNotFoundError: No module named 'pytesseract'`
- also emitted a parser regex `SyntaxWarning`.

Interpretation:
- Rigorous runtime can’t be directly benchmarked in current environment without dedicated dependency setup and API credentials.
- Static comparison remains valid and substantial; empirical full-output side-by-side was partially blocked.

## 13) Borrow / Adapt / Benchmark / Ignore Matrix

### A) BORROW SOON
- Specialist taxonomy pattern:
  - section / rigor / writing role split
- QC category synthesis pattern:
  - one pass to reconcile redundant/contradictory findings
- score normalization schema:
  - clearer category-level scoring definitions.

### B) ADAPT CAREFULLY
- Executive summary synthesis approach:
  - keep but adapt to local-first models and existing deep-run artifacts
- category-specific suggestion schema:
  - adapt to DOCX inline/comment artifact model
- section-agent prompt framing:
  - adapt to AI-Reviewer section-role blocking/targeting rules.

### C) BENCHMARK FIRST
- full 24-agent brute-force pattern:
  - test latency/quality tradeoff vs current deep-run
- QC strictness thresholds:
  - validate improvements in comment sanity + rewrite quality before rollout
- outlet-fit logic:
  - benchmark as optional workflow only.

### D) IGNORE
- Direct OpenAI-key-first runtime architecture
- hardcoded script-chain orchestration replacing project-run system
- web/app commercialization scaffolding from Rigorous README context.

## 14) Recommended Integration Path (No Merge)

1. Build a **Rigorous-inspired rubric pack** inside AI-Reviewer prompts/profiles:
- explicit section/rigor/writing checklists per stage.

2. Add **category reconciliation stage** in deep-run:
- lightweight QC synthesis over produced findings, not full duplicate brute-force reruns.

3. Add **structured scoring schema** compatible with AI-Reviewer manifests:
- preserve local-first + DOCX deliverables.

4. Add **benchmark harness**:
- compare current deep-run vs role-specialized variant on approved projects only.

5. Keep provider/runtime boundaries:
- no OpenAI-hardcoded imports in main workflow path.

## 15) Direct Merge Judgment

Direct merge does **not** make sense.

Reason:
- mismatched provider/privacy assumptions
- mismatched deliverable philosophy (report-centric vs manuscript-edit-centric)
- mismatched operational maturity (tests, locks, project artifacts, validation layers).

Recommended approach:
- selective concept import (prompts/schemas/QC logic), implemented natively in AI-Reviewer architecture.

