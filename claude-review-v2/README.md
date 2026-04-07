# claude-review-v2

`claude-review-v2` is a self-contained OpenClaude-style shell for manuscript review, backed by a local TypeScript-to-Python bridge.

This subproject is designed to run review workflows without relying on root-level `ai_reviewer` launch paths for normal operation. The default launcher path stays inside `claude-review-v2` and uses the local bridge/runtime.

## Scope and Boundary

- Primary runtime for this effort: `claude-review-v2/`
- Primary launcher entrypoint: `claude-review-v2/scripts/launch.js`
- Layer A shell runtime: `claude-review-v2/src/` and `claude-review-v2/scripts/line-repl.js`
- Layer B Python bridge: `claude-review-v2/src/bridge/python/review_mcp_server.py`
- Default profile: `local_moe`

Legacy parent-repo guided handoff exists only as an explicit opt-in compatibility path:

- `CLAUDE_REVIEW_ALLOW_LEGACY_GUIDED=1 node scripts/launch.js`

Without that env var, no-argument launch stays inside `claude-review-v2`.

## What You Get

- OpenClaude-like command loop tailored to manuscript operations.
- Guided project/profile/deep-run flow.
- Explicit deep-run reasoning mode choice:
  - `MOE (multi-model specialists)`
  - `Single-model Gemma 4`
- Structured deep review with stage-level model routing trace.
- Support-paper ingest pipeline with reusable structured cache.
- Line-by-line citation verification against in-text citations and reference section mappings.
- Artifact rendering, replay, diff, validation, and run summaries.

## Deep-Run Mode Choice (Important)

When you run `/deep-run` interactively, the shell asks:

```text
Deep run reasoning mode:
 1. MOE (multi-model specialists)
 2. Single-model Gemma 4
Choose mode [1/2, Enter=<recommended>]:
```

Implementation path:

- Prompt logic: `scripts/line-repl.js` (`chooseDeepRunMode`)
- Execution: `runReviewFlow(..., reasoningMode)`
- Backend routing: `review_mcp_server.py` (`_resolve_stage_models`)

### Gemma-single routing behavior

In `gemma_single` mode, the bridge maps the core reasoning stages to one Gemma model target when available:

- `structural_review`
- `high_level_review`
- `hostile_review`
- `methods_verification`
- `line_by_line_edits`
- `style_alignment`
- `reconciliation`
- `final_arbitration`

Support ingest and citation verification model targets also follow the same Gemma target in this mode.

If Gemma is unavailable/unusable, degradation is explicit in run artifacts (`run_summary.json`, `routing_trace.json`) with fallback reason text.

## Profiles

Available review profiles:

- `quick_local`
- `balanced_local`
- `deep_local`
- `local_moe` (default)
- `one_big_model`
- `full_manuscript_final_pass`
- `offline_strict`
- `llama_cpp_standard`
- `llama_cpp_turboquant`
- `gemma4_26b`
- `gemma4_31b`

Profile metadata and resolution live in:

- `src/utils/model/reviewProfiles.ts`
- `src/commands/review/runParameters.ts`

## Core Commands

- `/wizard` guided run setup
- `/project` project selection
- `/profile` profile selection
- `/deep-mode` default deep-run mode (`moe` / `gemma`)
- `/review` standard review
- `/deep-run` deep staged review (with mode prompt)
- `/doctor` environment and model readiness
- `/diagnose` tool/state diagnostics
- `/artifacts` validate/summarize run artifacts
- `/replay` replay one run
- `/diff` compare two runs

## Artifact Model

Deep runs typically produce:

- `run_summary.json`
- `routing_trace.json`
- `manuscript_comment_manifest.json`
- `manuscript_comment_metadata.json`
- `manuscript_suggested_changes_manifest.json`
- `support_ingest_report.json`
- `support_ingest_cache_index.json`
- `support_usage_ledger.json`
- `citation_verification_ledger.json`
- `claim_verification_summary.json`
- `assertion_ledger.json`
- `terminology_definition_report.json`
- `coherence_transition_report.json`
- `methods_report.json`
- `figure_table_reference_report.json`
- `format_compliance_report.json`
- `validation_report.json`
- `tool_event_log.jsonl`
- `network_event_log.jsonl`

Visible comment bodies are intentionally concise; richer metadata stays in manifests.

## Requirements

Required:

- Node.js 20+
- Python 3.10+
- Ollama local service (`http://localhost:11434`)

Recommended:

- Bun (build flow)
- `pdftotext` for cleaner PDF extraction quality in fallback mode

Optional:

- `ai_reviewer` Python package for richer parsing/ingest (bridge has internal fallbacks)

## Launching

Primary path:

```bash
node scripts/launch.js
```

macOS wrappers:

```bash
./launchers/macos/claude-review-v2.sh
# or double-click
./launchers/macos/claude-review-v2.command
```

Windows wrappers:

```powershell
.\launchers\windows\claude-review-v2.cmd
# or
powershell -ExecutionPolicy Bypass -File .\launchers\windows\claude-review-v2.ps1
```

## Health Checks

```bash
bash scripts/doctor_runtime.sh
bash scripts/smoke_fallback.sh
```

Additional launch-plan verification:

```bash
node scripts/launch.js --print-launch-plan
bash launchers/macos/claude-review-v2.sh --print-launch-plan
```

## Validation Guidance

For this effort, real validation should stay in-subproject and use approved test projects only.

Do not use blocked project families (for example: horseshoe or pampa-named projects).

## Documentation Map

See [docs/INDEX.md](docs/INDEX.md) for full architecture, launcher, UX, setup, and troubleshooting references.
