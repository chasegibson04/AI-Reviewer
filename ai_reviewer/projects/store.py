from __future__ import annotations

import json
import shutil
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from ai_reviewer.logging_utils import sanitize_name
from ai_reviewer.ingest.loaders import SUPPORTED_EXTENSIONS
from ai_reviewer.projects.schema import EvaluationRecord, MaterialMetadata, ProjectDefaults, ProjectMetadata, RunRecord


class ProjectError(RuntimeError):
    pass


class ProjectStore:
    def __init__(self, root: Path = Path("projects")):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.active_path = self.root / ".active_project"

    def _project_dir(self, project_id: str) -> Path:
        for path in self.root.iterdir():
            if not path.is_dir():
                continue
            meta_file = path / "project.json"
            if not meta_file.exists():
                continue
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            if data.get("project_id") == project_id or data.get("slug") == project_id or data.get("name") == project_id:
                return path
        raise ProjectError(f"Project not found: {project_id}")

    def _ensure_material_dirs(self, project_dir: Path) -> None:
        (project_dir / "materials").mkdir(parents=True, exist_ok=True)
        (project_dir / "materials" / "managed").mkdir(parents=True, exist_ok=True)
        (project_dir / "materials" / "manuscript").mkdir(parents=True, exist_ok=True)
        (project_dir / "materials" / "other").mkdir(parents=True, exist_ok=True)

    def _write_project(self, project_dir: Path, meta: ProjectMetadata) -> None:
        meta.materials = [self._material_with_relative_path(project_dir, material) for material in meta.materials]
        meta.updated_at = datetime.now(timezone.utc).isoformat()
        (project_dir / "project.json").write_text(meta.model_dump_json(indent=2), encoding="utf-8")

    def _read_project(self, project_dir: Path) -> ProjectMetadata:
        self._ensure_material_dirs(project_dir)
        raw_text = (project_dir / "project.json").read_text(encoding="utf-8")
        data = json.loads(raw_text)

        # Repair legacy fields
        if not data.get("slug"):
            name = data.get("name") or project_dir.name
            data["slug"] = sanitize_name(name.lower(), fallback="project")

        for material in data.get("materials", []):
            if not material.get("original_path"):
                mid = material.get("material_id")
                fname = material.get("filename")
                if mid and fname:
                    managed = project_dir / "materials" / "managed" / mid / fname
                    if managed.exists():
                        material["original_path"] = str(managed.resolve())
                    else:
                        material["original_path"] = str(project_dir / "materials" / fname)
                else:
                    material["original_path"] = str(project_dir / "materials" / (fname or "unknown"))

        meta = ProjectMetadata.model_validate(data)
        normalized_materials = [self._material_with_relative_path(project_dir, material) for material in meta.materials]
        changed = any(material.relative_path != normalized.relative_path for material, normalized in zip(meta.materials, normalized_materials))
        if changed:
            meta.materials = normalized_materials
            self._write_project(project_dir, meta)
        else:
            meta.materials = normalized_materials
        return meta

    def _material_relative_path(self, project_dir: Path, material: MaterialMetadata) -> str:
        if material.relative_path:
            return str(material.relative_path).replace("\\", "/")
        try:
            original = Path(material.original_path)
            if original.exists():
                return str(original.resolve().relative_to(project_dir.resolve())).replace("\\", "/")
        except Exception:
            pass
        managed = project_dir / "materials" / "managed" / material.material_id / material.filename
        if managed.exists():
            return str(managed.relative_to(project_dir)).replace("\\", "/")
        legacy = project_dir / "materials" / material.material_id / material.filename
        if legacy.exists():
            return str(legacy.relative_to(project_dir)).replace("\\", "/")
        if "manual-folder" in material.tags:
            folder = "manuscript" if material.category == "manuscript_draft" else "other"
            return f"materials/{folder}/{material.filename}"
        return f"materials/managed/{material.material_id}/{material.filename}"

    def _material_with_relative_path(self, project_dir: Path, material: MaterialMetadata) -> MaterialMetadata:
        if material.relative_path:
            return material.model_copy(update={"relative_path": str(material.relative_path).replace("\\", "/")})
        return material.model_copy(update={"relative_path": self._material_relative_path(project_dir, material)})

    def create_project(
        self,
        name: str,
        description: str,
        tags: list[str],
        defaults: ProjectDefaults,
        output_root: str = "outputs",
    ) -> tuple[Path, ProjectMetadata]:
        slug = sanitize_name(name.lower(), fallback="project")
        project_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "_" + slug
        project_dir = self.root / project_id
        if project_dir.exists():
            raise ProjectError(f"Project directory already exists: {project_dir}")

        for child in ["materials", "runs", "evaluations", "notes", "cache"]:
            (project_dir / child).mkdir(parents=True, exist_ok=True)
        self._ensure_material_dirs(project_dir)

        meta = ProjectMetadata(
            project_id=project_id,
            name=name,
            slug=slug,
            description=description,
            tags=tags,
            defaults=defaults,
            output_root=output_root,
        )
        self._write_project(project_dir, meta)
        self.set_active_project(project_id)
        return project_dir, meta

    def list_projects(self, include_archived: bool = False) -> list[tuple[Path, ProjectMetadata]]:
        out: list[tuple[Path, ProjectMetadata]] = []
        for path in sorted(self.root.iterdir()):
            if not path.is_dir():
                continue
            meta_file = path / "project.json"
            if not meta_file.exists():
                continue
            try:
                meta = self._read_project(path)
                if meta.archived and not include_archived:
                    continue
                out.append((path, meta))
            except Exception:
                # Log or warn if needed, but skip broken project metadata
                continue
        return out

    def get_project(self, project_id: str | None = None) -> tuple[Path, ProjectMetadata]:
        if project_id is None:
            project_id = self.get_active_project_id()
            if project_id is None:
                raise ProjectError("No active project selected.")
        pdir = self._project_dir(project_id)
        return pdir, self._read_project(pdir)

    def set_active_project(self, project_id: str) -> None:
        pdir = self._project_dir(project_id)
        self.active_path.write_text(str(pdir.name), encoding="utf-8")

    def get_active_project_id(self) -> str | None:
        if not self.active_path.exists():
            return None
        return self.active_path.read_text(encoding="utf-8").strip() or None

    def rename_project(self, project_id: str, new_name: str) -> ProjectMetadata:
        pdir, meta = self.get_project(project_id)
        meta.name = new_name
        meta.slug = sanitize_name(new_name.lower(), fallback=meta.slug)
        self._write_project(pdir, meta)
        return meta

    def archive_project(self, project_id: str, archived: bool = True) -> ProjectMetadata:
        pdir, meta = self.get_project(project_id)
        meta.archived = archived
        self._write_project(pdir, meta)
        return meta

    def delete_project(self, project_id: str, force: bool = False) -> None:
        pdir, meta = self.get_project(project_id)
        if not force:
            raise ProjectError("Refusing delete without force=True")
        shutil.rmtree(pdir)
        if self.get_active_project_id() == pdir.name:
            self.active_path.unlink(missing_ok=True)

    def set_defaults(self, project_id: str, defaults: ProjectDefaults) -> ProjectMetadata:
        pdir, meta = self.get_project(project_id)
        meta.defaults = defaults
        self._write_project(pdir, meta)
        return meta

    def add_material(
        self,
        project_id: str,
        source: Path,
        category: str,
        description: str = "",
        tags: list[str] | None = None,
    ) -> MaterialMetadata:
        if not source.exists() or not source.is_file():
            raise ProjectError(f"Material source missing: {source}")

        pdir, meta = self.get_project(project_id)
        self._ensure_material_dirs(pdir)
        mid = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        mdir = pdir / "materials" / "managed" / mid
        mdir.mkdir(parents=True, exist_ok=False)

        safe_name = sanitize_name(source.name, fallback="material")
        target = mdir / safe_name
        shutil.copy2(source, target)

        material = MaterialMetadata(
            material_id=mid,
            filename=safe_name,
            original_path=str(source.resolve()),
            relative_path=str(target.relative_to(pdir)).replace("\\", "/"),
            category=category,
            description=description,
            tags=tags or [],
        )
        (mdir / "metadata.json").write_text(material.model_dump_json(indent=2), encoding="utf-8")

        meta.materials.append(material)
        self._write_project(pdir, meta)
        return material

    def remove_material(self, project_id: str, material_id: str) -> None:
        pdir, meta = self.get_project(project_id)
        remaining: list[MaterialMetadata] = []
        for material in meta.materials:
            if material.material_id != material_id:
                remaining.append(material)
                continue
            mdir = pdir / "materials" / "managed" / material.material_id
            if mdir.exists():
                shutil.rmtree(mdir)
        meta.materials = remaining
        self._write_project(pdir, meta)

    def material_path(self, project_dir: Path, material: MaterialMetadata) -> Path:
        managed = project_dir / "materials" / "managed" / material.material_id / material.filename
        if managed.exists():
            return managed
        original = Path(material.original_path)
        if original.exists():
            return original
        legacy = project_dir / "materials" / material.material_id / material.filename
        if legacy.exists():
            return legacy
        return managed

    def _manual_material_entries(self, project_dir: Path) -> list[MaterialMetadata]:
        entries: list[MaterialMetadata] = []
        mappings = [("manuscript", "manuscript_draft"), ("other", "miscellaneous")]
        for folder_name, category in mappings:
            root = project_dir / "materials" / folder_name
            root.mkdir(parents=True, exist_ok=True)
            for path in sorted(root.rglob("*")):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                rel = str(path.relative_to(project_dir)).replace("\\", "/")
                digest = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]
                entries.append(
                    MaterialMetadata(
                        material_id=f"manual_{folder_name}_{digest}",
                        filename=path.name,
                        original_path=str(path.resolve()),
                        relative_path=rel,
                        category=category,  # type: ignore[arg-type]
                        description=f"Auto-discovered from materials/{folder_name}",
                        tags=["manual-folder", folder_name],
                    )
                )
        return entries

    def sync_project_material_inventory(self, project_id: str) -> tuple[int, int, int]:
        pdir, meta = self.get_project(project_id)
        self._ensure_material_dirs(pdir)
        manual_entries = self._manual_material_entries(pdir)
        manual_by_id = {m.material_id: m for m in manual_entries}
        existing_manual = {m.material_id: m for m in meta.materials if "manual-folder" in m.tags}
        managed_entries = [m for m in meta.materials if "manual-folder" not in m.tags]

        added = len([m for mid, m in manual_by_id.items() if mid not in existing_manual])
        changed = len(
            [
                m
                for mid, m in manual_by_id.items()
                if mid in existing_manual and existing_manual[mid].original_path != m.original_path
            ]
        )
        removed = len([mid for mid in existing_manual if mid not in manual_by_id])

        meta.materials = managed_entries + list(manual_by_id.values())
        self._write_project(pdir, meta)
        return added, changed, removed

    def add_run_record(self, project_id: str, record: RunRecord) -> None:
        pdir, meta = self.get_project(project_id)
        meta.runs.append(record)
        self._write_project(pdir, meta)

    def add_evaluation_record(self, project_id: str, record: EvaluationRecord) -> None:
        pdir, meta = self.get_project(project_id)
        meta.evaluations.append(record)
        self._write_project(pdir, meta)

    def mark_run_baseline(self, project_id: str, run_id: str) -> None:
        pdir, meta = self.get_project(project_id)
        notes = pdir / "notes" / "baseline.txt"
        notes.write_text(run_id, encoding="utf-8")
        self._write_project(pdir, meta)

    def get_run_record(self, project_id: str, run_id: str) -> RunRecord:
        _, meta = self.get_project(project_id)
        for run in meta.runs:
            if run.run_id == run_id:
                return run
        raise ProjectError(f"Run not found: {run_id}")
