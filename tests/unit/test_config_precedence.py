import os
from pathlib import Path

import pytest

from ai_reviewer.config import load_config


def test_config_precedence_and_env_override(tmp_path: Path, monkeypatch):
    cfg = tmp_path / "override.yaml"
    cfg.write_text(
        "defaults:\n  output_root: custom_out\ntimeouts:\n  chat_seconds: 111\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_REVIEWER_CHAT_TIMEOUT", "222")
    loaded = load_config(str(cfg))
    assert loaded.defaults.output_root == "custom_out"
    assert loaded.timeouts.chat_seconds == 222


def test_load_config_missing_override_raises():
    with pytest.raises(FileNotFoundError):
        load_config("does_not_exist.yaml")
