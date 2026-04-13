import json
import os
import subprocess
from pathlib import Path


def _launch_plan(env: dict[str, str] | None = None) -> dict:
    project_root = Path(__file__).resolve().parents[1]
    run_env = {**os.environ}
    if env:
        run_env.update(env)
    proc = subprocess.run(
        ["node", "scripts/launch.js", "--print-launch-plan"],
        cwd=str(project_root),
        env=run_env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def test_default_launch_plan_stays_in_subproject():
    payload = _launch_plan()
    assert payload["projectRoot"].endswith("claude-review-v2")
    assert payload["launchTarget"] != "legacy_guided_workflow"
    assert payload["launchTarget"] in {"line_repl", "dist_cli"}


def test_legacy_handoff_is_opt_in_only():
    payload = _launch_plan({"CLAUDE_REVIEW_ALLOW_LEGACY_GUIDED": "1"})
    if payload["legacyGuidedAvailable"]:
        assert payload["launchTarget"] == "legacy_guided_workflow"
    else:
        assert payload["launchTarget"] in {"line_repl", "dist_cli"}
