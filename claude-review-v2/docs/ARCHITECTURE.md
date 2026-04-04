# Architecture

The `claude-review-v2` product follows a distinct two-layer architecture, combining the interactive terminal session model of OpenClaude with the rigorous review pipeline of AI-Reviewer.

## Layer A: OpenClaude-style Agent Shell

This layer represents the outer shell and user-facing terminal interface. It is responsible for providing a familiar, real-time, streaming execution experience.

**Core Components:**
- **Session Loop (`src/entrypoints/`, `src/screens/`):** Manages the primary user interaction loop and command execution.
- **Terminal Rendering (`src/ink/`):** Streams assistant and tool output.
- **Provider & Routing (`src/utils/model/`, `src/services/api/`):** Local-first profile selection and provider handling (Ollama default in this project configuration).
- **Command Surface (`src/commands.ts`):** Slash command entrypoints (`/project`, `/review`, `/deep-run`, `/doctor`, `/diagnose`, `/profile`, `/artifacts`, `/replay`, `/diff`).

## Layer B: Review Agent Backend

This layer encapsulates the domain-specific manuscript review logic. It exposes the various stages of the AI-Reviewer pipeline as callable "tools" to the Layer A shell.

**Core Components:**
- **Bridge Server (`src/bridge/python/review_mcp_server.py`):** Local MCP-style JSON-RPC tool server for manuscript parsing, analysis, rendering, validation, replay, diff, benchmark.
- **TS Tool Wrappers (`src/tools/*Tool/`):** Tool wrappers that call `mcp__review_bridge__*` tools when bridge is connected.
- **Artifact Rendering/Validation (bridge layer):** JSON/JSONL/Markdown artifact generation and validation implemented in the Python bridge.

## Execution Flow

1. The user launches `claude-review-v2`. Layer A detects the active project environment and local model availability, outputting initial guidance.
2. The user requests a review (e.g., via `/deep-run`).
3. Layer A initializes the run and dispatches review tools through the bridge.
4. Profile/routing metadata is injected into run data (`routing_trace`, `run_summary`).
5. Layer B executes tool operations and returns structured payloads.
6. Layer B writes artifacts (JSON/JSONL/Markdown), then validates output integrity and local-only constraints.
7. Layer A surfaces summaries and next actions.
