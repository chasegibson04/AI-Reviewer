# Architecture

`claude-review-v2` is a two-layer local architecture with an explicit shell/bridge split.

## Layer A: TypeScript Shell (OpenClaude-style)

Primary ownership:

- Interactive terminal UX and slash command loop.
- Guided workflow orchestration (`/wizard`, `/project`, `/profile`, `/review`, `/deep-run`).
- Deep-run mode choice prompt (MOE vs single-model Gemma 4).
- Runtime summaries shown to users.
- Dispatch of bridge tool calls.

Key paths:

- `scripts/line-repl.js` (interactive manuscript-first command loop)
- `scripts/launch.js` (launch entrypoint and launch-plan routing)
- `src/commands/` (command surfaces and command tests)
- `src/utils/model/reviewProfiles.ts` (profile definitions and defaults)
- `src/commands/review/runParameters.ts` (profile/mode arg parsing)

## Layer B: Python Bridge

Primary ownership:

- Manuscript parse/load and section mapping helpers.
- Stage-by-stage deep review generation.
- Support-paper ingest, structured cache, and cache index output.
- Citation verification (line/sentence-local checks with reference mapping).
- Artifact rendering and run validation.
- Replay/diff helpers.

Key path:

- `src/bridge/python/review_mcp_server.py`

Bridge notes:

- Transport: stdio JSON-RPC compatible with MCP-style methods.
- Methods used: `initialize`, `tools/list`, `tools/call`.
- Tool results returned as JSON payload text.

## Startup and Launch Flow

Default no-arg launch path:

1. user starts launcher wrapper or `node scripts/launch.js`
2. launcher validates runtime config and dist health
3. default target is internal `line_repl` (self-contained)
4. line REPL starts and connects to local Python bridge

Compatibility path (opt-in only):

- `CLAUDE_REVIEW_ALLOW_LEGACY_GUIDED=1` enables parent guided launcher handoff
- this path is disabled by default

## Deep-Run Routing Model

Bridge routing function:

- `_resolve_stage_models(...)`

Requested modes:

- `moe`
- `gemma_single`

`gemma_single` behavior:

- resolves one Gemma target (prefer detected Gemma 4 variants)
- maps all core reasoning stages to that one model target
- maps support-ingest and citation-verification model targets to that same model
- emits degraded fallback reason if Gemma target unavailable

`moe` behavior:

- per-stage candidate model selection from `STAGE_TO_MODEL_CANDIDATES`
- support-ingest/citation-verification prefer Gemma when available, otherwise explicit fallback

## Ingest and Citation Pipelines

Support ingest pipeline:

- resolves support docs from manuscript context/reference hints
- produces structured records with identity/provenance/summaries/evidence chunks
- stores/reuses cache under `.runtime/support_ingest_cache`
- emits `support_ingest_report.json` and `support_ingest_cache_index.json`

Citation verification pipeline:

- extracts citation mentions from manuscript text
- maps mention markers to reference entries
- checks support records per sentence-level claim
- supports abstract-only fallback mode when full source unavailable
- emits `citation_verification_ledger.json` and `claim_verification_summary.json`

## Artifact Contract (High-Value Files)

- `run_summary.json` (top-level run/result mode summary)
- `routing_trace.json` (requested/effective mode, stage model map, degraded flags)
- `manuscript_comment_manifest.json` (visible comment records)
- `manuscript_comment_metadata.json` (expanded metadata)
- `manuscript_suggested_changes_manifest.json` (rewrite suggestions)
- `support_ingest_report.json`
- `support_ingest_cache_index.json`
- `citation_verification_ledger.json`
- `validation_report.json`

## Diagnostics and Honesty Model

The architecture is designed to surface degraded behavior explicitly:

- preflight model probe failures
- stage fallback events (`fallback_error`, `heuristic_only`)
- aggregated fallback reasons in run summary/routing trace
- doctor/diagnose model lane status (short, medium, JSON, ingest, citation, long)
