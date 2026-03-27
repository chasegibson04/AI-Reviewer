# AI-Reviewer Workflow Mechanics (Exact Runtime Behavior)

This is the precise runtime behavior for each major workflow in the current codebase.
It documents model selection, context construction, rounds/passes, and fallback/repair behavior.

## 1) `launch` (guided interactive)

`launch` is a guided wrapper that routes into existing commands:
- `single-review` -> `review --project <id>`
- `batch-review` -> `review --project <id> --material-ids <all indexed materials>`
- `deep-run` -> `deep-run --project <id>`
- `compare-drafts` -> `compare`
- `full-evaluation-sweep` -> `evaluate-paper`
- `benchmark-models` -> `benchmark`
- `diagnose` -> `diagnose`

Before route:
- syncs project manual folders (`materials/manuscript`, `materials/other`)
- syncs global training cache (if enabled)
- lists local Ollama models

## 2) `review` (single/batch review engine)

## Input targeting rules

- `review <input_path>`: parses input path (file/folder)
- `review --project <id>`:
  - default primary targets: all `manuscript_draft` materials
  - `materials/other` are parsed as **supporting context docs**
  - if no manuscript exists: graceful error with action message
- `--material-ids`: explicit override of primary targets (can include non-manuscript)

## Model selection

- default balanced run model: `mistral-small3.2:latest`
- deep reasoning default: `phi4-reasoning:latest`
- optional final judge/arbitration: `llama3.3:70b-instruct-q4_K_M`
- fast triage model family: `phi4-mini:latest`, `qwen3:4b`
- embeddings default: `bge-m3:latest` (with `mxbai-embed-large:latest` supported)
- embedding fallback model in config: `nomic-embed-text-v2-moe:latest`

## Round/call counts per command

Per command:
- 1 preflight chat sanity ping (`{"ok":true}`) before processing docs

Per primary document:
- 1 main generation call (`/api/chat`) via `run_review`
- plus repair attempts only if parsing/validation fails:
  - local cleanup pass (no model call)
  - optional model repair calls, one per candidate repair model

Retrieval calls (if retrieval enabled for profile):
- 1 embedding call for query
- 1 embedding call per chunk in retrieval pool
- adaptive downsizing on context overflow (same chunk retried with smaller text)

## Context used in prompt

Primary review prompt context includes:
- primary manuscript chunks (or retrieved top-k chunks)
- parser warnings, headings, document metadata
- global training guidance block (if enabled)
- supporting docs summary blocks (from `materials/other`)

If retrieval is enabled:
- retrieval pool includes chunks from:
  - primary manuscript
  - supporting docs (`materials/other`)
- top-k retrieved chunks become final context block

## 3) `deep-run` (multi-stage deep editorial/reviewer pipeline)

`deep-run` is not a single prompt; it executes staged passes with artifacts.

## Stage sequence

1. Stage 00 sync
   - sync project inventory
   - require manuscript presence
   - sync/load training guidance
   - write manifests (`deep_run_plan.json`, `context_manifest.json`, etc.)

2. Stage 01 ingest + normalization + source mode detection
   - parse manuscript
   - parse up to 10 supporting materials from `materials/other`
   - chunk manuscript with deep profile chunk settings

3. Stage 02 context synthesis
   - one strict JSON synthesis call:
   - outputs: manuscript overview, section map, claims/methods/results/conclusions/risk areas

4. Stage 03 high-level review
   - `run_review` using `balanced` profile

5. Stage 04 hostile/adversarial review
   - `run_review` using `adversarial` profile

6. Stage 05 methods verification
   - `run_review` using `methods` profile

7. Stage 06 line-by-line/paragraph edits
   - up to 12 chunk-level edit calls (one chat call per selected chunk)

8. Stage 07 style/lab-guidance alignment
   - one strict JSON style alignment call

9. Stage 08 reconciliation
   - one strict JSON reconciliation call combining stage outputs

10. Stage 09 manuscript annotation
   - DOCX source mode: generate `reviewed_manuscript_with_comments.docx`
   - PDF source mode: generate surrogate base DOCX + `surrogate_manuscript_from_pdf_with_comments.docx`
   - validates real comment count + body text preservation

