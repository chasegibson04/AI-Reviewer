from pathlib import Path


def test_windows_bat_launcher_has_ollama_check():
    text = Path("launchers/launch_ai_reviewer.bat").read_text(encoding="utf-8")
    assert "http://127.0.0.1:11434/api/version" in text
    assert "python -m ai_reviewer launch" in text


def test_powershell_launcher_has_venv_bootstrap():
    text = Path("launchers/launch_ai_reviewer.ps1").read_text(encoding="utf-8")
    assert "python -m venv" in text
    assert "-m ai_reviewer launch" in text


def test_macos_launcher_has_strict_mode():
    text = Path("launchers/launch_ai_reviewer.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert "ai_reviewer launch" in text
