from pathlib import Path

from ai_reviewer.cli import _resolve_repo_path
from ai_reviewer.paths import REPO_ROOT


def test_resolve_repo_path_relative():
    out = _resolve_repo_path(Path("outputs"))
    assert out == (REPO_ROOT / "outputs").resolve()


def test_resolve_repo_path_absolute(tmp_path: Path):
    out = _resolve_repo_path(tmp_path)
    assert out == tmp_path

