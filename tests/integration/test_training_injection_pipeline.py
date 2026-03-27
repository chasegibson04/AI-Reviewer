from pathlib import Path

from typer.testing import CliRunner

from ai_reviewer.cli import app


class TrainingAwareProvider:
    def __init__(self):
        self.prompts = []

    def health(self):
        return True, "ok"

    def list_models(self):
        return ["gemma3:27b", "mxbai-embed-large:latest", "mistral-small3.1:24b"]

    def chat(self, request):
        self.prompts.append(request.user_prompt)

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


def test_review_injects_training_guidance(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    provider = TrainingAwareProvider()
    counter = {"n": 0}

    train_root = tmp_path / "training_materials"
    (train_root / "published_papers").mkdir(parents=True)
    (train_root / "published_papers" / "style.md").write_text(
        "# Style\n\nUse concise language and clear section structure.",
        encoding="utf-8",
    )
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        f"training:\n"
        f"  enabled: true\n"
        f"  source_root: {train_root.as_posix()}\n"
        f"  cache_root: {(tmp_path / 'training_cache').as_posix()}\n"
        f"  auto_sync_on_start: true\n"
        f"  inject_by_default: true\n",
        encoding="utf-8",
    )

    def fake_provider_and_config(config_path, output_dir_override, command_name, debug=False):
        from ai_reviewer.config import load_config
        from ai_reviewer.logging_utils import configure_logging, create_run_dir
        from ai_reviewer.training.cache import TrainingCacheManager

        counter["n"] += 1
        cfg = load_config(config_path)
        run = create_run_dir(tmp_path, f"{command_name}_{counter['n']}")
        logger = configure_logging(run)
        TrainingCacheManager.from_config(cfg, logger=logger).sync()
        return provider, cfg, run, logger

    monkeypatch.setattr("ai_reviewer.cli._provider_and_config", fake_provider_and_config)

    paper = tmp_path / "paper.md"
    paper.write_text("# Paper\n\nResults section.", encoding="utf-8")
    result = runner.invoke(app, ["review", str(paper), "--config-path", str(cfg_path)])
    assert result.exit_code == 0
    assert any("LAB TRAINING GUIDANCE" in p for p in provider.prompts)


def test_review_can_disable_training_guidance(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    provider = TrainingAwareProvider()

    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        f"training:\n"
        f"  enabled: true\n"
        f"  source_root: {(tmp_path / 'training_materials').as_posix()}\n"
        f"  cache_root: {(tmp_path / 'training_cache').as_posix()}\n",
        encoding="utf-8",
    )

    def fake_provider_and_config(config_path, output_dir_override, command_name, debug=False):
        from ai_reviewer.config import load_config
        from ai_reviewer.logging_utils import configure_logging, create_run_dir

        cfg = load_config(config_path)
        run = create_run_dir(tmp_path, command_name)
        logger = configure_logging(run)
        return provider, cfg, run, logger

    monkeypatch.setattr("ai_reviewer.cli._provider_and_config", fake_provider_and_config)
    paper = tmp_path / "paper.md"
    paper.write_text("# Paper\n\nResults section.", encoding="utf-8")
    result = runner.invoke(app, ["review", str(paper), "--config-path", str(cfg_path), "--disable-training-guidance"])
    assert result.exit_code == 0
    assert not any("LAB TRAINING GUIDANCE" in p for p in provider.prompts)
