from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ALLOWED_PROJECT_IDS = {
    "20260325163524_test-existingphactorpaper",
    "20260327051312_miniaturization_d2b",
}

REQUIRED_FILES = [
    "run_summary.json",
    "routing_trace.json",
    "manuscript_comment_manifest.json",
    "manuscript_comment_metadata.json",
    "manuscript_suggested_changes_manifest.json",
    "support_ingest_report.json",
    "support_usage_ledger.json",
    "support_ingest_cache_index.json",
    "citation_verification_ledger.json",
    "claim_verification_summary.json",
    "validation_report.json",
]


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _latest_validation_root(project_root: Path) -> Path:
    root = project_root / "test_outputs" / "allowed_project_validation"
    candidates = sorted([path for path in root.iterdir() if path.is_dir()], reverse=True)
    if not candidates:
        raise FileNotFoundError("No allowed-project validation directories found.")
    return candidates[0]


def _score_run(run_dir: Path) -> dict[str, Any]:
    missing = [name for name in REQUIRED_FILES if not (run_dir / name).exists()]
    run_summary = _load_json(run_dir / "run_summary.json", {})
    routing = _load_json(run_dir / "routing_trace.json", {})
    comments = _load_json(run_dir / "manuscript_comment_manifest.json", [])
    comment_metadata = _load_json(run_dir / "manuscript_comment_metadata.json", [])
    suggested_changes = _load_json(run_dir / "manuscript_suggested_changes_manifest.json", [])
    ingest = _load_json(run_dir / "support_ingest_report.json", {})
    support_usage = _load_json(run_dir / "support_usage_ledger.json", {})
    citation = _load_json(run_dir / "citation_verification_ledger.json", {})
    claim_summary = _load_json(run_dir / "claim_verification_summary.json", {})
    validation = _load_json(run_dir / "validation_report.json", {})

    comment_texts = [str(item) for item in comments if str(item).strip()]
    clutter_hits = [
        text for text in comment_texts if re.search(r"review round|stage:|severity:|source:", text, flags=re.IGNORECASE)
    ]
    long_comments = [text for text in comment_texts if len(text) > 220]
    no_op_changes = [
        row
        for row in suggested_changes
        if isinstance(row, dict) and str(row.get("original", "")).strip() == str(row.get("suggested", "")).strip()
    ]
    citation_entries = citation.get("entries", []) if isinstance(citation.get("entries"), list) else []
    local_cache_hits = sum(1 for row in citation_entries if str(row.get("source_resolution", "")) == "local_cache")
    abstract_only_hits = sum(1 for row in citation_entries if str(row.get("status", "")) == "abstract_only")
    stage_statuses = routing.get("stage_model_map", []) if isinstance(routing.get("stage_model_map"), list) else []
    degraded_honest = (
        "reasoning_mode_requested" in run_summary
        and "reasoning_mode_effective" in run_summary
        and "degraded" in run_summary
        and "fallback_reason" in run_summary
        and bool(stage_statuses)
    )

    return {
        "run_dir": str(run_dir),
        "profile": run_summary.get("profile"),
        "reasoning_mode_effective": run_summary.get("reasoning_mode_effective"),
        "validation_valid": bool(validation.get("valid")),
        "missing_files": missing,
        "comment_count": len(comment_texts),
        "clutter_hits": len(clutter_hits),
        "long_comment_hits": len(long_comments),
        "no_op_suggested_changes": len(no_op_changes),
        "citation_mention_count": citation.get("mention_count", 0),
        "citation_entry_count": len(citation_entries),
        "citation_status_counts": claim_summary.get("status_counts", {}),
        "citation_local_cache_hits": local_cache_hits,
        "citation_abstract_only_hits": abstract_only_hits,
        "support_used_sources": len(support_usage.get("used_sources", [])),
        "support_unused_sources": len(support_usage.get("unused_sources", [])),
        "support_cache_reused_docs": ingest.get("cache_reused_docs", 0),
        "support_cache_refreshed_docs": ingest.get("cache_refreshed_docs", 0),
        "support_ingested_docs": ingest.get("ingested_docs", 0),
        "degraded_honest": degraded_honest,
        "stage_statuses": [
            {
                "stage": row.get("stage"),
                "model": row.get("model"),
                "status": row.get("status"),
            }
            for row in stage_statuses
            if isinstance(row, dict)
        ],
        "metadata_stage_counts": _count_metadata_stages(comment_metadata),
    }


def _count_metadata_stages(rows: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        stage = str(row.get("stage", "unknown"))
        counts[stage] = counts.get(stage, 0) + 1
    return counts


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    validation_root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else _latest_validation_root(project_root)
    index_path = validation_root / "validation_index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing validation index: {index_path}")

    index = _load_json(index_path, {})
    allowed = set(index.get("allowed_projects_only", []))
    if allowed != ALLOWED_PROJECT_IDS:
        raise RuntimeError(f"Validation root is not approved-project-only: {sorted(allowed)}")

    runs = index.get("runs", [])
    evaluations = []
    for record in runs:
        run_dir = Path(record["output_dir"]).resolve()
        manuscript = str(record.get("manuscript", ""))
        if not any(project_id in manuscript for project_id in ALLOWED_PROJECT_IDS):
            raise RuntimeError(f"Run manuscript is not from an approved project: {manuscript}")
        evaluations.append(_score_run(run_dir))

    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "validation_root": str(validation_root),
        "allowed_projects_only": sorted(ALLOWED_PROJECT_IDS),
        "runs": evaluations,
    }

    out_dir = validation_root / "artifact_evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "artifact_evaluation.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# Artifact-First Evaluation",
        "",
        f"- Validation root: `{validation_root}`",
        f"- Approved projects only: `{', '.join(sorted(ALLOWED_PROJECT_IDS))}`",
        "",
        "| Run | Valid | Comments | Citation mentions | Local cache hits | Abstract-only hits | Support used | No-op rewrites | Degraded honesty |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in evaluations:
        run_name = Path(row["run_dir"]).name
        lines.append(
            f"| {run_name} | {row['validation_valid']} | {row['comment_count']} | {row['citation_mention_count']} | "
            f"{row['citation_local_cache_hits']} | {row['citation_abstract_only_hits']} | {row['support_used_sources']} | "
            f"{row['no_op_suggested_changes']} | {row['degraded_honest']} |"
        )
    (out_dir / "artifact_evaluation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
