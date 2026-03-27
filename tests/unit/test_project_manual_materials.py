from pathlib import Path

from ai_reviewer.projects.schema import ProjectDefaults
from ai_reviewer.projects.store import ProjectStore


def test_manual_material_sync(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    _, meta = store.create_project("Manual", "", [], ProjectDefaults(review_model="gemma3:27b"))
    pdir, _ = store.get_project(meta.project_id)

    manuscript = pdir / "materials" / "manuscript" / "draft.md"
    manuscript.write_text("# Draft\n\ntext", encoding="utf-8")
    other = pdir / "materials" / "other" / "notes.txt"
    other.write_text("notes", encoding="utf-8")

    added, changed, removed = store.sync_project_material_inventory(meta.project_id)
    assert added >= 2
    assert changed == 0
    assert removed == 0
    _, synced = store.get_project(meta.project_id)
    assert len(synced.materials) >= 2

    manuscript.unlink()
    _, _, removed2 = store.sync_project_material_inventory(meta.project_id)
    assert removed2 >= 1

