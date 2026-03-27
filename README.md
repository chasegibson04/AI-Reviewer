# AI-Reviewer

AI-Reviewer is a local-first, privacy-first review platform for paper critique, draft improvement, and repeatable evaluation workflows.  
This repo is a fork of AI-Scientist, but AI-Reviewer is now the primary product path.

## What Changed From Upstream

- Primary workflow changed from autonomous scientist runs to review-focused workflows.
- Ollama local provider is first-class and default.
- Strict offline behavior is enabled by default.
- Structured review schema + repair pipeline are default.
- Project-based workflow is first-class (projects, materials, runs, evaluations).
- Launchers and CLI are designed for Windows/macOS local usage.

Legacy `ai_scientist/` code remains for provenance and optional use, but it is secondary and potentially risky.

## Core Principles

- Local-first: run against local Ollama by default.
- Privacy-first: no hidden cloud fallback.
- Review-first: paper review/writing assistance, not autonomous experiment execution.
- Schema-validated: robust structured outputs with repair.
- Observable: each run writes logs, metadata, and artifacts.

## Quickstart (Windows)

1. Start Ollama:
```powershell
ollama serve
```
2. Launch (Windows):
- Double-click `launch_ai_reviewer.bat`, or
- Run PowerShell launcher:
```powershell
powershell -ExecutionPolicy Bypass -File .\launchers\launch_ai_reviewer.ps1
```

## Quickstart (macOS)

1. Start Ollama:
```bash
ollama serve
```
2. Launch (macOS):
```bash
chmod +x launch_ai_reviewer.command launchers/launch_ai_reviewer.sh launchers/launch_ai_reviewer.command
./launch_ai_reviewer.command
```
You can also double-click `launch_ai_reviewer.command` in Finder. Keep the launcher inside the repo folder.
If you downloaded a zip from GitHub and double-click fails, run the `chmod` command above once to restore executable permissions.

If macOS blocks first launch from downloaded files:
```bash
xattr -dr com.apple.quarantine .
```
3. Apple Silicon note (M1/M2/M3):
- install Python and Ollama in native arm64 mode
- Homebrew default path should include `/opt/homebrew/bin`
- launcher auto-adds `/opt/homebrew/bin` and `/usr/local/bin` when started from Finder/Terminal

Recommended setup:
```bash
brew install python
brew install --cask ollama
```

## Install (Manual)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .[dev]
```

## Recommended Model Defaults

- Balanced reviewer default: `mistral-small3.2:latest`
- Deep reasoning default: `phi4-reasoning:latest`
- Optional final arbitration: `llama3.3:70b-instruct-q4_K_M`
- Fast triage model: `phi4-mini:latest` (or `qwen3:4b`)
- Embeddings default: `bge-m3:latest` (with `mxbai-embed-large:latest` still supported)
- Embeddings fallback: `nomic-embed-text-v2-moe:latest`
- Repair fallback: `qwen2.5:7b-instruct`, `mistral-small3.2:latest`
- Keep `gemma2:27b` available as legacy reviewer option

## Project-First Workflow

Primary workflow:
1. Create/select project
2. Add materials
3. Run review/compare/evaluation workflows
4. Inspect run history and reuse configurations

Each project now includes these manual-drop folders:
- `projects/<project_id>/materials/manuscript`
- `projects/<project_id>/materials/other`

Files dropped there are auto-discovered and indexed on launch/review/inspect.
Default review behavior is manuscript-first:
- `review --project <id>` targets `materials/manuscript` as primary review document(s)
- files under `materials/other` are parsed and used as supporting evidence/style context
- use explicit `--material-ids` if you want to target a non-manuscript file directly

### Project Commands

```bash
ai-reviewer project create "My Project" --description "Journal submission"
ai-reviewer project list
ai-reviewer project use <project_id>
ai-reviewer project add-material paper.pdf --category published_paper --project <project_id>
ai-reviewer project inspect --project <project_id>
ai-reviewer project runs --project <project_id>
ai-reviewer project rerun <run_id> --project <project_id>
ai-reviewer project set-defaults --project <project_id> --review-model gemma3:27b
ai-reviewer project mark-baseline <run_id> --project <project_id>
```

Supported material categories:
- manuscript_draft
- published_paper
- reviewer_comments
- supplemental_document
- style_guide
- journal_instructions
- reference_example
- methods_reference
- miscellaneous

## Lab-Wide Training Materials (Global Guidance)

AI-Reviewer now supports a global, incremental training-materials cache for lab standards.

Source tree (source of truth, never moved by the system):

```text
training_materials/
  published_papers/
  formatting_color_guides/
  external_guides/
  other_groups_papers/
  in_progress_examples/
