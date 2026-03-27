from __future__ import annotations

import json
from pathlib import Path

from ai_reviewer.review.schema import ReviewSchema
from ai_reviewer.review.docx_export import write_markdown_as_docx


def _format_duration_seconds(value: float | None) -> str | None:
    if value is None:
        return None
    v = float(value)
    # Ollama may return nanoseconds; normalize for human readability.
    if v > 1_000_000:
        v = v / 1_000_000_000.0
    return f"{v:.3f}s"


def render_markdown(
    review: ReviewSchema,
    source_metadata: dict | None = None,
    warnings: list[str] | None = None,
    run_metadata: dict | None = None,
) -> str:
    rec = review.recommendation
    debug = review.model_debug_metadata

    lines: list[str] = []
    lines.append("# AI-Reviewer Report")
    lines.append("")

    lines.append("## Document Metadata")
    merged_meta = dict(source_metadata or {})
    merged_meta.update(review.document_metadata)
    if merged_meta:
        for key, value in merged_meta.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- Not available")

    lines.append("")
    lines.append("## Executive Summary")
    lines.append(review.summary)
    lines.append("")
    lines.append("## Summary")
    lines.append(review.summary)

    lines.append("")
    lines.append("## Recommendation")
    lines.append(f"- Decision: **{rec.decision.upper()}**")
    lines.append(f"- Confidence: {review.confidence:.2f}")
    lines.append(f"- Rationale: {rec.rationale}")

    sections = [
        ("Major Strengths", review.major_strengths),
        ("Major Weaknesses", review.major_weaknesses),
        ("Novelty Concerns", review.novelty_concerns),
        ("Methods & Statistics Concerns", review.methodological_concerns + review.statistical_concerns),
        ("Writing & Organization Concerns", review.writing_organization_concerns),
        ("Figure/Table Concerns", review.figure_table_concerns),
        ("Citation/Reference Concerns", review.citation_reference_concerns),
        ("Reproducibility Concerns", review.reproducibility_concerns),
        ("Suggested Experiments/Analyses", review.suggested_experiments_analyses),
        ("Detailed Reviewer Comments", review.detailed_reviewer_comments),
    ]

    for title, items in sections:
        lines.append("")
        lines.append(f"## {title}")
        if items:
            for item in items:
                lines.append(f"- {item}")
        else:
            lines.append("- None provided")

    lines.append("")
    lines.append("## Section-Specific Comments")
    if review.section_specific_comments:
        for c in review.section_specific_comments:
            lines.append(f"- [{c.severity}] {c.section}: {c.comment}")
    else:
        lines.append("- None provided")

    lines.append("")
    lines.append("## Action Items For Author")
    if review.extracted_action_items:
        for action in review.extracted_action_items:
            lines.append(f"- ({action.priority}) {action.action}")
    else:
        lines.append("- None provided")

    lines.append("")
    lines.append("## Model/Debug Appendix")
    lines.append("## Model Debug Metadata")
    lines.append(f"- Provider: {debug.provider}")
    lines.append(f"- Model: {debug.model}")
    lines.append(f"- Temperature: {debug.temperature}")
    lines.append(f"- Parse Failures: {debug.parse_failures}")
    dur = _format_duration_seconds(debug.total_duration)
    if dur is not None:
        lines.append(f"- Total Duration: {dur}")
    if run_metadata and run_metadata.get("estimated_duration_seconds") is not None:
        est = _format_duration_seconds(run_metadata.get("estimated_duration_seconds"))
        basis = run_metadata.get("estimate_basis", {})
        basis_count = basis.get("count")
        if basis.get("scaled_by_chars_seconds") is not None:
            basis_note = f" (size-adjusted median from {basis_count} prior runs)" if basis_count else ""
        else:
            basis_note = f" (median of {basis_count} prior runs)" if basis_count else ""
        if est is not None:
            lines.append(f"- Estimated Duration: {est}{basis_note}")
    if debug.prompt_eval_count is not None:
        lines.append(f"- Prompt Eval Count: {debug.prompt_eval_count}")
    if debug.eval_count is not None:
        lines.append(f"- Eval Count: {debug.eval_count}")

    lines.append("")
    lines.append("## Warnings")
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- None")

    return "\n".join(lines).strip() + "\n"


