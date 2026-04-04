# claude-review-v2

`claude-review-v2` is an OpenClaude-style terminal shell adapted for manuscript review.

It keeps the OpenClaude session/command experience while shifting the tool domain to AI-Reviewer workflows through a local TypeScript-to-Python bridge.

## Current state

What is working now:
- OpenClaude-style interactive shell with manuscript-oriented commands.
- Local-first profile system with explicit MOE and big-model review modes.
- Python bridge (`src/bridge/python/review_mcp_server.py`) for parsing, analysis, artifact rendering, replay/diff, and validation.
- Artifact generation under in-folder run outputs.
- Cross-platform launchers (macOS + Windows) included in this folder.

What is still partial:
- Full standalone Bun/OpenClaude build parity is still environment-sensitive.
- Windows runtime has launcher-level validation and script linting in this environment, but not full native interactive runtime execution.
- Some OpenClaude upstream command modules remain present in source; manuscript command guidance is prioritized in docs and startup flow.

## Repository boundary

All project runtime/docs/tests for this effort are inside `claude-review-v2/`.

Do not use blacklisted projects in validation:
- PAMPA
- horseshoe / horseshoe crab

## Architecture summary

- Layer A (TypeScript shell): OpenClaude-style command/session runtime (`src/`)
- Layer B (Python review backend): local MCP-style bridge (`src/bridge/python/review_mcp_server.py`)
- Bridge contract: JSON-RPC over stdio using `initialize`, `tools/list`, `tools/call`

See [Architecture](docs/ARCHITECTURE.md).

## Commands

Primary manuscript command surface:
- `/project`
- `/review`
- `/deep-run`
- `/artifacts`
- `/diagnose`
- `/doctor`
- `/replay`
- `/diff`
- `/profile`

## Selectable review profiles

- `quick_local`
- `balanced_local`
- `deep_local`
- `local_moe`
- `one_big_model`
- `full_manuscript_final_pass`
- `offline_strict`
- `llama_cpp_standard`
- `llama_cpp_turboquant`
- `gemma4_26b`
- `gemma4_31b`

Default profile: `local_moe`.

### Big-model mode (Gemma 4)

- `one_big_model`: single-model dominant review path.
- `full_manuscript_final_pass`: aggregated final-pass/judge path.
- Preferred model order: `gemma4:26b`, then `gemma4:31b` if detected.
- If Gemma 4 is unavailable, fallback is explicit in diagnostics/run summaries.

## Requirements

- Node.js 20+
- Bun (for build path)
- Python 3.10+
- Ollama running locally for local-first model execution

Optional:
- `ai_reviewer` Python package for richer parsing (bridge falls back when unavailable)

## Launch

### Recommended launcher entrypoint

- `node scripts/launch.js`

This script:
- launches `dist/cli.mjs` when available
- runs `bun run build` automatically when Bun exists and `dist` is missing
- prints explicit recovery commands when prerequisites are missing

### macOS

- `launchers/macos/claude-review-v2.command`
- `launchers/macos/claude-review-v2.sh`

See [macOS setup](docs/MACOS_SETUP.md).

### Windows

- `launchers/windows/claude-review-v2.cmd`
- `launchers/windows/claude-review-v2.bat`
- `launchers/windows/claude-review-v2.ps1`

See [Windows setup](docs/WINDOWS_SETUP.md).

## Diagnostics and smoke

- `bash scripts/doctor_runtime.sh`
- `bash scripts/smoke.sh` (Bun build path)
- `bash scripts/smoke_fallback.sh` (no Bun build required)

## Tests

- `python3 -m pytest -q tests/test_mcp_review.py`
- `python3 tests/overnight_validation_runner.py`
- `npm run test:provider-recommendation`
- `node --test --experimental-strip-types src/utils/model/reviewProfiles.test.ts src/commands/review/runParameters.test.ts`

## Fixtures and outputs

Internal fixtures for validation:
- `fixtures/manuscripts/gan_diffusion.pdf`
- `fixtures/manuscripts/s44160-023-00351-1.pdf`

Run outputs and reports:
- `test_outputs/`
- `reports/`
- `audits/`

## Artifacts written per run

Typical run directories include:
- `source_mode.json`
- `section_map.json`
- `manuscript_comment_manifest.json`
- `manuscript_suggested_changes_manifest.json`
- `support_ingest_report.json`
- `support_usage_ledger.json`
- `assertion_ledger.json`
- `claim_verification_summary.json`
- `citation_verification_ledger.json`
- `format_compliance_report.json`
- `terminology_definition_report.json`
- `coherence_transition_report.json`
- `figure_table_reference_report.json`
- `routing_trace.json`
- `tool_event_log.jsonl`
- `network_event_log.jsonl`
- `run_summary.json`
- `session_transcript.md`

## Documentation index

Start with [docs/INDEX.md](docs/INDEX.md).