```

Cache/output artifacts:

```text
data/training_cache/
  manifest.json
  global_guidance.json
  last_sync.json
  files/<file_id>/
    parsed.json
    takeaways.json
```

Behavior:
- detects added/changed/removed files incrementally
- processes only changed inputs
- removes deleted files from active guidance
- injects compact guidance into runs by default
- keeps full transparency via status, manifests, and logs

## Main Commands

- `ai-reviewer launch`
- `ai-reviewer review <file-or-folder>` (fallback file/folder mode remains)
- `ai-reviewer review --project <project_id>`
- `ai-reviewer compare <old-draft> <new-draft>`
- `ai-reviewer evaluate-paper <paper>`
- `ai-reviewer deep-run --project <project_id>`
- `ai-reviewer list-models`
- `ai-reviewer diagnose`
- `ai-reviewer doctor`
- `ai-reviewer test-models`
- `ai-reviewer benchmark`
- `ai-reviewer ingest <file-or-folder>`
- `ai-reviewer slack-dev simulate ...`
- `ai-reviewer training sync|status|rebuild|list|show`
- `ai-reviewer tools list|diagnose|smoke-test`

## Exact Mechanics Reference

For the detailed engineering write-up of exactly how each workflow option executes (models, context, round counts, stage behavior, retries/repair), see:

- [Workflow Mechanics](docs/ai_reviewer/WORKFLOW_MECHANICS.md)

## Published Paper Evaluation Sweep

Use this when you want a full multi-profile run for later critique/tuning:

```bash
ai-reviewer evaluate-paper paper.pdf --project <project_id>
```

Default sweep includes:
- quick
- balanced
- deep
- adversarial
- methods
- writing
- editor

Artifacts include:
- workflow subfolders (`workflows/01_quick`, etc.)
- `evaluation_packet.json`
- `evaluation_summary.md`
- `evaluation_summary.docx`
- disagreement and action-item aggregation

## Slack Integration Readiness (Dev)

Architecture and payload models are included under `ai_reviewer/slack/`:
- command mapping
- submission/result schemas
- local simulation flow

Simulate lab Slack command routing locally:

```bash
ai-reviewer slack-dev simulate --file paper.pdf --command "hostile review" --project <project_id>
```

This is dev scaffolding, not a production Slack deployment.

## Output Organization

Project-scoped outputs now live inside each project folder.  
Global `outputs/` is only for non-project global commands.

Project layout:

```text
projects/<project_id>/
  project.json
  materials/
    manuscript/
    other/
    managed/
  runs/
  evaluations/
  audits/
  notes/
  cache/
