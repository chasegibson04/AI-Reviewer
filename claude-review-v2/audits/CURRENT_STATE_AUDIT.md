# CURRENT_STATE_AUDIT
Date: 2026-04-03

## Scope audited
- `claude-review-v2/` source, bridge, commands, tools, startup, model routing, tests, and output artifacts.
- Read-only cross-checks against `openclaude-main/`, `ai_reviewer/`, and legacy `claude-review/`.

## What is implemented and wired
- OpenClaude-style shell/session core remains present in `src/main.tsx`, `src/query.ts`, `src/ink/*`, command registry, and tool runner stack.
- Required command names are present and registered: `/project`, `/review`, `/deep-run`, `/artifacts`, `/diagnose`, `/doctor`, `/replay`, `/diff`, `/profile`.
- Manuscript tool modules are registered in `src/tools.ts` and call the local bridge via MCP tool names.
- Python bridge at `src/bridge/python/review_mcp_server.py` serves `initialize`, `tools/list`, and `tools/call` over stdio JSON-RPC.
- Startup messaging is project/manuscript aware via `src/setup.ts` + `src/utils/manuscriptDetection.ts`.

## What was broken and is now fixed in this pass
- Bridge no longer hard-crashes on missing `python-docx`/`ai_reviewer` runtime imports.
- Bridge now uses optional `ai_reviewer` parsing and fallback local parsers for DOCX/PDF when deps are unavailable.
- Bridge responses were oversized for line-based test clients; parse output now bounded to prevent stream limit overrun.
- Validation now persists `validation_report.json` in output runs.
- Block policy (`pampa`, `horseshoe`) is enforced directly in bridge logic.

## What remains partial
- Bridge analysis quality is deterministic and real but still heuristic (not full parity with deep AI-Reviewer inference pipeline).
- Full TS shell runtime parity validation is blocked in this environment because Bun is not installed.
- Global TypeScript `typecheck` for the OpenClaude-derived tree still has extensive pre-existing compile errors and missing internal assumptions.

## Build/runtime blocker status
- `bun` missing (`command not found`) prevents canonical `bun run build` path in this environment.
- Node fallback works for limited tests (`test:provider-recommendation`) but not full runtime parity for Bun-specific imports/macros.

## Honest overall state
- The bridge/tool domain is materially real and executable locally with artifact generation and validation evidence.
- Full OpenClaude runtime parity and full AI-Reviewer deep-run parity are not yet proven in this environment.
