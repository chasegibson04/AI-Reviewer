from pathlib import Path

from ai_reviewer.config import load_config, write_example_local_config


def test_load_defaults_has_local_first():
    cfg = load_config()
    assert cfg.defaults.strict_offline is True
    assert cfg.defaults.balanced_review_model == "gemma3:27b"
    assert cfg.training.enabled is True
    assert cfg.orchestrator.model == "phi4-reasoning:latest"


def test_write_example_local_config(tmp_path: Path):
    target = tmp_path / "local.example.yaml"
    write_example_local_config(target)
    assert target.exists()
    cfg = load_config(str(target))
    assert cfg.defaults.output_root == "outputs"
