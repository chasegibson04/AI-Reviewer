from pathlib import Path

from typer.testing import CliRunner
from docx import Document

from ai_reviewer.cli import app


def test_tools_commands_smoke(tmp_path: Path):
    runner = CliRunner()
    docx_path = tmp_path / "sample.docx"
    d = Document()
    d.add_paragraph("Sample paragraph")
    d.save(str(docx_path))

    result = runner.invoke(app, ["tools", "list"])
    assert result.exit_code == 0
    result = runner.invoke(app, ["tools", "diagnose"])
    assert result.exit_code == 0
    result = runner.invoke(app, ["tools", "smoke-test", "--sample-docx", str(docx_path)])
    assert result.exit_code == 0
