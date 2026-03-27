from __future__ import annotations

from pathlib import Path

from ai_reviewer.training.schema import TrainingManifest


def load_manifest(path: Path, source_root: Path) -> TrainingManifest:
    if not path.exists():
        return TrainingManifest(source_root=str(source_root))
    return TrainingManifest.model_validate_json(path.read_text(encoding="utf-8"))


def save_manifest(path: Path, manifest: TrainingManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

