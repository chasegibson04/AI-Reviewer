# Projects, Evaluations, and Slack Readiness

## Project Model

AI-Reviewer is project-first.

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

Meaning:
- `materials/manuscript` is the primary review lane
- `materials/other` is supporting context only
- `materials/managed` stores normalized managed inputs such as native DOCX sources

## Project Workflow

1. create/select project
2. add manuscript and supporting materials
3. run `review` or `deep-run`
4. inspect run history and artifacts
5. rerun or benchmark as needed

Useful commands:

```powershell
ai-reviewer project create "Name"
ai-reviewer review --project <id>
ai-reviewer deep-run --project <id>
ai-reviewer project runs --project <id>
ai-reviewer project rerun <run_id> --project <id>
```

## Evaluation Sweep

`evaluate-paper` runs multiple review profiles for comparison and tuning.

Outputs include:
- per-profile workflow bundles
- aggregate summary
- disagreement analysis
- action-item aggregation

## Slack Readiness

Slack support remains an adapter/simulation boundary, not a production requirement.

Current path:
- schemas in `ai_reviewer/slack/models.py`
- adapter logic in `ai_reviewer/slack/adapter.py`
- local simulation via `ai-reviewer slack-dev simulate`

This path is isolated from the core local manuscript workflow.
