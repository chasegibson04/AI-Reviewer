import json
from pathlib import Path

from typer.testing import CliRunner

from ai_reviewer.cli import app


class BatchProvider:
    def health(self):
        return True, "ok"

    def list_models(self):
        return ["gemma3:27b", "mxbai-embed-large:latest", "mistral-small3.1:24b"]

    def chat(self, request):
        class R:
            content = (
                '{'
                '"document_metadata":{"title":"Fixture"},'
                '"summary":"Summary",'
                '"major_strengths":["s"],'
                '"major_weaknesses":["w"],'
                '"novelty_concerns":[],'
                '"methodological_concerns":[],'
                '"statistical_concerns":[],'
                '"writing_organization_concerns":[],'
                '"figure_table_concerns":[],'
                '"citation_reference_concerns":[],'
                '"reproducibility_concerns":[],'
                '"suggested_experiments_analyses":[],'
                '"recommendation":{"decision":"revise","rationale":"ok"},'
                '"confidence":0.7,'
                '"detailed_reviewer_comments":["fine"],'
                '"section_specific_comments":[],'
                '"extracted_action_items":[],'
                '"model_debug_metadata":{"provider":"ollama","model":"gemma3:27b","temperature":0.2,"parse_failures":0}'
                '}'
            )
            total_duration = 1
            prompt_eval_count = 12
            eval_count = 25
            retries_used = 0
            prompt_chars = 100
            approx_prompt_tokens = 25
        return R()

    def embed(self, text, model, timeout_seconds=90):
        class E:
            embedding = [0.2] * 32
        return E()


def test_batch_review_generates_summary(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    provider = BatchProvider()

    def fake_provider_and_config(config_path, output_dir_override, command_name, debug=False):
        from ai_reviewer.config import load_config
        from ai_reviewer.logging_utils import configure_logging, create_run_dir
        cfg = load_config()
        run = create_run_dir(tmp_path, command_name)
        logger = configure_logging(run)
        return provider, cfg, run, logger

    monkeypatch.setattr("ai_reviewer.cli._provider_and_config", fake_provider_and_config)

    p1 = tmp_path / "a.md"
    p2 = tmp_path / "b.md"
    p1.write_text("# A\n\ntext", encoding="utf-8")
    p2.write_text("# B\n\ntext", encoding="utf-8")

    result = runner.invoke(app, ["review", str(tmp_path), "--output-dir", str(tmp_path)])
    assert result.exit_code == 0

    summary_files = list(tmp_path.rglob("batch_summary.json"))
    assert summary_files
    payload = json.loads(summary_files[-1].read_text(encoding="utf-8"))
    assert payload["processed"] >= 1
