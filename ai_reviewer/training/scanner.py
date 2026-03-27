from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ai_reviewer.ingest.loaders import SUPPORTED_EXTENSIONS
from ai_reviewer.paths import REPO_ROOT
from ai_reviewer.training.schema import TrainingCategory

TRAINING_CATEGORIES: tuple[TrainingCategory, ...] = (
    "published_papers",
    "formatting_color_guides",
    "external_guides",
    "other_groups_papers",
    "in_progress_examples",
)


@dataclass
class ScannedTrainingFile:
    relative_path: str
    absolute_path: str
    category: TrainingCategory
    fingerprint: str
    size_bytes: int
    modified_timestamp: float


def ensure_training_tree(source_root: Path) -> None:
    source_root.mkdir(parents=True, exist_ok=True)
    for category in TRAINING_CATEGORIES:
        (source_root / category).mkdir(parents=True, exist_ok=True)


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _to_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except Exception:
        return str(path)


def scan_training_files(source_root: Path) -> dict[str, ScannedTrainingFile]:
    ensure_training_tree(source_root)
    scanned: dict[str, ScannedTrainingFile] = {}
    for category in TRAINING_CATEGORIES:
        cat_dir = source_root / category
        for path in sorted(cat_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            rel = _to_relative(path)
            stat = path.stat()
            scanned[rel] = ScannedTrainingFile(
                relative_path=rel,
                absolute_path=str(path.resolve()),
                category=category,
                fingerprint=_sha256(path),
                size_bytes=stat.st_size,
                modified_timestamp=stat.st_mtime,
            )
    return scanned


def diff_manifest(
    previous: dict[str, str],
    current: dict[str, ScannedTrainingFile],
) -> tuple[list[str], list[str], list[str], list[str]]:
    prev_paths = set(previous.keys())
    cur_paths = set(current.keys())
    added = sorted(cur_paths - prev_paths)
    removed = sorted(prev_paths - cur_paths)
    unchanged = sorted(p for p in cur_paths & prev_paths if previous[p] == current[p].fingerprint)
    changed = sorted((cur_paths & prev_paths) - set(unchanged))
    return added, changed, removed, unchanged

