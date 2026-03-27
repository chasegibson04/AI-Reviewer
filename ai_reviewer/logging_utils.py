from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def sanitize_name(value: str, fallback: str = "item") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or fallback


def create_run_dir(output_root: Path, command_name: str, label: str | None = None) -> Path:
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cmd = sanitize_name(command_name)
    suffix = f"_{sanitize_name(label)}" if label else ""
    base_name = f"{timestamp}_{cmd}{suffix}"
    run_dir: Path | None = None
    for i in range(0, 1000):
        candidate_name = base_name if i == 0 else f"{base_name}_{i:03d}"
        candidate = output_root / candidate_name
        try:
            candidate.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        run_dir = candidate
        break
    if run_dir is None:
        raise RuntimeError(f"Unable to allocate unique run directory under {output_root}")
    (run_dir / "raw").mkdir(exist_ok=True)
    (run_dir / "reports").mkdir(exist_ok=True)
    (run_dir / "artifacts").mkdir(exist_ok=True)
    return run_dir


def create_child_bundle(parent: Path, stem: str, index: int) -> Path:
    safe = sanitize_name(stem)
    bundle = parent / f"{index:03d}_{safe}"
    bundle.mkdir(parents=True, exist_ok=False)
    (bundle / "raw").mkdir(exist_ok=True)
    (bundle / "reports").mkdir(exist_ok=True)
    (bundle / "artifacts").mkdir(exist_ok=True)
    return bundle


def configure_logging(run_dir: Path, level: str = "INFO", debug_console: bool = False) -> logging.Logger:
    logger = logging.getLogger("ai_reviewer")
    logger.setLevel(level.upper())
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    file_handler = logging.FileHandler(run_dir / "debug.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    stream.setLevel(logging.DEBUG if debug_console else logging.INFO)
    logger.addHandler(stream)
    return logger


def write_run_metadata(run_dir: Path, metadata: dict[str, Any]) -> None:
    with (run_dir / "run_metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, ensure_ascii=False)
