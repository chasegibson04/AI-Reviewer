# AI-Reviewer TS-Python Bridge

This directory contains the local bridge server used by the TypeScript OpenClaude shell to execute manuscript-review tools in Python.

## Layer ownership

### TypeScript shell (Layer A)
- Command UX and session behavior.
- Startup/project-awareness messaging.
- Tool registration and orchestration through MCP tool calls.
- Provider/profile routing with local-first defaults.

### Python bridge (Layer B)
- Manuscript discovery and parsing (`.docx`, `.pdf`).
- Domain analyses (terminology, coherence, methods, citations, format).
- Artifact rendering (`run_summary`, manifests, ledgers, reports, transcript, event logs).
- Artifact validation and replay/diff/benchmark helpers.

## Transport and contract
- Local stdio JSON-RPC methods: `initialize`, `tools/list`, `tools/call`.
- Tool responses are returned as MCP-style `content[type=text]` JSON payloads.
- Event logs are written per run:
  - `tool_event_log.jsonl`
  - `network_event_log.jsonl`

## Dependency behavior
- The bridge optionally uses `ai_reviewer.ingest.loaders` when available.
- If `ai_reviewer` parser dependencies are unavailable, fallback local parsers are used:
  - DOCX: zipped XML (`word/document.xml`) extraction.
  - PDF: heuristic byte-text extraction.
- This keeps the bridge runnable in constrained local environments.

## Policy
- Blocked project snippets enforced in bridge: `pampa`, `horseshoe`.

## Environment requirements
- Python 3.10+
- No mandatory Python MCP package required for bridge runtime.
- Optional parser quality upgrades come from installed `ai_reviewer` parser dependencies.
