from pathlib import Path

from ai_reviewer.config import load_config
from ai_reviewer.training.cache import TrainingCacheManager


def test_training_sync_add_change_remove(tmp_path: Path):
    source_root = tmp_path / "training_materials"
    cache_root = tmp_path / "cache"
    (source_root / "published_papers").mkdir(parents=True)
    f = source_root / "published_papers" / "paper.md"
    f.write_text("# Paper\n\nInitial content", encoding="utf-8")

    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        f"training:\n  enabled: true\n  source_root: {source_root.as_posix()}\n  cache_root: {cache_root.as_posix()}\n",
        encoding="utf-8",
    )
    cfg = load_config(str(cfg_path))
    manager = TrainingCacheManager.from_config(cfg)

    r1 = manager.sync()
    assert r1.added == 1
    assert r1.active_files == 1

    f.write_text("# Paper\n\nUpdated content with style and format guidance", encoding="utf-8")
    r2 = manager.sync()
    assert r2.changed == 1

    f.unlink()
    r3 = manager.sync()
    assert r3.removed == 1
    status = manager.status()
    assert status["active_guidance_files"] == 0

