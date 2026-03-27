from pathlib import Path

from typer.testing import CliRunner

from ai_reviewer.cli import app


def test_training_commands(tmp_path: Path):
    runner = CliRunner()
    source_root = tmp_path / "training_materials"
    (source_root / "external_guides").mkdir(parents=True)
    (source_root / "external_guides" / "guide.md").write_text("# Guide\n\nUse concise wording.", encoding="utf-8")
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        f"training:\n  enabled: true\n  source_root: {source_root.as_posix()}\n  cache_root: {(tmp_path / 'cache').as_posix()}\n",
        encoding="utf-8",
    )
    r1 = runner.invoke(app, ["training", "sync", "--config-path", str(cfg)])
    assert r1.exit_code == 0
    r2 = runner.invoke(app, ["training", "status", "--config-path", str(cfg)])
    assert r2.exit_code == 0
    assert "tracked_files" in r2.stdout
    r3 = runner.invoke(app, ["training", "list", "--config-path", str(cfg)])
    assert r3.exit_code == 0
    assert "external_guides" in r3.stdout

