# Architecture

`claude-review-v2` uses a two-layer local architecture.

## Layer A: TypeScript shell (OpenClaude-style)

Primary responsibilities:
- Interactive terminal session and command UX.
- Slash command orchestration (`/project`, `/review`, `/deep-run`, `/doctor`, `/diagnose`, `/artifacts`, `/replay`, `/diff`, `/profile`).
- Profile selection and local-first model routing metadata.

Key paths:
- `src/commands/`
- `src/utils/model/reviewProfiles.ts`
- `src/entrypoints/`, `src/screens/`, `src/ink/`

## Layer B: Python review bridge

Primary responsibilities:
- Manuscript discovery/parsing (`.docx`, `.pdf`).
- Domain analyses (terminology, coherence, methods, citations, figures/tables, journal format).
- Artifact rendering and validation.
- Replay, diff, and benchmark helpers.

Key path:
- `src/bridge/python/review_mcp_server.py`

## Bridge contract

Transport:
- Local stdio JSON-RPC (MCP-style methods):
  - `initialize`
  - `tools/list`
  - `tools/call`

Delegation model:
- TS command/tool layer emits tool calls.
- Python bridge executes domain logic.
- Bridge returns structured JSON payloads in MCP text content.

## Artifact flow

Per run, bridge writes artifacts such as:
- `run_summary.json`
- `routing_trace.json`
- `manuscript_comment_manifest.json`
- `tool_event_log.jsonl`
- `network_event_log.jsonl`
- `validation_report.json`
- `session_transcript.md`

## Local-first behavior

- Ollama is the expected local backend.
- Profile resolution is explicit and surfaced in `/profile`, `/doctor`, and `/diagnose`.
- Big-model profiles prefer Gemma 4 where detected.
- Blocked project snippets (`pampa`, `horseshoe`) are enforced in bridge policy.
