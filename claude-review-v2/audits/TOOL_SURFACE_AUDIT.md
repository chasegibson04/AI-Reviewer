# TOOL_SURFACE_AUDIT
Date: 2026-04-04

## Required review tools
Implemented in TS tool registry (`src/tools.ts`) and exposed by Python bridge (`review_mcp_server.py`):
- inspect_project
- discover_manuscript
- parse_docx
- parse_pdf
- map_sections
- digest_manuscript
- analyze_terminology
- analyze_coherence
- analyze_methods
- analyze_figures_tables
- analyze_citations
- analyze_journal_format
- generate_line_edits
- arbitrate_review
- render_outputs
- validate_outputs
- replay_run
- diff_run
- benchmark_project

## End-to-end usability status
- Bridge-level usability: verified by `tests/test_mcp_review.py` and overnight runner.
- TS-wrapper usability: wrappers resolve `mcp__review_bridge__*` tools and delegate.
- Fallback behavior:
  - Most wrappers fail clearly if bridge is missing.
  - `inspect_project` and `discover_manuscript` now try bridge first, then local fallback.

## Fixed this phase
- Corrected schema drift in:
  - `AnalyzeMethodsTool`
  - `ArbitrateReviewTool`
- Removed misleading fake success fallback in `ParseDocxTool`.

## Remaining weak areas
- Tool output sophistication is still heuristic in bridge.
- Some wrapper schemas still use `z.any()` for output (type looseness).
