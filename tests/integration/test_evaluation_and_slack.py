from pathlib import Path

from typer.testing import CliRunner

from ai_reviewer.cli import app
from ai_reviewer.projects.store import ProjectStore


class EvalProvider:
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
                '"confidence":0.7,"detailed_reviewer_comments":["fine"],"section_specific_comments":[],"extracted_action_items":[{"action":"Do X","priority":"high","owner":"author"}],'  # noqa: E501
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


def test_evaluate_paper_and_slack_simulate(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    provider = EvalProvider()
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

    paper = tmp_path / "published.md"
    paper.write_text("# Published\n\nFindings", encoding="utf-8")

    eval_result = runner.invoke(app, ["evaluate-paper", str(paper), "--output-dir", str(tmp_path / "outputs")])
    assert eval_result.exit_code == 0
    assert list((tmp_path / "outputs").rglob("evaluation_packet.json"))

    slack_result = runner.invoke(
        app,
        ["slack-dev", "simulate", "--file", str(paper), "--command", "hostile review", "--output-dir", str(tmp_path / "outputs")],
    )
    assert slack_result.exit_code == 0
    _, project_meta = store.list_projects()[0]
    pdir, _ = store.get_project(project_meta.project_id)
    assert list((pdir / "runs").rglob("slack_result_summary.json"))
