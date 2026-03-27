from pathlib import Path

from ai_reviewer.launcher_checks import run_launcher_selfcheck


def test_launcher_selfcheck_returns_checks():
    checks = run_launcher_selfcheck(Path.cwd())
    names = {c.name for c in checks}
    assert "python" in names
    assert "path_spaces" in names
