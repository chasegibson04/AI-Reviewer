from pathlib import Path
import json

from typer.testing import CliRunner

from ai_reviewer.cli import app
from ai_reviewer.projects.schema import ProjectDefaults
from ai_reviewer.projects.store import ProjectStore


class ManualProvider:
    def health(self):
        return True, "ok"

    def list_models(self):
        return ["gemma3:27b", "mxbai-embed-large:latest", "mistral-small3.1:24b"]

    def chat(self, request):
        class R:
            content = (
                "{"
                '"document_metadata":{"title":"Fixture"},'
                '"summary":"Summary",'
                '"major_strengths":["s"],'
                '"major_weaknesses":["w"],'
                '"novelty_concerns":[],"methodological_concerns":[],"statistical_concerns":[],"writing_organization_concerns":[],'  # noqa: E501
                '"figure_table_concerns":[],"citation_reference_concerns":[],"reproducibility_concerns":[],'  # noqa: E501
                '"suggested_experiments_analyses":[],"recommendation":{"decision":"revise","rationale":"ok"},'
                '"confidence":0.7,"detailed_reviewer_comments":["fine"],"section_specific_comments":[],"extracted_action_items":[],'  # noqa: E501
                '"model_debug_metadata":{"provider":"ollama","model":"gemma3:27b","temperature":0.2,"parse_failures":0}'
                "}"
            )
            total_duration = 1
            prompt_eval_count = 10
            eval_count = 20
            retries_used = 0
            prompt_chars = 100
            approx_prompt_tokens = 25

        return R()

    def embed(self, text, model, timeout_seconds=90):
        class E:
            embedding = [0.1] * 16

        return E()


def test_review_project_with_manual_material_folder(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    provider = ManualProvider()
    store = ProjectStore(tmp_path / "projects")

    def fake_store():
        return store

    def fake_provider_and_config(config_path, output_dir_override, command_name, debug=False):
        from ai_reviewer.config import load_config
        from ai_reviewer.logging_utils import configure_logging, create_run_dir

        cfg = load_config()
        run = create_run_dir(tmp_path / "outputs", command_name)
        logger = configure_logging(run)
        return provider, cfg, run, logger

    monkeypatch.setattr("ai_reviewer.cli._store", fake_store)
    monkeypatch.setattr("ai_reviewer.cli._provider_and_config", fake_provider_and_config)

    _, meta = store.create_project(
        "Manual Project",
        "",
        [],
        defaults=ProjectDefaults(review_model="gemma3:27b"),
    )
    pdir, _ = store.get_project(meta.project_id)
    f = pdir / "materials" / "manuscript" / "paper.md"
    f.write_text("# Title\n\ntext", encoding="utf-8")
    support = pdir / "materials" / "other" / "support.md"
    support.write_text("# Support\n\nEvidence context text.", encoding="utf-8")

    result = runner.invoke(app, ["review", "--project", meta.project_id])
    assert result.exit_code == 0
    _, updated = store.get_project(meta.project_id)
    assert updated.materials
    assert updated.runs
    out_dirs = sorted((tmp_path / "outputs").glob("*_review"))
    assert out_dirs
    summary = json.loads((out_dirs[-1] / "artifacts" / "batch_summary.json").read_text(encoding="utf-8"))
    assert summary["processed"] == 1
    assert summary["supporting_context_docs"] == 1


def test_review_project_other_only_fails_gracefully(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    provider = ManualProvider()
    store = ProjectStore(tmp_path / "projects")

    def fake_store():
        return store

    def fake_provider_and_config(config_path, output_dir_override, command_name, debug=False):
        from ai_reviewer.config import load_config
        from ai_reviewer.logging_utils import configure_logging, create_run_dir

        cfg = load_config()
        run = create_run_dir(tmp_path / "outputs", command_name)
        logger = configure_logging(run)
        return provider, cfg, run, logger

    monkeypatch.setattr("ai_reviewer.cli._store", fake_store)
    monkeypatch.setattr("ai_reviewer.cli._provider_and_config", fake_provider_and_config)

    _, meta = store.create_project(
        "Only Other",
        "",
        [],
        defaults=ProjectDefaults(review_model="gemma3:27b"),
    )
    pdir, _ = store.get_project(meta.project_id)
    f = pdir / "materials" / "other" / "paper.md"
    f.write_text("# Title\n\ntext", encoding="utf-8")

    result = runner.invoke(app, ["review", "--project", meta.project_id])
    assert result.exit_code != 0
    assert "No parseable manuscript docs found for project" in result.stdout
