from __future__ import annotations

from dataclasses import dataclass
import json
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


def _load_json(path: Path, issues: list[str], label: str) -> dict:
    if not _non_empty(path):
        issues.append(f"Missing or empty {label}: {path}")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append(f"Invalid JSON in {label}: {exc}")
        return {}
    if not isinstance(data, dict):
        issues.append(f"{label} must be a JSON object.")
        return {}
    return data


def _read_text(path: Path, issues: list[str], label: str) -> str:
    if not _non_empty(path):
        issues.append(f"Missing or empty {label}: {path}")
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        issues.append(f"Could not read {label}: {exc}")
        return ""


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
        _require_non_empty(first / "manuscript_suggested_changes_manifest.json", issues, "manuscript_suggested_changes_manifest.json")
        _require_non_empty(first / "suggested_changes_validation.json", issues, "suggested_changes_validation.json")
        annotated_candidates = [
            first / "reviewed_manuscript_with_comments.docx",
            first / "surrogate_manuscript_from_pdf_with_comments.docx",
        ]
        if not any(_non_empty(p) for p in annotated_candidates):
            issues.append("Missing annotated manuscript DOCX (expected reviewed_manuscript_with_comments.docx or surrogate_manuscript_from_pdf_with_comments.docx).")
        else:
            key_files.append(next(p for p in annotated_candidates if _non_empty(p)))
        suggested_candidates = [
            first / "reviewed_manuscript_with_suggested_changes.docx",
            first / "surrogate_manuscript_from_pdf_with_suggested_changes.docx",
        ]
        if not any(_non_empty(p) for p in suggested_candidates):
            issues.append("Missing suggested-changes manuscript DOCX.")
        else:
            key_files.append(next(p for p in suggested_candidates if _non_empty(p)))

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
        run_dir / "manuscript_suggested_changes_manifest.json",
        run_dir / "suggested_changes_validation.json",
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
    suggested_candidates = [
        run_dir / "reviewed_manuscript_with_suggested_changes.docx",
        run_dir / "surrogate_manuscript_from_pdf_with_suggested_changes.docx",
    ]
    if not any(_non_empty(p) for p in suggested_candidates):
        issues.append("Missing suggested-changes deep-run manuscript DOCX.")
    else:
        key_files.append(next(p for p in suggested_candidates if _non_empty(p)))

    run_meta = _load_json(run_dir / "run_metadata.json", issues, "run_metadata.json")
    report = _load_json(run_dir / "final_deep_review_report.json", issues, "final_deep_review_report.json")
    comment_manifest = _load_json(run_dir / "manuscript_comment_manifest.json", issues, "manuscript_comment_manifest.json")
    docx_manifest = _load_json(run_dir / "docx_comment_manifest.json", issues, "docx_comment_manifest.json")
    commented_validation = _load_json(run_dir / "commented_docx_validation.json", issues, "commented_docx_validation.json")

    report_md = _read_text(run_dir / "final_deep_review_report.md", issues, "final_deep_review_report.md")
    if report_md:
        if len(report_md.strip()) < 600:
            issues.append("final_deep_review_report.md is unusually short; expected non-trivial synthesis content.")
        required_heads = ["## final", "## stage_status", "## warnings"]
        for head in required_heads:
            if head not in report_md.lower():
                issues.append(f"final_deep_review_report.md missing expected section heading: {head}")

    if report:
        final_payload = report.get("final", {})
        if not isinstance(final_payload, dict):
            issues.append("final_deep_review_report.json has invalid final payload.")
        else:
            major = len(final_payload.get("consolidated_weaknesses", []) or [])
            actions = len(final_payload.get("priority_actions", []) or [])
            if major == 0 and actions == 0:
                issues.append("Final report has no weaknesses/actions; likely low-value or malformed synthesis.")
        report_warnings = report.get("warnings", [])
        if isinstance(report_warnings, list) and run_meta:
            expected = int(run_meta.get("warnings_count", 0) or 0)
            if expected != len(report_warnings):
                issues.append(
                    f"warnings_count mismatch: run_metadata={expected}, final_report={len(report_warnings)}."
                )

    if run_meta:
        stage_status = run_meta.get("stage_status", {})
        if isinstance(stage_status, dict):
            failed = [k for k, v in stage_status.items() if str(v).lower() == "failed"]
            degraded = [k for k, v in stage_status.items() if str(v).lower() == "degraded"]
            if failed and str(run_meta.get("status", "")).lower() == "success":
                issues.append("run_metadata status=success despite failed stages.")
            if degraded and str(run_meta.get("status", "")).lower() == "success":
                issues.append("run_metadata status=success despite degraded stages.")

    if comment_manifest and docx_manifest:
        c_added = int(comment_manifest.get("comments_added", 0) or 0)
        d_added = int(docx_manifest.get("comments_added", 0) or 0)
        if c_added != d_added:
            issues.append(f"Comment manifest mismatch: manuscript={c_added}, docx_manifest={d_added}.")
        targets = comment_manifest.get("comment_targets", [])
        if isinstance(targets, list) and c_added > 0 and len(targets) == 0:
            issues.append("comments_added > 0 but comment_targets is empty.")
        if c_added == 0:
            issues.append("No comments were added; deep-run should produce actionable comments.")

    if commented_validation:
        if not bool(commented_validation.get("comments_attached", False)):
            issues.append("commented_docx_validation indicates comments_attached=false.")
        if bool(commented_validation.get("silent_noop_suspected", False)):
            issues.append("commented_docx_validation flagged silent_noop_suspected=true.")
        val_count = int(commented_validation.get("new_ai_reviewer_comments_added_count", 0) or 0)
        man_count = int(comment_manifest.get("new_ai_reviewer_comments_added_count", 0) or 0) if comment_manifest else 0
        if man_count and val_count and man_count != val_count:
            issues.append(
                f"new_ai_reviewer_comments_added_count mismatch: validation={val_count}, manifest={man_count}."
            )

    debug_text = _read_text(run_dir / "debug.log", issues, "debug.log")
    if debug_text:
        if "code=empty_response" in debug_text.lower():
            warning_count = int(run_meta.get("warnings_count", 0) or 0) if run_meta else 0
            if warning_count == 0:
                issues.append("debug.log shows EMPTY_RESPONSE failures but warnings_count is 0.")
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
