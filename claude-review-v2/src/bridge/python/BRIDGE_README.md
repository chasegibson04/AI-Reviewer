# AI-Reviewer TS-Python Bridge (claude-review-v2)

This bridge is Layer B for `claude-review-v2` and owns manuscript-domain review execution.

## Contract Summary

Transport:

- stdio JSON-RPC, MCP-style method surface
- methods used: `initialize`, `tools/list`, `tools/call`

Primary implementation:

- `src/bridge/python/review_mcp_server.py`

## Bridge Responsibilities

- manuscript discovery and parse helpers (`.docx`, `.pdf`)
- section map and digest helpers
- staged deep review generation
- model routing transparency and fallback tracing
- support-paper ingest and cache management
- line/sentence-level citation verification against references
- rendered-page PDF color-palette extraction and report generation
- visible comment composition + manifest metadata export
- suggested change generation
- run artifact rendering and validation
- replay/diff support

## Deep Review Core Flow

1. parse and clean manuscript text
2. derive section map and analysis reports
3. resolve model plan based on profile/mode
4. ingest support docs into structured cache records
5. run line-by-line citation verification pass
6. run stage prompts across stage model map
7. compose concise visible comments + rich manifests
8. write run artifacts and validation outputs

## Color-Palette Audit Flow

Tool:

- `extract_color_palette`

Flow:

1. validate PDF path and blocked-project policy
2. render PDF pages to images
3. downsample and quantize per page
4. merge near-duplicate colors into representative swatches
5. classify representative colors as `viridis_like`, `plasma_like`, or `unmatched`
6. write JSON/CSV/PDF artifacts under an in-subproject output root

Output contract:

- `color_palette_full.json`
- `color_palette_filtered.json`
- `color_palette_full.csv`
- `color_palette_filtered.csv`
- `color_palette_page_usage.json`
- `color_palette_report.pdf`
- `color_palette_debug_montage.png`

Honesty note:

- extraction is based on rendered page pixels
- it is intentionally practical and inspectable, not perfect raw PDF object analysis

## Model Plan Semantics

Resolver:

- `_resolve_stage_models(...)`

Modes:

- `moe`: stage-specific model candidates
- `gemma_single`: one Gemma target applied across main reasoning stages

Degradation model:

- if requested model path unavailable/unusable, fallback is explicit
- routing trace includes `degraded` and `fallback_reason`

## Ingest Cache Semantics

Cache root:

- `.runtime/support_ingest_cache`

Record intent:

- stable source identity/fingerprint
- parsed/derived summaries and evidence blocks
- machine-readable structure for downstream citation checks

Cache lifecycle:

- unchanged source: reuse
- changed source: refresh/re-ingest

## Citation Verification Semantics

- parse citation mentions sentence by sentence
- map markers to reference entries
- check support docs individually where available
- permit abstract-only fallback when full paper unavailable (if enabled)
- label lower-confidence abstract-only checks explicitly

Outputs:

- `citation_verification_ledger.json`
- `claim_verification_summary.json`
- citation-related comment details in manifests

## Comment and Metadata Output Strategy

Visible comments (`manuscript_comment_manifest.json`):

- concise human-readable editorial note style

Metadata (`manuscript_comment_metadata.json` and supporting ledgers):

- stage/source/status/confidence/fallback context
- evidence pointers and ingest/citation traceability

## Reliability and Diagnostics

- model probes feed diagnostic commands (`/doctor`, `/diagnose`)
- stage fallback states are persisted in `routing_trace.json`
- network and tool activity are logged (`network_event_log.jsonl`, `tool_event_log.jsonl`)

## Policy Guards

Bridge blocks known disallowed project snippets in path segments:

- `pampa`
- `horseshoe`
- `test-d2b`

This is enforced before manuscript operations proceed.
