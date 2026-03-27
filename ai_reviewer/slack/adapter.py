from __future__ import annotations

import json
from pathlib import Path

from ai_reviewer.projects.store import ProjectStore
from ai_reviewer.slack.models import SlackResultSummary, SlackSubmission


def map_slack_command_to_workflow(command: str) -> dict:
    lowered = command.lower().strip()
    if "hostile" in lowered or "reviewer #2" in lowered:
        return {"workflow": "review", "profile": "adversarial"}
    if "deep" in lowered:
        return {"workflow": "review", "profile": "deep"}
    if "evaluate" in lowered or "sweep" in lowered:
        return {"workflow": "evaluate_paper", "profile": "balanced"}
    if "methods" in lowered:
        return {"workflow": "review", "profile": "methods"}
    return {"workflow": "review", "profile": "balanced"}


def save_submission_record(submission: SlackSubmission, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"slack_submission_{submission.request_id}.json"
    path.write_text(submission.model_dump_json(indent=2), encoding="utf-8")
    return path


def build_result_summary(
    submission: SlackSubmission,
    store: ProjectStore,
    project_id: str,
    run_id: str | None,
    status: str,
    outputs: list[str],
    warnings: list[str],
) -> SlackResultSummary:
    return SlackResultSummary(
        request_id=submission.request_id,
        project_id=project_id,
        status=status,
        run_id=run_id,
        headline=f"AI-Reviewer finished {status} for {submission.file_name}",
        outputs=outputs,
        warnings=warnings,
    )


def save_result_summary(summary: SlackResultSummary, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
