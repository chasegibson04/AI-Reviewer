from pathlib import Path

from typer.testing import CliRunner

from ai_reviewer.cli import app
from ai_reviewer.output_verifier import VerificationResult
from ai_reviewer.projects.schema import ProjectDefaults
from ai_reviewer.projects.store import ProjectStore


class StubProvider:
    def health(self):
        return True, "ok"

    def list_models(self):
        return ["gemma3:27b", "mxbai-embed-large:latest", "mistral-small3.1:24b"]

    def chat(self, request):
        class R:
            content = '{"ok": true}'
            total_duration = 1
            prompt_eval_count = 1
            eval_count = 1
            retries_used = 0
            prompt_chars = 10
            approx_prompt_tokens = 3
        return R()

    def embed(self, text, model, timeout_seconds=90):
        class E:
            embedding = [0.1] * 8
        return E()


def test_review_fails_if_output_verification_fails(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    store = ProjectStore(tmp_path / "projects")
    provider = StubProvider()

    def fake_store():
        return store

    def fake_provider_and_config(config_path, output_dir_override, command_name, debug=False, **kwargs):
        from ai_reviewer.config import load_config
        from ai_reviewer.logging_utils import configure_logging, create_run_dir

        cfg = load_config()
        run = create_run_dir(tmp_path / "outputs", command_name)
        logger = configure_logging(run)
        return provider, cfg, run, logger

    class FakeResult:
        warnings = []

    def fake_run_review(**kwargs):
        return FakeResult()

    monkeypatch.setattr("ai_reviewer.cli._store", fake_store)
    monkeypatch.setattr("ai_reviewer.cli._provider_and_config", fake_provider_and_config)
    monkeypatch.setattr("ai_reviewer.cli.run_review", fake_run_review)
    monkeypatch.setattr(
        "ai_reviewer.cli.verify_review_run",
        lambda run_dir: VerificationResult(ok=False, issues=["missing report"], key_files=[]),
    )

    _, meta = store.create_project("Verifier", "", [], defaults=ProjectDefaults(review_model="gemma3:27b"))
    pdir, _ = store.get_project(meta.project_id)
    (pdir / "materials" / "manuscript" / "doc.md").write_text("# Title\n\nBody", encoding="utf-8")

    result = runner.invoke(app, ["review", "--project", meta.project_id])
    assert result.exit_code != 0
    assert "output verification failed" in result.stdout.lower()
