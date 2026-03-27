from pathlib import Path

from ai_reviewer.projects.schema import EvaluationRecord, ProjectDefaults, RunRecord
from ai_reviewer.projects.store import ProjectStore


def test_project_store_lifecycle(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    defaults = ProjectDefaults(review_model="gemma3:27b", embedding_model="mxbai-embed-large:latest")
    _, meta = store.create_project("My Project", "desc", ["tag1"], defaults)
    assert meta.name == "My Project"

    src = tmp_path / "draft.md"
    src.write_text("# Draft\n\ntext", encoding="utf-8")
    mat = store.add_material(meta.project_id, src, "manuscript_draft", "draft", ["v1"])
    assert mat.material_id

    store.add_run_record(
        meta.project_id,
        RunRecord(
            run_id="run1",
            workflow="review",
            output_dir="outputs/run1",
            profile="balanced",
            model="gemma3:27b",
        ),
    )
    store.add_evaluation_record(
        meta.project_id,
        EvaluationRecord(
            evaluation_id="eval1",
            anchor_material_id=mat.material_id,
            run_id="run1",
            profiles=["balanced", "deep"],
            output_dir="outputs/run1",
        ),
    )
    store.mark_run_baseline(meta.project_id, "run1")

    _, loaded = store.get_project(meta.project_id)
    assert len(loaded.materials) == 1
    assert len(loaded.runs) == 1
    assert len(loaded.evaluations) == 1

    store.rename_project(meta.project_id, "Renamed")
    _, renamed = store.get_project(meta.project_id)
    assert renamed.name == "Renamed"

    store.archive_project(meta.project_id, archived=True)
    _, archived = store.get_project(meta.project_id)
    assert archived.archived is True

    store.remove_material(meta.project_id, mat.material_id)
    _, after_remove = store.get_project(meta.project_id)
    assert not after_remove.materials

