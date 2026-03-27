from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class VerificationResult:
    ok: bool
    issues: list[str]
    key_files: list[Path]


def _non_empty(path: Path) -> bool:
    return path.exists() and path.is_file() and path.stat().st_size > 0


def _require_non_empty(path: Path, issues: list[str], label: str) -> None:
    if not _non_empty(path):
        issues.append(f"Missing or empty {label}: {path}")


def verify_review_run(run_dir: Path) -> VerificationResult:
    issues: list[str] = []
    key_files: list[Path] = []

    if not run_dir.exists():
        return VerificationResult(False, [f"Run directory missing: {run_dir}"], key_files)

    _require_non_empty(run_dir / "run_metadata.json", issues, "run_metadata.json")
    _require_non_empty(run_dir / "debug.log", issues, "debug.log")
    _require_non_empty(run_dir / "artifacts" / "batch_summary.json", issues, "batch_summary.json")

    bundle_dirs = [
        p for p in run_dir.iterdir()
        if p.is_dir() and re.match(r"^\d{3}_", p.name)
    ]
    if not bundle_dirs:
        issues.append("No per-document bundle directories found (expected 001_<name>, etc).")
    else:
        first = sorted(bundle_dirs)[0]
        for rel in ("validated_review.json", "review_report.md", "review_report.txt", "review_report.docx", "run_metadata.json"):
            path = first / rel
            _require_non_empty(path, issues, rel)
            key_files.append(path)
        _require_non_empty(first / "manuscript_comment_manifest.json", issues, "manuscript_comment_manifest.json")
        _require_non_empty(first / "source_mode.json", issues, "source_mode.json")
        _require_non_empty(first / "commented_docx_validation.json", issues, "commented_docx_validation.json")
        annotated_candidates = [
            first / "reviewed_manuscript_with_comments.docx",
            first / "surrogate_manuscript_from_pdf_with_comments.docx",
        ]
        if not any(_non_empty(p) for p in annotated_candidates):
            issues.append("Missing annotated manuscript DOCX (expected reviewed_manuscript_with_comments.docx or surrogate_manuscript_from_pdf_with_comments.docx).")
        else:
            key_files.append(next(p for p in annotated_candidates if _non_empty(p)))

    return VerificationResult(ok=not issues, issues=issues, key_files=key_files)


def verify_deep_run(run_dir: Path) -> VerificationResult:
    issues: list[str] = []
    key_files = [
        run_dir / "run_metadata.json",
        run_dir / "final_deep_review_report.json",
        run_dir / "final_deep_review_report.md",
        run_dir / "final_deep_review_report.txt",
        run_dir / "final_deep_review_report.docx",
        run_dir / "docx_comment_manifest.json",
        run_dir / "manuscript_comment_manifest.json",
        run_dir / "source_mode.json",
        run_dir / "commented_docx_validation.json",
        run_dir / "deep_run_plan.json",
    ]
    for path in key_files:
        _require_non_empty(path, issues, path.name)
    if _non_empty(run_dir / "stage_11_reconciliation.json"):
        key_files.append(run_dir / "stage_11_reconciliation.json")
    elif _non_empty(run_dir / "stage_07_reconciliation.json"):
        key_files.append(run_dir / "stage_07_reconciliation.json")
    else:
        issues.append("Missing reconciliation artifact (stage_11_reconciliation.json or stage_07_reconciliation.json).")
    _require_non_empty(run_dir / "debug.log", issues, "debug.log")
    annotated_candidates = [
        run_dir / "reviewed_manuscript_with_comments.docx",
        run_dir / "surrogate_manuscript_from_pdf_with_comments.docx",
    ]
    if not any(_non_empty(p) for p in annotated_candidates):
        issues.append("Missing annotated deep-run manuscript DOCX.")
    else:
        key_files.append(next(p for p in annotated_candidates if _non_empty(p)))
    return VerificationResult(ok=not issues, issues=issues, key_files=key_files)


def verify_evaluation_run(run_dir: Path) -> VerificationResult:
    issues: list[str] = []
    key_files = [
        run_dir / "evaluation_packet.json",
        run_dir / "evaluation_summary.md",
        run_dir / "evaluation_summary.docx",
        run_dir / "run_metadata.json",
        run_dir / "debug.log",
    ]
    for path in key_files:
        _require_non_empty(path, issues, path.name)

    workflows_dir = run_dir / "workflows"
    if not workflows_dir.exists():
        issues.append(f"Missing workflows directory: {workflows_dir}")
    else:
        bundles = [p for p in workflows_dir.iterdir() if p.is_dir()]
        if not bundles:
            issues.append("No workflow bundles found in evaluation output.")
        else:
            sample = sorted(bundles)[0]
            for rel in ("validated_review.json", "review_report.md", "review_report.txt", "review_report.docx"):
                _require_non_empty(sample / rel, issues, f"{sample.name}/{rel}")
            key_files.append(sample / "review_report.md")

    return VerificationResult(ok=not issues, issues=issues, key_files=key_files)
