# UX Specification

This UX spec defines the manuscript-first, OpenClaude-like terminal experience for `claude-review-v2`.

## UX Goals

- Keep interactive command-loop flow simple and explicit.
- Make profile and reasoning-mode choices visible, not hidden.
- Surface model readiness and degradation honestly.
- Keep visible manuscript comments concise and readable.
- Keep machine-readable metadata rich in artifacts/manifests.

## Startup UX

On startup, users should be able to quickly determine:

- active project
- active profile
- default deep mode
- local model availability (especially Gemma variants)
- next useful commands (`/project`, `/profile`, `/doctor`, `/deep-run`)

## Command Workflow UX

Primary workflow order:

1. `/project` select manuscript workspace
2. `/profile` select review profile
3. `/doctor` or `/diagnose` verify backend/models
4. `/review` or `/deep-run` execute
5. `/artifacts` inspect outputs

Guided variant:

- `/wizard` performs project/profile/manuscript selection and run choice.

## Deep-Run Mode Choice UX

Before interactive deep execution, prompt user for reasoning mode:

- `MOE (multi-model specialists)`
- `Single-model Gemma 4`

Prompt should be plain-language and show recommended default.

User intent controls:

- interactive choice prompt
- optional CLI flag override (`--mode moe` / `--mode gemma`)
- persistent default via `/deep-mode`

## Run Summary UX Requirements

Summaries must include:

- profile used
- reasoning mode requested and effective
- model target
- degraded/fallback flag and reason when relevant
- support ingest summary
- citation verification summary
- run directory path

## Stage-to-Model Transparency

Artifacts should expose stage routing in `routing_trace.json`:

- each stage name
- model assigned
- stage status (`ok`, `fallback_error`, `heuristic_only`, etc.)
- error/fallback reason if applicable
- finding count

## Comment UX Requirements

Visible comment body style:

- compact and direct
- one issue per comment
- optional short fix line
- no metadata boilerplate in the visible message

Manifest metadata style:

- can include richer context (stage, evidence, confidence, support source status)

## Citation UX Requirements

Citation verification outputs should be:

- sentence-local where possible
- explicit about confidence level
- explicit when abstract-only fallback was used
- explicit when support could not be verified

## Degraded-Mode Honesty

If requested model path fails or degrades:

- tell user in terminal summary
- persist reason in `run_summary.json` and `routing_trace.json`
- do not label degraded path as fully successful single-model Gemma behavior
