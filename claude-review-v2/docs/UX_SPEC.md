# UX Specification

The target UX is OpenClaude-like session behavior applied to manuscript review.

## Core experience

- Keep OpenClaude-style conversational terminal loop.
- Keep tool-driven execution (not a hidden batch subprocess flow).
- Keep concise operational output and command ergonomics.
- Avoid custom shell branding drift.

## Startup expectations

On launch, the shell should quickly surface:
- backend availability (Ollama reachability)
- model/profile availability
- manuscript/project presence in workspace
- suggested next commands

## Primary command UX

The documented manuscript workflow uses:
- `/project`
- `/profile`
- `/doctor` or `/diagnose`
- `/review` or `/deep-run`
- `/artifacts`
- `/replay` and `/diff`

## Profile UX

Users can select profiles by alias or number via `/profile`.

Main run styles:
- balanced local
- deep local
- local MOE staged routing
- one big model (Gemma 4 preference)
- final manuscript pass (Gemma 4 preference)

Default profile: `local_moe`.

## Output UX

After runs, users should get:
- explicit run summary with profile/model mode
- artifact locations
- validation pass/fail status
- clear fallback notices when preferred model is unavailable
