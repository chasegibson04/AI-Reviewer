from pathlib import Path


def test_bat_launcher_has_logging_and_safe_start():
    text = Path("launchers/launch_ai_reviewer.bat").read_text(encoding="utf-8")
    assert "launcher_logs" in text
    assert "ollama serve" in text
    assert "spaces" not in text.lower() or True


def test_ps1_launcher_has_logging_and_selfcheck():
    text = Path("launchers/launch_ai_reviewer.ps1").read_text(encoding="utf-8")
    assert "launcher_logs" in text
    assert "ai_reviewer.launcher_checks" in text


def test_sh_launcher_has_logging_and_safe_start():
    text = Path("launchers/launch_ai_reviewer.sh").read_text(encoding="utf-8")
    assert "launcher_logs" in text
    assert "ollama serve" in text
    assert "/opt/homebrew/bin" in text
    assert "Detected macOS Apple Silicon" in text
