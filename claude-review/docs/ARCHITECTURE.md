# `claude-review` Architecture

`claude-review` is a terminal-first workstation that bridges the high-performance UX of `Claude Code` (via `OpenClaude`) with the specialized scientific review intelligence of `AI-Reviewer`.

## 1. Concept Mapping

### From OpenClaude/Claude Code to `claude-review`
| OpenClaude Concept | `claude-review` Equivalent | Purpose |
| :--- | :--- | :--- |
| **Terminal UX** | `review interactive` | High-signal, streaming feedback, visible tool calls. |
| **Provider/Shim** | `ProviderManager` | Unified interface for local (Ollama) and remote (OpenAI/Anthropic) models. |
| **Doctor/Hardening** | `review doctor` | Runtime sanity checks, reachability, and profile validation. |
| **Tool Execution** | `ReviewTools` | Specialized tools for manuscript parsing, sectioning, and annotation. |
| **Slash Commands** | `/review`, `/fix`, `/export` | Fast, terminal-native shortcuts for complex tasks. |

### From AI-Reviewer to `claude-review`
| AI-Reviewer Concept | `claude-review` Equivalent | Purpose |
| :--- | :--- | :--- |
| **Deep Run Pipeline** | `ReviewPipeline` | Multi-stage, layered review workflow. |
| **Profiles** | `ReviewProfiles` | Configurations for balanced, adversarial, and methods-focused review. |
| **Artifacts** | `RunProject` | Persistent JSON manifests and annotated manuscript outputs. |
| **Orchestrator** | `StageController` | Quality evaluation and retry logic for individual stages. |
| **Context Pack** | `SupportContext` | Linking manuscript to supporting literature and style guides. |

## 2. Review Pipeline Stages
The pipeline is designed as a series of specialized, state-persistent stages. Each stage can use a different model (routing) based on complexity:

1.  **Ingest & Index:** Normalize DOCX/PDF, extract text, and build section map.
2.  **Structural Triage:** Rapid analysis of flow, missing sections, and citation density.
3.  **Digestion:** Deep analysis of manuscript and supporting literature.
4.  **Verification:** Semantic claim verification against supporting evidence.
5.  **Critique Layers:**
    - **Balanced:** Broad evaluation of strengths/weaknesses.
    - **Hostile:** Adversarial critique focused on rigor and overclaiming.
    - **Methods:** Strict evaluation of methodological soundness.
6.  **Refinement:** Style alignment, line-edits, and format compliance.
7.  **Reconciliation:** Arbitration of conflicting critiques into a unified revision plan.
8.  **Annotation:** Rendering comments and suggestions into the final DOCX.

## 3. CLI / Session Loop
The `review interactive` mode provides a persistent agentic session:
- **Input:** User prompts or slash commands.
- **Process:** Agent uses tools to inspect the manuscript or run pipeline stages.
- **Feedback:** Streaming text, visible tool execution headers, and real-time status updates.
- **Output:** Immediate console feedback plus background artifact generation.

## 4. Provider & Routing Model (MoE-Style)
`claude-review` uses a goal-aware routing system:
- **Fast Profile:** Uses `gpt-4o-mini` or `llama-3-8b` for indexing and triage.
- **Reasoning Profile:** Uses `o1-preview` or `deepseek-v3` for critique and arbitration.
- **Local Profile:** Defaults to `ollama` with `qwen2.5-coder:14b` for privacy-first workflows.

Routing is defined in `config/profiles.yaml` and can be overridden per run.

## 5. Project & Artifact Data Model
- **Project Root:** `claude-review/projects/<project_id>/`
- **Source:** `source/manuscript.docx`
- **Manifests:** `runs/<timestamp>/manifest.json` (Stage status, model stack, and file links).
- **Stage Outputs:** `runs/<timestamp>/stages/stage_<XX>_<name>.json` (Raw and parsed results).
- **Final Output:** `outputs/` (Commented DOCX and suggested-changes JSON).

## 6. Console UX & Visibility

### Tool Visibility
Every tool call is displayed with its intent and status:
`[tool] parse_docx | source=manuscript.docx | status=success | duration=450ms`

### Network Logging
Any online interaction is explicitly logged:
`[network] openai | chat/completions | model=gpt-4o | status=streaming | size=1.2kb`

### Step Headers
The terminal uses clear, concise headers for each pipeline stage:
`--- STAGE 05: CONTEXT LINKING ---`
`Linking 15 claims to 4 supporting papers...`

## 7. Logging & Reproducibility
- Every session is logged to `logs/session_<timestamp>.log`.
- `ReviewPipeline` results include `seed`, `temperature`, and `fingerprint` for full reproducibility.
- `review doctor` captures environmental snapshots for debugging.
