# Projects, Evaluation Sweeps, and Slack Readiness

## Project Model

AI-Reviewer uses a project-first model:
- project metadata and defaults
- material inventory
- run history
- evaluation history

Project storage:

```text
projects/<project_id>/
  project.json
  materials/<material_id>/
    <source file>
    metadata.json
  runs/
  evaluations/
  notes/
  cache/
```

## Project Workflow

1. Create/select a project.
2. Add materials with categories.
3. Run review/compare/evaluation commands.
4. Inspect run history and baseline markers.
5. Re-run prior settings for tuning.

Useful commands:

```bash
ai-reviewer project create "Name"
ai-reviewer project add-material draft.tex --project <id> --category manuscript_draft
ai-reviewer review --project <id>
ai-reviewer project runs --project <id>
ai-reviewer project rerun <run_id> --project <id>
```

## Published Paper Evaluation Sweep

`ai-reviewer evaluate-paper` runs a multi-profile bundle for meta-analysis and later prompt/model tuning.

Output packet includes:
- per-profile workflow bundles
- aggregate summary
- disagreement analysis
- action-item aggregation
- model/profile metadata

## Slack Readiness

Current Slack support is an adapter boundary and local simulation path:
- schemas: `ai_reviewer/slack/models.py`
- mapping + serialization: `ai_reviewer/slack/adapter.py`
- CLI simulation: `ai-reviewer slack-dev simulate`

Simulated route:
1. Parse Slack-like command text.
2. Map to internal workflow request.
3. Create/select project.
4. Ingest submitted file as project material.
5. Execute workflow.
6. Persist result summary payload for return.

This is intentionally isolated and optional, so Slack is not required for core local usage.

