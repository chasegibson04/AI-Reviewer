# `claude-review` Implementation Plan

This document outlines the milestones, file/folder structure, and testing plan for the `claude-review` terminal workstation.

## Milestone 1: Scaffolding & Core Architecture
- **Goal:** Set up the self-contained TypeScript/Bun environment and basic CLI loop.
- **Tasks:**
    - Initialize `package.json` with necessary dependencies (Bun, Ink, Commander, etc.).
    - Implement the `review doctor` command for environment validation.
    - Create the `ProjectManager` for handling project-specific directories and artifacts.
- **Artifacts:** `package.json`, `src/index.ts`, `src/commands/doctor.ts`.

## Milestone 2: Provider & Router Layer
- **Goal:** Implement the `ProviderManager` and the smart-router for MoE-style model selection.
- **Tasks:**
    - Build the `openaiShim` for unified provider support (Ollama, OpenAI, Anthropic).
    - Implement goal-based model selection (`latency`, `balanced`, `quality`).
    - Create the profile configuration system (`profiles.yaml`).
- **Artifacts:** `src/services/provider/`, `src/services/router/`, `config/profiles.yaml`.

## Milestone 3: Review Pipeline (Stage 1-6)
- **Goal:** Implement the ingestion, indexing, and initial critique layers.
- **Tasks:**
    - Build the `DocumentParser` (leveraging existing AI-Reviewer tool patterns).
    - Implement `StructuralReview` and `Digestion` stages.
    - Add the `VerificationTool` for semantic claim checking.
- **Artifacts:** `src/pipeline/stages/`, `src/services/parser/`.

## Milestone 4: Terminal UX & Streaming
- **Goal:** Create a high-signal terminal interface with real-time feedback.
- **Tasks:**
    - Implement the `ReviewSession` with streaming assistant output.
    - Create visible headers for tool calls and network events.
    - Build the diagnostic panel and session transcript logger.
- **Artifacts:** `src/ui/`, `src/services/logger/`.

## Milestone 5: Output & Validation
- **Goal:** Generate final deliverables and perform quality audits.
- **Tasks:**
    - Implement the `CommentGenerator` for DOCX annotation.
    - Create the `ValidationManifest` for run-level quality auditing.
    - Build the `review export` command.
- **Artifacts:** `src/pipeline/stages/annotation.ts`, `src/commands/export.ts`.

## Milestone 6: Hardening & Benchmarking
- **Goal:** Ensure stability and measure performance against approved targets.
- **Tasks:**
    - Implement the `benchmark` command.
    - Run hardening checks (smoke tests + runtime diagnostics).
    - Validate output quality against the `miniaturization_d2b` project.
- **Artifacts:** `src/commands/benchmark.ts`, `tests/`.

---

## Folder Tree Plan
```
claude-review/
├── bin/                # Executable CLI entrypoint
├── config/             # Default and user profiles
├── docs/               # Architecture, pipeline, and plans
├── projects/           # Local project storage (manuscripts, artifacts)
├── reports/            # Doctor and benchmark reports
├── src/
│   ├── commands/       # CLI command definitions (doctor, run, export)
│   ├── pipeline/       # Review pipeline stages and orchestration
│   ├── services/       # Core services (provider, router, parser, logger)
│   ├── ui/             # Terminal UX components (streaming, headers)
│   ├── utils/          # Shared utilities (file, path, json)
│   └── index.ts        # Main application entrypoint
├── tests/              # Unit and integration tests
├── package.json        # Dependencies and build scripts
└── tsconfig.json       # TypeScript configuration
```

## Test Plan
- **Unit Tests:** Test individual services (router, parser, shim) in isolation using `bun:test`.
- **Integration Tests:** Test the full `ReviewPipeline` with mock model responses.
- **UI Tests:** Use `ink-testing-library` to validate terminal rendering.
- **E2E Tests:** Run a limited review pipeline on dummy manuscripts to verify end-to-end flow.

## Risks & Mitigations
- **Risk:** High latency on local models.
- **Mitigation:** Implement `latency` goal in router to use smaller/faster models for non-critical stages.
- **Risk:** Hallucinated citations or claims.
- **Mitigation:** Strict `ValidationPass` stage and visible network logging for metadata lookups.
- **Risk:** Large context window limits.
- **Mitigation:** Use aggressive chunking and section-focused digestion stages.