def render_text(
    review: ReviewSchema,
    source_metadata: dict | None = None,
    warnings: list[str] | None = None,
    run_metadata: dict | None = None,
) -> str:
    return (
        render_markdown(review, source_metadata=source_metadata, warnings=warnings, run_metadata=run_metadata)
        .replace("# ", "")
        .replace("## ", "")
    )


def write_review_bundle(
    bundle_dir: Path,
    review: ReviewSchema,
    raw_response: str,
    repaired_response: str | None,
    warnings: list[str],
    source_metadata: dict | None = None,
    run_metadata: dict | None = None,
    keep_raw: bool = True,
    chunk_manifest: list[dict] | None = None,
    retrieval_manifest: list[dict] | None = None,
) -> None:
    reports_dir = bundle_dir / "reports"
    artifacts_dir = bundle_dir / "artifacts"
    raw_dir = bundle_dir / "raw"

    reports_dir.mkdir(exist_ok=True, parents=True)
    artifacts_dir.mkdir(exist_ok=True, parents=True)
    raw_dir.mkdir(exist_ok=True, parents=True)

    source_metadata = source_metadata or {}
    run_metadata = run_metadata or {}
    markdown = render_markdown(review, source_metadata=source_metadata, warnings=warnings, run_metadata=run_metadata)
    plain_text = render_text(review, source_metadata=source_metadata, warnings=warnings, run_metadata=run_metadata)

    (reports_dir / "review_report.md").write_text(markdown, encoding="utf-8")
    (reports_dir / "review_report.txt").write_text(plain_text, encoding="utf-8")
    write_markdown_as_docx(markdown, reports_dir / "review_report.docx")
    (reports_dir / "review.md").write_text(markdown, encoding="utf-8")
    (reports_dir / "review.txt").write_text(plain_text, encoding="utf-8")
    (reports_dir / "editor_summary.txt").write_text(
        f"Decision: {review.recommendation.decision.upper()}\n"
        f"Confidence: {review.confidence:.2f}\n"
        f"Summary: {review.summary[:1000]}\n",
        encoding="utf-8",
    )

    (artifacts_dir / "validated_review.json").write_text(review.model_dump_json(indent=2), encoding="utf-8")
    (artifacts_dir / "review.validated.json").write_text(review.model_dump_json(indent=2), encoding="utf-8")
    (artifacts_dir / "source_metadata.json").write_text(json.dumps(source_metadata, indent=2), encoding="utf-8")
    (artifacts_dir / "warnings.json").write_text(json.dumps(warnings, indent=2), encoding="utf-8")
    (artifacts_dir / "chunk_manifest.json").write_text(json.dumps(chunk_manifest or [], indent=2), encoding="utf-8")
    (artifacts_dir / "retrieval_manifest.json").write_text(json.dumps(retrieval_manifest or [], indent=2), encoding="utf-8")

    # Required top-level artifact naming for easier human scanning.
    (bundle_dir / "run_metadata.json").write_text(json.dumps(run_metadata, indent=2), encoding="utf-8")
    (bundle_dir / "source_metadata.json").write_text(json.dumps(source_metadata, indent=2), encoding="utf-8")
    (bundle_dir / "validated_review.json").write_text(review.model_dump_json(indent=2), encoding="utf-8")
    (bundle_dir / "review_report.md").write_text(markdown, encoding="utf-8")
    (bundle_dir / "review_report.txt").write_text(plain_text, encoding="utf-8")
    write_markdown_as_docx(markdown, bundle_dir / "review_report.docx")

    if keep_raw:
        (bundle_dir / "raw_model_response.txt").write_text(raw_response, encoding="utf-8")
        (raw_dir / "raw_model_response.txt").write_text(raw_response, encoding="utf-8")
        if repaired_response:
            (bundle_dir / "repaired_model_response.txt").write_text(repaired_response, encoding="utf-8")
            (raw_dir / "repaired_model_response.txt").write_text(repaired_response, encoding="utf-8")
