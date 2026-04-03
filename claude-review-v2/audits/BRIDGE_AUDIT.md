# BRIDGE_AUDIT
Date: 2026-04-03

## Bridge topology
- TS layer invokes MCP tool names (`mcp__review_bridge__*`) from manuscript tool wrappers.
- Python bridge process: `src/bridge/python/review_mcp_server.py`.
- Transport: local stdio JSON-RPC with `initialize`, `tools/list`, `tools/call`.

## Implemented tool surface
- Implemented handlers:
  - `inspect_project`, `discover_manuscript`, `parse_docx`, `parse_pdf`, `map_sections`, `digest_manuscript`
  - `analyze_terminology`, `analyze_coherence`, `analyze_methods`, `analyze_figures_tables`, `analyze_citations`, `analyze_journal_format`
  - `generate_line_edits`, `arbitrate_review`, `render_outputs`, `validate_outputs`, `replay_run`, `diff_run`, `benchmark_project`

## Runtime hardening added
- Optional import path for `ai_reviewer.ingest.loaders`; graceful fallback parsing when unavailable.
- Fallback DOCX extraction via zipped XML (`word/document.xml`) and fallback PDF byte-text heuristics.
- Blocked project policy (`pampa`, `horseshoe`) applied to project names and paths.
- Tool/network logging emitted to artifact outputs (`tool_event_log.jsonl`, `network_event_log.jsonl`).

## Contract and artifact behavior
- `render_outputs` writes required review artifacts plus session transcript and logs.
- `validate_outputs` checks required files, JSON/JSONL parseability, front-matter target violations, and remote network host usage.
- `validate_outputs` now also writes `validation_report.json`.

## Remaining bridge limitations
- Analysis logic is rule-based; no live LLM arbitration inside bridge yet.
- MCP framing is newline JSON-RPC only, not full `Content-Length` framed protocol.
- PDF fallback parser quality is limited compared with full parser dependencies.

## Evidence
- `claude-review-v2/tests/test_mcp_review.py` passes end-to-end.
- Fresh artifacts produced under `claude-review-v2/test_outputs/pytest_bridge_run_a/` and `_b/`.
