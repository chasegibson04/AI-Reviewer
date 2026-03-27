from pathlib import Path

from ai_reviewer.training.scanner import diff_manifest, scan_training_files


def test_training_scan_and_diff(tmp_path: Path):
    root = tmp_path / "training_materials"
    (root / "published_papers").mkdir(parents=True)
    (root / "published_papers" / "a.md").write_text("# A\n\nText", encoding="utf-8")
    scanned = scan_training_files(root)
    assert len(scanned) == 1
    only = next(iter(scanned.values()))
    prev = {only.relative_path: only.fingerprint}
    added, changed, removed, unchanged = diff_manifest(prev, scanned)
    assert not added
    assert not changed
    assert not removed
    assert len(unchanged) == 1

