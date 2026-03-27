from datetime import datetime

from ai_reviewer.logging_utils import create_run_dir


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 3, 25, 16, 0, 0)


def test_create_run_dir_handles_same_second_collision(tmp_path, monkeypatch):
    import ai_reviewer.logging_utils as lu

    monkeypatch.setattr(lu, "datetime", _FixedDatetime)
    first = create_run_dir(tmp_path, "review")
    second = create_run_dir(tmp_path, "review")
    assert first.exists()
    assert second.exists()
    assert first != second
    assert second.name.startswith(first.name + "_")