```

Compatibility for older global-output runs:

```bash
ai-reviewer project migrate-outputs --project <project_id>        # dry-run
ai-reviewer project migrate-outputs --project <project_id> --no-dry-run
```

## Deep Run Workflow

`deep-run` is a staged, multi-pass pipeline (not a single prompt):

1. Project/context sync (project + training guidance)
2. Manuscript/supporting ingest and chunking
3. Context synthesis
4. High-level review pass
5. Adversarial reviewer pass
6. Methods/evidence verification pass
7. Line/paragraph edit pass
8. Style/lab-guidance alignment pass
9. Reconciliation + final report generation

Key deep-run outputs:
- `deep_run_plan.json`
- `context_manifest.json`
- `training_guidance_used.json`
- `project_materials_used.json`
- `stage_0x_*.json/.md`
- `final_deep_review_report.{json,md,txt,docx}`

Default model stack:
- context synthesis: `gemma3:27b`
- deep critique stages: `llama3.3:70b-instruct-q4_K_M` (fallback when missing)
- reconciliation/repair: `mistral-small3.1:24b` (fallback chain)
- embeddings: `mxbai-embed-large:latest` (fallback `nomic-embed-text-v2-moe:latest`)

Review bundles include:
- `run_metadata.json`
- `source_metadata.json`
- `raw_model_response.txt`
- `repaired_model_response.txt` (if used)
- `validated_review.json`
- `review_report.md`
- `review_report.txt`
- `review_report.docx`
- `manuscript_comment_manifest.json`
- `source_mode.json`
- `commented_docx_validation.json`
- `manuscript_suggested_changes_manifest.json`
- `suggested_changes_validation.json`
- `reviewed_manuscript_with_comments.docx` (DOCX source mode), or
- `surrogate_manuscript_from_pdf_with_comments.docx` (PDF surrogate mode)
- `reviewed_manuscript_with_suggested_changes.docx` (DOCX source mode), or
- `surrogate_manuscript_from_pdf_with_suggested_changes.docx` (PDF surrogate mode)
- `debug.log`
- `artifacts/chunk_manifest.json`
- `artifacts/retrieval_manifest.json`

After `review`, `deep-run`, and `evaluate-paper`, AI-Reviewer now performs an automatic post-run output verification step.
Success is only reported when required artifacts are present and non-empty.

The completion summary now prints:
- absolute run directory path
- key report/artifact file paths
- verification status

Useful discovery commands:

```bash
ai-reviewer project runs --project <project_id>
ai-reviewer project last-output --project <project_id>
```

## Manuscript Annotation Output (Primary Editorial Deliverable)

AI-Reviewer now generates a manuscript-style commented DOCX output (not only report memo files):

- If manuscript source is `.docx`:
  - `reviewed_manuscript_with_comments.docx`
  - `reviewed_manuscript_with_suggested_changes.docx`
- If manuscript source is PDF-only:
  - `surrogate_manuscript_from_pdf_base.docx`
  - `surrogate_manuscript_from_pdf_with_comments.docx`
  - `surrogate_manuscript_from_pdf_with_suggested_changes.docx`

Validation is recorded in:
- `source_mode.json` (`original_docx` vs `pdf_only_surrogate`)
- `manuscript_comment_manifest.json` (comment targets + category/rationale payloads)
- `commented_docx_validation.json` (comment count, attachment ranges, body-text preservation)
- `manuscript_suggested_changes_manifest.json` (per-change provenance)
- `suggested_changes_validation.json` (docx exists + structure checks)

## Profiles

- quick
- balanced
- deep
- adversarial
- writing
- methods
- revision
- editor
- citation
- repro

## Diagnostics And Benchmarking

- `diagnose`: environment + model availability + strict offline posture
- `doctor`: remediation suggestions and safe optional fixes
- `test-models`: model sanity checks and embedding smoke checks
- `benchmark`: latency/format/completeness scorecard and recommendation tags

## Configuration

- `config/defaults.yaml`
- `config/local.example.yaml`
- `config/local.yaml` (optional local override)
- `config/local.override.yaml` (optional local override)

Generate local config template:

```bash
ai-reviewer init-config
```

Training config keys:
- `training.enabled`
- `training.source_root`
- `training.cache_root`
- `training.auto_sync_on_start`
- `training.inject_by_default`
- `training.max_injection_chars`

Per-run disable flag:
- `--disable-training-guidance` on `review`, `compare`, and `evaluate-paper`

## Security Notes

- Strict offline defaults are ON.
- Non-local endpoints are blocked in strict mode.
- No silent cloud provider fallback.
- Legacy AI-Scientist autonomous execution remains available but is not default and should be sandboxed.

## Troubleshooting

- `docs/ai_reviewer/TROUBLESHOOTING.md`
- `docs/ai_reviewer/MODEL_SELECTION.md`
- `docs/ai_reviewer/SECURITY.md`
- `docs/ai_reviewer/ARCHITECTURE.md`
- `docs/ai_reviewer/PROJECTS_AND_SLACK.md`
- `docs/ai_reviewer/TRAINING_MATERIALS.md`

## Testing

```bash
python -m pytest -q
python -m pytest -q -m smoke
```
