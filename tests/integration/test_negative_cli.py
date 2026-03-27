from pathlib import Path

from typer.testing import CliRunner

from ai_reviewer.cli import app


def test_review_bad_input_path():
    runner = CliRunner()
    result = runner.invoke(app, ["review", "does_not_exist.pdf"])
    assert result.exit_code != 0
    assert "Input path not found" in result.stdout
