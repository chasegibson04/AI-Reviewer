from pathlib import Path

from typer.testing import CliRunner

from ai_reviewer.cli import app
from ai_reviewer.ingest.types import ParsedDocument


runner = CliRunner()


class FakeProvider:
    def __init__(self):
        self.calls = []

    def health(self):
        return True, "ok"

    def list_models(self):
        return ["gemma3:27b", "mxbai-embed-large:latest", "mistral-small3.1:24b"]

    def chat(self, request):
        self.calls.append(request)
        class R:
            content = '{"ok": true}'
            total_duration = 1
            prompt_eval_count = 10
            eval_count = 20
        return R()

    def embed(self, text, model, timeout_seconds=90):
        class E:
            embedding = [0.1] * 16
        return E()


def test_list_models_command(monkeypatch, tmp_path: Path):
    provider = FakeProvider()

    def fake_provider_and_config(config_path, output_dir_override, command_name, debug=False):
        from ai_reviewer.config import load_config
        from ai_reviewer.logging_utils import configure_logging, create_run_dir

        cfg = load_config()
        out = output_dir_override or tmp_path
        run = create_run_dir(Path(out), command_name)
        logger = configure_logging(run)
        return provider, cfg, run, logger

    monkeypatch.setattr("ai_reviewer.cli._provider_and_config", fake_provider_and_config)
    result = runner.invoke(app, ["list-models", "--config-path", "config/defaults.yaml"])
    assert result.exit_code == 0
    assert "Detected Ollama Models" in result.stdout


def test_ingest_command(monkeypatch, tmp_path: Path):
    provider = FakeProvider()

    def fake_provider_and_config(config_path, output_dir_override, command_name, debug=False):
        from ai_reviewer.config import load_config
        from ai_reviewer.logging_utils import configure_logging, create_run_dir

        cfg = load_config()
        out = output_dir_override or tmp_path
        run = create_run_dir(Path(out), command_name)
        logger = configure_logging(run)
        return provider, cfg, run, logger

    monkeypatch.setattr("ai_reviewer.cli._provider_and_config", fake_provider_and_config)
    md = tmp_path / "x.md"
    md.write_text("# Title\n\nSome text", encoding="utf-8")
    result = runner.invoke(app, ["ingest", str(md), "--output-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "Ingested 1 documents" in result.stdout
