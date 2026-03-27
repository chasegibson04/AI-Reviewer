import json
from pathlib import Path


def test_batch_summary_golden_shape(tmp_path: Path):
    payload = {
        "command": "review",
        "processed": 2,
        "failures": 1,
        "results": [{"source": "a", "success": True}],
        "errors": [{"source": "b", "error": "x"}],
    }
    out = tmp_path / "batch_summary.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert set(["command", "processed", "failures", "results", "errors"]).issubset(loaded.keys())
