# AI-Reviewer

AI-Reviewer is a local-first manuscript review system focused on project-scoped runs, commented manuscript output, suggested revisions, and auditable review artifacts.

## Product Position

Primary workflow:
- review manuscripts locally
- generate manuscript comments and suggested revisions
- keep artifacts, manifests, and validation files per run
- support PDF-surrogate and native DOCX source modes

This repository still contains legacy `ai_scientist/` code for provenance, but `ai-reviewer` is the active product path.

## Runtime Defaults

Repository defaults from `config/defaults.yaml`:
- balanced review model: `mistral-small3.2:latest`
- deep review model: `phi4-reasoning:latest`
- embedding model: `bge-m3:latest`
- strict offline: `true`
- deep-run routing mode: `default`

Important distinction:
- local `config/local.yaml` or environment overrides may route stronger models in practice
- the validation/benchmark artifacts in `audits/` show what actually ran on this machine

## Core Guarantees

- local Ollama is the only chat/embed runtime path
- no silent cloud fallback
- strict schema validation and repair remain on by default
- output verification runs after `review`, `deep-run`, and `evaluate-paper`
- manuscript-first outputs are primary deliverables

## Quickstart

### Windows

```powershell
ollama serve
powershell -ExecutionPolicy Bypass -File .\launchers\launch_ai_reviewer.ps1
```

### macOS

```bash
ollama serve
chmod +x launch_ai_reviewer.command launchers/launch_ai_reviewer.sh launchers/launch_ai_reviewer.command
./launch_ai_reviewer.command
```

If macOS blocks launch from downloaded files:

```bash
xattr -dr com.apple.quarantine .
```

## Main Workflows

- `ai-reviewer review <file-or-folder>`
- `ai-reviewer review --project <project_id>`
- `ai-reviewer deep-run --project <project_id>`
- `ai-reviewer deep-run --project <project_id> --context-material-ids <id1,id2>`
- `ai-reviewer evaluate-paper <paper> --project <project_id>`
- `ai-reviewer compare <old-draft> <new-draft>`
- `ai-reviewer diagnose`
- `ai-reviewer test-models`
- `ai-reviewer benchmark`
- `ai-reviewer training sync|status|rebuild|list|show`

## Project-First Layout

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

Behavior:
- `materials/manuscript` is the primary review target set
- `materials/other` is treated as supporting context only
- support materials are filtered before grounding to reduce contamination

## Deep-Run Summary

`deep-run` is a staged multi-pass path, not a single prompt.

Current stage families:
1. structural/source ingest
2. manuscript/support digest
3. context synthesis
4. high-level/hostile/methods critique
5. line edits and style alignment
6. optional context-pack compliance check
7. reconciliation + bounded final arbitration
8. commented manuscript + suggested revisions
9. final report + validation

Routing notes:
- `deep_run_routing.mode: default` uses conservative stage routing
- `deep_run_routing.mode: max_quality` uses stronger local models where benchmarks supported it
- benchmark evidence showed stronger routing helps style/edit surfacing more than final reconciliation quality

## Manuscript Outputs

For DOCX input:
- `reviewed_manuscript_with_comments.docx`
- `reviewed_manuscript_with_suggested_changes.docx`

For PDF input:
- `surrogate_manuscript_from_pdf_base.docx`
- `surrogate_manuscript_from_pdf_with_comments.docx`
- `surrogate_manuscript_from_pdf_with_suggested_changes.docx`

Validation/manifests:
- `source_mode.json`
- `section_map.json`
- `manuscript_comment_manifest.json`
- `commented_docx_validation.json`
- `manuscript_suggested_changes_manifest.json`
- `suggested_changes_validation.json`

Current limitation:
- suggested revisions now render as Word tracked insertions/deletions in the suggested-revisions DOCX

## Native DOCX Notes

Current behavior on native and pre-annotated DOCX:
- preserve existing DOCX comments
- preserve visible prior suggested-change blocks
- strip visible suggestion blocks from analysis text
- layer new comments on top
- render new suggested revisions as tracked changes against the clean paragraph text
- validate `meaningful_new_review_state` and `silent_noop_suspected`

## Verification Notes

- strict offline remains the default
- citation fetch is metadata/OA-only and still runs under strict offline
- citation fetch labels now distinguish:
  - `citation_exists`
  - `metadata_match_likely`
  - `support_relationship_not_verified`
  - `external_metadata_check_only`
  - `needs_human_verification`
- this system does not claim full claim-to-paper verification

## Optional Layers

- figure review exists, but current validated mode is text-only and should remain OFF by default on the approved PDFs
- context-pack/compliance is useful as opt-in, not as a default replacement for manuscript review

## Key Docs

- [Workflow Mechanics](docs/ai_reviewer/WORKFLOW_MECHANICS.md)
- [Architecture](docs/ai_reviewer/ARCHITECTURE.md)
- [Model Selection](docs/ai_reviewer/MODEL_SELECTION.md)
- [Privacy Audit](docs/ai_reviewer/PRIVACY_AUDIT.md)
- [Troubleshooting](docs/ai_reviewer/TROUBLESHOOTING.md)
- [Testing Procedure](audits/TESTING_PROCEDURE.md)

## Testing

```powershell
python -m pytest -q
```
