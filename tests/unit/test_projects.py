from pathlib import Path
import json

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


def test_project_store_backfills_missing_material_relative_path(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    defaults = ProjectDefaults(review_model="gemma3:27b", embedding_model="mxbai-embed-large:latest")
    pdir, meta = store.create_project("Legacy Project", "", [], defaults)

    source = tmp_path / "legacy.md"
    source.write_text("# Legacy\n\ntext", encoding="utf-8")
    material = store.add_material(meta.project_id, source, "manuscript_draft")

    project_json = pdir / "project.json"
    payload = json.loads(project_json.read_text(encoding="utf-8"))
    payload["materials"][0].pop("relative_path", None)
    project_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    _, loaded = store.get_project(meta.project_id)
    assert loaded.materials[0].relative_path == f"materials/managed/{material.material_id}/{material.filename}"

    rewritten = json.loads(project_json.read_text(encoding="utf-8"))
    assert rewritten["materials"][0]["relative_path"] == f"materials/managed/{material.material_id}/{material.filename}"


def test_project_store_backfills_missing_slug_and_original_path(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")

    # Create a legacy-style project.json directly
    project_id = "legacy_proj"
    project_dir = tmp_path / "projects" / project_id
    project_dir.mkdir(parents=True)
    (project_dir / "materials").mkdir()
    (project_dir / "runs").mkdir()
    (project_dir / "evaluations").mkdir()

    legacy_data = {
        "project_id": project_id,
        "name": "Legacy Project Name",
        # "slug": "legacy-project-name", # MISSING
        "defaults": {
            "review_model": "test-model",
            "profile": "balanced"
        },
        "materials": [
            {
                "material_id": "mat1",
                "filename": "test.pdf",
                # "original_path": "/path/to/test.pdf", # MISSING
                "category": "manuscript_draft"
            }
        ]
    }

    (project_dir / "project.json").write_text(json.dumps(legacy_data), encoding="utf-8")

    # Should not crash and should repair
    _, loaded = store.get_project(project_id)
    assert loaded.slug == "legacy_project_name"
    assert loaded.materials[0].original_path
    assert "test.pdf" in loaded.materials[0].original_path

    # Verify writeback occurred
    rewritten = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert rewritten["slug"] == "legacy_project_name"
    assert rewritten["materials"][0]["original_path"]


def test_list_projects_skips_broken_metadata(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")

    # Create one valid project
    store.create_project("Good Project", "", [], ProjectDefaults(review_model="m1"))

    # Create one broken project (invalid JSON)
    bad_dir = tmp_path / "projects" / "broken_proj"
    bad_dir.mkdir(parents=True)
    (bad_dir / "project.json").write_text("{broken: json", encoding="utf-8")

    # Create one project with irreparable missing required fields (e.g. no defaults)
    missing_dir = tmp_path / "projects" / "missing_proj"
    missing_dir.mkdir(parents=True)
    (missing_dir / "project.json").write_text(json.dumps({
        "project_id": "missing_proj",
        "name": "Missing Required Fields"
        # No defaults -> Pydantic error
    }), encoding="utf-8")

    # Should not crash and should only find the good one
    projects = store.list_projects()
    assert len(projects) == 1
    assert projects[0][1].name == "Good Project"
