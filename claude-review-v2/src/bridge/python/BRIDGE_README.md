# AI-Reviewer TS↔Python Bridge

This directory contains the Python-based MCP server that bridges the TypeScript OpenClaude shell to the `ai_reviewer` domain logic.

## Responsibilities

### TypeScript Shell (Layer A)
- **UI/UX**: Ink-based rendering, terminal input, streaming output.
- **Session Management**: History, context compression, tool block rendering.
- **Orchestration**: Guiding the agent through the staged review workflow.
- **Provider Routing**: Mapping model aliases to local Ollama endpoints.

### Python Bridge (Layer B)
- **Document Ingest**: Structured parsing of `.docx` and `.pdf` files.
- **Domain Logic**: Deep scientific analysis (methods skepticism, coherence, terminology).
- **Artifact Generation**: Producing JSON manifests and Markdown reports.
- **Validation**: Ensuring outputs adhere to the required scientific schemas.

## Protocol

The bridge uses the **Model Context Protocol (MCP)** over stdio.

### Key Tools
- `inspect_project`: Environment and manuscript detection.
- `parse_docx` / `parse_pdf`: Content extraction.
- `analyze_methods`: Specialized methodological critique.
- `render_outputs`: Artifact production.

## Environment Requirements
- Python 3.10+
- `python-docx`, `pypdf`, `mcp` (Python package)
- Ollama (running on localhost:11434)
