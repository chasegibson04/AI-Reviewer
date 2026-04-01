# `claude-review` Command Surface

`claude-review` provides a terminal-native workstation interface with top-level commands, an interactive mode, and slash-command shortcuts.

## Top-Level Commands

| Command | Purpose |
| :--- | :--- |
| `review login` | Configure LLM providers (Ollama, OpenAI, etc.). |
| `review init <path>` | Initialize a review project from a DOCX/PDF file. |
| `review doctor` | Run runtime, provider, and reachability diagnostics. |
| `review run` | Execute the full multi-stage review pipeline. |
| `review export` | Generate the final commented DOCX and JSON artifacts. |
| `review interactive` | Enter a persistent, streaming agentic session. |
| `review project <id>` | List artifacts and status for a specific project. |
| `review benchmark` | Run performance and quality tests on approved targets. |

## Interactive Mode (`review interactive`)

The interactive mode provides a persistent agent session with the following behaviors:
- **Streaming Assistant:** Real-time text output from the review agent.
- **Tool Visibility:** Clearly separated headers for tool calls (e.g., `parse_docx`, `verify_claim`).
- **Context Awareness:** The agent can access any artifact or stage result from the current project.
- **Drafting:** Ability to propose and refine individual edits before final export.

### Slash Commands (within Interactive Mode)

- `/review`: Start or resume the full review pipeline.
- `/fix <issue_id>`: Propose a specific fix for a identified issue.
- `/diff`: Show a side-by-side comparison of proposed rewrites.
- `/compact`: Condense the current session history to save tokens.
- `/doctor`: Run a quick diagnostic check of the current session.
- `/export`: Trigger the final annotation and delivery process.
- `/help`: Show all available commands and shortcuts.

## Flags & Options

- `--project-id <id>`: Target a specific existing project.
- `--profile <name>`: Use a predefined provider/routing profile (e.g., `fast`, `balanced`, `max-quality`).
- `--model <name>`: Override the default model for the current session.
- `--local-only`: Force the use of local (Ollama) models only.
- `--verbose`: Show detailed debug logs and tool payloads.
- `--json`: Output machine-readable JSON for all commands (useful for CI/CD).

## Profiles (`config/profiles.yaml`)

Profiles define the model routing for different stages of the review:

- **`fast`**: Prioritizes latency. Uses `gpt-4o-mini` or `llama-3-8b`.
- **`balanced`**: Default profile. Uses `gpt-4o` or `deepseek-v3`.
- **`max-quality`**: Prioritizes depth. Uses `o1-preview` or `claude-3-5-sonnet`.
- **`offline`**: Strict local-only mode. Uses `qwen2.5-coder:14b` or `phi-4`.
