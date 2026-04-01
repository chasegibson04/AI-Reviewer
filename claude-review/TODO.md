# `claude-review` TODO List

A prioritized checklist for the development of the `claude-review` terminal workstation.

## Phase 1: Discovery & Architecture (COMPLETE)
- [x] Research OpenClaude/Claude Code architecture and session-feel.
- [x] Map AI-Reviewer deep run pipeline to terminal-first workstation.
- [x] Create `README.md` and `docs/ARCHITECTURE.md`.
- [x] Define `REVIEW_PIPELINE.md` with 12 layered stages.
- [x] Create `IMPLEMENTATION_PLAN.md` with milestones and folder tree.
- [x] Define `CONSTRAINTS.md` for safety and boundary enforcement.
- [x] Propose `COMMAND_SURFACE.md` with top-level and slash commands.
- [x] Establish `BENCHMARK_PLAN.md` with approved targets and KPIs.

## Phase 2: Environment & Core (In Progress)
- [ ] Initialize `package.json` and `tsconfig.json`.
- [ ] Scaffold the project directory structure.
- [ ] Implement `review doctor` command for environment validation.
- [ ] Build the `ProjectManager` for project/run/artifact persistence.
- [ ] Set up the basic `commander` CLI entrypoint.

## Phase 3: Provider & Routing (Next)
- [ ] Implement `ProviderManager` with `openaiShim`.
- [ ] Build the `RouterService` for goal-aware model selection.
- [ ] Create default `config/profiles.yaml`.
- [ ] Implement provider login/auth flows.

## Phase 4: Pipeline Stages
- [ ] Implement Stage 1 & 2: Ingest, parsing, and structural triage.
- [ ] Implement Stage 3: Manuscript and supporting literature digestion.
- [ ] Implement Stage 4 & 5: Terminology audit and flow analysis.
- [ ] Implement Stage 6: Methods, rigor, and hostile critique layer.
- [ ] Implement Stage 7 & 8: Figure/table audit and citation verification.
- [ ] Implement Stage 9 & 10: Line-edits and reconciliation.
- [ ] Implement Stage 11 & 12: Annotation rendering and final validation.

## Phase 5: Terminal UX
- [ ] Implement streaming assistant output.
- [ ] Build the `ReviewSession` with visible tool execution headers.
- [ ] Implement interactive slash commands.
- [ ] Create the diagnostic/status panel.

## Phase 6: Hardening & Export
- [ ] Implement `review export` with DOCX and JSON delivery.
- [ ] Implement `review benchmark` command.
- [ ] Run end-to-end tests on approved benchmark targets.
- [ ] Final project-wide audit and stabilization.

---

## Dependencies to Add
- `bun` (Runtime and package manager)
- `commander` (CLI framework)
- `ink` (React-based terminal UI)
- `openai` (Unified SDK for shim)
- `zod` (Schema validation)
- `yaml` (Configuration parsing)
- `docx` (Word document generation)
- `pdf-parse` (PDF extraction)
- `chalk` (Terminal styling)
- `ora` (Spinners and status indicators)
- `ajv` (JSON schema validation)
