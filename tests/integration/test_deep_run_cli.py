from pathlib import Path

from typer.testing import CliRunner

from ai_reviewer.cli import app
from ai_reviewer.projects.schema import ProjectDefaults
from ai_reviewer.projects.store import ProjectStore


class CliDeepProvider:
    def health(self):
        return True, "ok"

    def list_models(self):
        return ["gemma3:27b", "llama3.3:70b-instruct-q4_K_M", "mxbai-embed-large:latest", "mistral-small3.1:24b"]

    def chat(self, request):
        lower = request.system_prompt.lower()
        if "strict json" in lower and "reviewer" in lower:
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
        elif "reconcile" in lower:
            content = '{"consolidated_strengths":["x"],"consolidated_weaknesses":["y"],"disagreements":[],"priority_actions":["a"],"revision_plan":["p"],"response_to_reviewers_bullets":["r"],"confidence_notes":["c"]}'  # noqa: E501
        elif "style and formatting" in lower:
            content = '{"style_issues":["s"],"formatting_issues":["f"],"tone_issues":["t"],"alignment_actions":["a"]}'
        elif "local edit suggestions" in lower:
            content = '{"section":"sec","issues":["i"],"rewrite_candidates":["r"]}'
        else:
            content = '{"manuscript_overview":"m","section_map":["s"],"claims":["c"],"methods":["m"],"results":["r"],"conclusions":["c"],"risk_areas":["x"]}'  # noqa: E501

        class R:
            total_duration = 1.0
            prompt_eval_count = 10
            eval_count = 10
            retries_used = 0
            prompt_chars = 100
            approx_prompt_tokens = 25
            raw = {}

            def __init__(self, text: str):
                self.content = text

        return R(content)

    def embed(self, text, model, timeout_seconds=90):
        class E:
            embedding = [0.1] * 16

        return E()


def test_deep_run_cli_happy_path(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    store = ProjectStore(tmp_path / "projects")
    provider = CliDeepProvider()
    _, meta = store.create_project("DeepCLI", "", [], ProjectDefaults(review_model="gemma3:27b"))
    pdir, _ = store.get_project(meta.project_id)
    (pdir / "materials" / "manuscript" / "main.md").write_text("# Main\n\nMethods and results", encoding="utf-8")
    (pdir / "materials" / "other" / "ctx.md").write_text("# Ctx\n\nSupport", encoding="utf-8")
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        f"training:\n  enabled: false\n  source_root: {(tmp_path / 'training').as_posix()}\n  cache_root: {(tmp_path / 'tc').as_posix()}\n",
        encoding="utf-8",
    )

    def fake_store():
        return store

    def fake_provider_and_config(config_path, output_dir_override, command_name, debug=False, **kwargs):
        from ai_reviewer.config import load_config
        from ai_reviewer.logging_utils import configure_logging, create_run_dir

        out = output_dir_override or (tmp_path / "outputs")
        out.mkdir(parents=True, exist_ok=True)
        run = create_run_dir(out, command_name)
        logger = configure_logging(run)
        return provider, load_config(config_path), run, logger

    monkeypatch.setattr("ai_reviewer.cli._store", fake_store)
    monkeypatch.setattr("ai_reviewer.cli._provider_and_config", fake_provider_and_config)
    result = runner.invoke(app, ["deep-run", "--project", meta.project_id, "--config-path", str(cfg), "--output-dir", str(tmp_path / "outputs")])
    assert result.exit_code == 0
    assert list((pdir / "runs").rglob("final_deep_review_report.json"))
    _, updated = store.get_project(meta.project_id)
    assert updated.runs
    assert str((pdir / "runs").resolve()) in updated.runs[-1].output_dir
