from pathlib import Path

from typer.testing import CliRunner

from ai_reviewer.cli import app
from ai_reviewer.projects.store import ProjectStore


class ProjectProvider:
    def health(self):
        return True, "ok"

    def list_models(self):
        return ["gemma3:27b", "llama3.3:70b-instruct-q4_K_M", "mxbai-embed-large:latest", "mistral-small3.1:24b"]

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
            total_duration = 1.0
            prompt_eval_count = 10
            eval_count = 20
            retries_used = 0
            prompt_chars = 100
            approx_prompt_tokens = 25

        return R()

    def embed(self, text, model, timeout_seconds=90):
        class E:
            embedding = [0.2] * 32

        return E()


def test_project_create_add_and_review(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    provider = ProjectProvider()
    store = ProjectStore(tmp_path / "projects")
    counter = {"n": 0}

    def fake_store():
        return store

    def fake_provider_and_config(config_path, output_dir_override, command_name, debug=False):
        from ai_reviewer.config import load_config
        from ai_reviewer.logging_utils import configure_logging, create_run_dir

        counter["n"] += 1
        cfg = load_config()
        out = output_dir_override or (tmp_path / "outputs")
        out.mkdir(parents=True, exist_ok=True)
        run = create_run_dir(Path(out), f"{command_name}_{counter['n']}")
        logger = configure_logging(run)
        return provider, cfg, run, logger

    monkeypatch.setattr("ai_reviewer.cli._store", fake_store)
    monkeypatch.setattr("ai_reviewer.cli._provider_and_config", fake_provider_and_config)

    material = tmp_path / "paper.md"
    material.write_text("# Title\n\nText", encoding="utf-8")

    create_result = runner.invoke(app, ["project", "create", "ProjA"])
    assert create_result.exit_code == 0
    _, meta = store.list_projects()[0]

    add_result = runner.invoke(
        app,
        ["project", "add-material", str(material), "--project", meta.project_id, "--category", "manuscript_draft"],
    )
    assert add_result.exit_code == 0
    _, meta = store.get_project(meta.project_id)
    assert len(meta.materials) == 1

    review_result = runner.invoke(app, ["review", "--project", meta.project_id, "--output-dir", str(tmp_path / "outputs")])
    assert review_result.exit_code == 0
    pdir, updated = store.get_project(meta.project_id)
    assert updated.runs
    assert str((pdir / "runs").resolve()) in updated.runs[-1].output_dir
