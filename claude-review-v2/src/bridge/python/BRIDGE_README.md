# AI-Reviewer TS-Python Bridge

This bridge is the review-domain backend for `claude-review-v2`.

## Purpose

- Provide manuscript review tools to the TypeScript shell through local stdio JSON-RPC.
- Keep Layer A (shell/session) and Layer B (domain analysis/render/validation) cleanly separated.

## Layer ownership

TypeScript shell (Layer A):
- command UX and session behavior
- profile/routing selection and run-mode narration
- tool orchestration through bridge calls

Python bridge (Layer B):
- manuscript discovery and parsing
- review analyses and arbitration helpers
- artifact generation, validation, replay, diff, benchmark

## Transport

- `initialize`
- `tools/list`
- `tools/call`

Tool result payloads are returned as text JSON content.

## Outputs

Bridge writes run artifacts, including:
- `run_summary.json`
- `routing_trace.json`
- `manuscript_comment_manifest.json`
- `manuscript_suggested_changes_manifest.json`
- `tool_event_log.jsonl`
- `network_event_log.jsonl`
- `validation_report.json`
- `session_transcript.md`

## Dependency behavior

- Runs without requiring external repo layout.
- Optional `ai_reviewer` package is used when installed in Python environment.
- Fallback parsers are used when optional parser package is unavailable.

## Policy guardrails

Bridge blocks projects containing:
- `pampa`
- `horseshoe`
