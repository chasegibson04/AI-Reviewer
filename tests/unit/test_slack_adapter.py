from pathlib import Path

from ai_reviewer.projects.schema import ProjectDefaults
from ai_reviewer.projects.store import ProjectStore
from ai_reviewer.slack.adapter import build_result_summary, map_slack_command_to_workflow, save_result_summary, save_submission_record
from ai_reviewer.slack.models import SlackSubmission, SlackWorkflowRequest


def test_slack_mapping():
    assert map_slack_command_to_workflow("hostile review")["profile"] == "adversarial"
    assert map_slack_command_to_workflow("deep pass")["profile"] == "deep"
    assert map_slack_command_to_workflow("evaluate paper")["workflow"] == "evaluate_paper"


def test_slack_submission_and_summary_serialization(tmp_path: Path):
    submission = SlackSubmission(
        request_id="r1",
        user_id="u1",
        channel_id="c1",
        file_path="paper.pdf",
        file_name="paper.pdf",
        workflow=SlackWorkflowRequest(command="balanced review"),
    )
    out = tmp_path / "out"
    submission_path = save_submission_record(submission, out)
    assert submission_path.exists()

    store = ProjectStore(tmp_path / "projects")
    _, meta = store.create_project("Slack", "", [], ProjectDefaults(review_model="gemma3:27b"))
    summary = build_result_summary(
        submission=submission,
        store=store,
        project_id=meta.project_id,
        run_id="run1",
        status="success",
        outputs=["x"],
        warnings=[],
    )
    target = out / "summary.json"
    save_result_summary(summary, target)
    assert target.exists()