11. Final report synthesis
   - writes final consolidated report JSON/MD/TXT/DOCX + run metadata

## Default model stack by stage

- structural triage: `phi4-mini:latest` (fallback `qwen3:4b`)
- context/supporting/manuscript digestion: `mistral-small3.2:latest` (fallback configured balanced)
- high-level/adversarial/methods verification: `phi4-reasoning:latest` (fallback configured deep)
- reconciliation/repair: `qwen2.5:7b-instruct` / configured repair stack
- optional arbitration model available: `llama3.3:70b-instruct-q4_K_M`

If preferred model missing:
- fallback selects available configured alternatives; selection is recorded in artifacts.

## Deep-run round/call counts (typical)

Minimum chat calls:
- stage2 (1) + stage3 (1) + stage4 (1) + stage5 (1) + stage7 (1) + stage8 (1) = 6
- plus stage6 chunk edits: up to 12
- typical total: 6 to 18 chat calls

Plus retrieval/embedding calls inside stages 3/4/5 if retrieval active.

## Failure behavior

- missing manuscript -> graceful `DeepRunError` message
- stage failures -> warning + stage artifact with failure payload
- reconciliation fallback still produces final report when possible
- run status becomes `partial` if any stage status is not `ok`

## 4) `evaluate-paper` (published paper sweep)

Runs one anchor document through profile set:
- quick
- balanced
- deep
- adversarial
- methods
- writing
- editor

Per profile:
- one `run_review` pipeline call (with repair as needed)

Outputs:
- per-profile workflow bundles under `workflows/`
- `evaluation_packet.json`
- `evaluation_summary.md`
- disagreement summary (decision/confidence spread)
- aggregated action items

## 5) `compare`

Behavior:
- parse old and new drafts
- compute heuristic section alignment and claim add/remove/change lists
- one strict compare model call for revision summary output
- writes compare JSON + Markdown report

## 6) `test-models`

For each selected chat model:
- one strict JSON generation call
- records latency and whether output needed repair markers

Optional embedding tests:
- one embedding smoke call per detected embedding model

## 7) `benchmark`

Per model:
- one benchmark review generation call (short + long fixtures in prompt)
- `parse_and_repair` on generated output
- additional `parse_and_repair` run against intentionally malformed fixture
- emits structured pass, repair dependence, completeness score, recommendation tag

## 8) Training materials context injection

When enabled:
- training cache syncs on startup (config-controlled)
- compact guidance block is injected (max chars configurable; default 2200)
- injection is profile-aware and logged

This guidance is used by:
- `review`
- `deep-run`
- `compare`
- `evaluate-paper`

## 9) Profile settings (exact configured values)

From `ai_reviewer/review/profiles.py`:

- `quick`: temp 0.1, retrieval off, strict on, force repair off
- `balanced`: temp 0.2, retrieval on, strict on, force repair off
- `deep`: temp 0.15, retrieval on, strict on, force repair on
- `adversarial`: temp 0.2, retrieval on, strict on, force repair on
- `methods`: temp 0.12, retrieval on, strict on, force repair on
- `writing`: temp 0.25, retrieval off, strict on, force repair off
- `editor`: temp 0.1, retrieval off, strict on, force repair off
- `revision`: temp 0.15, retrieval on, strict on, force repair on
- `citation`: temp 0.15, retrieval on, strict on, force repair on
- `repro`: temp 0.15, retrieval on, strict on, force repair on

`ensemble_count` and `reflection_count` are currently profile metadata fields for strategy intent and reporting.
The active runtime executes one main generation pass per review invocation plus repair/fallback passes as required.

## 10) Retry/timeout mechanics (exact defaults)

From config/provider defaults:

- chat timeout: 240s (deep-run internally bumps to at least 600s for stage calls)
- embed timeout: 120s
- chat attempts: 3
- embed attempts: 2
- backoff: linear base 1.0s * attempt

Strict offline:
- Ollama URL must be localhost/127.0.0.1 when strict offline is enabled.
