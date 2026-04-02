# Architecture

The `claude-review-v2` product follows a distinct two-layer architecture, combining the interactive terminal session model of OpenClaude with the rigorous review pipeline of AI-Reviewer.

## Layer A: OpenClaude-style Agent Shell

This layer represents the outer shell and user-facing terminal interface. It is responsible for providing a familiar, real-time, streaming execution experience.

**Core Components:**
- **Session Loop (`src/entrypoints/`, `src/screens/`):** Manages the primary user interaction loop, capturing input, and orchestrating responses. It features a conversational interface that guides the user.
- **Terminal Rendering (`src/ink/`):** Utilizes React-inspired streaming to visually represent tool execution, thought processes, and chat history.
- **Provider & Routing (`src/routing/`, `src/services/api/`):** Manages the connection to the backend LLM providers. By default, it prioritizes local models via Ollama (e.g., `mistral-small3.2:latest`, `phi4-reasoning:latest`). It handles stage-aware routing (e.g., selecting the best local model depending on the task).
- **Command Surface (`src/commands.ts`):** Handles slash commands (e.g., `/project`, `/review`, `/deep-run`, `/doctor`, `/diagnose`) to trigger complex agentic workflows or query state.

## Layer B: Review Agent Backend

This layer encapsulates the domain-specific manuscript review logic. It exposes the various stages of the AI-Reviewer pipeline as callable "tools" to the Layer A shell.

**Core Components:**
- **Review Tools (`src/tools/review/`):** These tools map to the stages of manuscript review:
  - Ingestion (e.g., `parse_docx`, `parse_pdf`)
  - Mapping (e.g., `map_sections`)
  - Digestion (e.g., `digest_manuscript`)
  - Analysis Stages (e.g., `analyze_methods`, `analyze_coherence`, `analyze_terminology`, `analyze_figures_tables`, `analyze_citations`)
  - Editing (e.g., `generate_line_edits`)
  - Arbitration (e.g., `arbitrate_review`)
- **Schema Validation (`src/review/validation/schemas.ts`):** Defines strict, typed interfaces for the output artifacts (issues, comments, metadata) produced by the review tools, ensuring compliance with the system's standards.
- **Artifact Rendering (`src/review/render/render_outputs.ts`):** Converts the processed and validated analysis artifacts into concrete outputs, such as heavily commented DOCX files and JSON validation manifests.

## Execution Flow

1. The user launches `claude-review-v2`. Layer A detects the active project environment and local model availability, outputting initial guidance.
2. The user requests a review (e.g., via `/deep-run`).
3. Layer A initializes the run and begins dispatching tasks to Layer B tools.
4. The router assigns the appropriate local model for the specific task.
5. As Layer B tools execute, they yield progress and reasoning back to Layer A, which streams this output to the user.
6. Once the pipeline completes, Layer B generates the final artifacts (manifests and DOCX files).
7. Layer A provides a summary to the user.
