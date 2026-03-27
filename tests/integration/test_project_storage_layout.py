from pathlib import Path

from typer.testing import CliRunner

from ai_reviewer.cli import app
from ai_reviewer.projects.schema import ProjectDefaults, RunRecord
from ai_reviewer.projects.store import ProjectStore


def test_project_migrate_outputs_moves_global_run(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    store = ProjectStore(tmp_path / "projects")

    def fake_store():
        return store

    monkeypatch.setattr("ai_reviewer.cli._store", fake_store)

    pdir, meta = store.create_project("MigrateProj", "", [], ProjectDefaults(review_model="gemma3:27b"))
    global_out = tmp_path / "outputs" / "20260101_000000_review"
    global_out.mkdir(parents=True, exist_ok=True)
    (global_out / "run_metadata.json").write_text("{}", encoding="utf-8")
    (global_out / "debug.log").write_text("x", encoding="utf-8")

    store.add_run_record(
        meta.project_id,
        RunRecord(
            run_id=global_out.name,
            workflow="review",
            output_dir=str(global_out.resolve()),
            model="gemma3:27b",
            status="success",
        ),
    )

    result = runner.invoke(app, ["project", "migrate-outputs", "--project", meta.project_id, "--no-dry-run"])
    assert result.exit_code == 0
    moved = pdir / "runs" / global_out.name
    assert moved.exists()
    _, updated = store.get_project(meta.project_id)
    assert Path(updated.runs[-1].output_dir).resolve() == moved.resolve()
