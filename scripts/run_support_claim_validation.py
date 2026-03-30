from __future__ import annotations

import json
from pathlib import Path

from ai_reviewer.ingest.loaders import parse_file
from ai_reviewer.projects.store import ProjectStore
from ai_reviewer.review.verification import (
    build_assertion_review_md,
    build_citation_accuracy_report_md,
    build_citation_verification_ledger,
    build_claim_to_citation_map,
    build_format_compliance_report,
    build_support_ingest_report,
    build_support_relevance_report_md,
    enrich_assertion_ledger,
    extract_assertion_ledger,
    filter_support_docs_for_grounding,
    internal_consistency_checks,
)


APPROVED_PROJECTS = [
    "20260325163524_test-existingphactorpaper",
    "20260327051312_miniaturization_d2b",
]


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_md(path: Path, title: str, rows: dict) -> None:
    lines = [f"# {title}", ""]
    for key, value in rows.items():
        lines.append(f"## {key}")
        if isinstance(value, list):
            if value:
                lines.extend(f"- {item}" for item in value)
            else:
                lines.append("- None")
        elif isinstance(value, dict):
            lines.append("```json")
            lines.append(json.dumps(value, indent=2))
            lines.append("```")
        else:
            lines.append(str(value))
        lines.append("")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    store = ProjectStore(repo_root / "projects")
    audit_root = repo_root / "audits" / "support_claim_validation"
    audit_root.mkdir(parents=True, exist_ok=True)
    summary: list[dict] = []

    for project_id in APPROVED_PROJECTS:
        pdir, meta = store.get_project(project_id)
        manuscript = next((m for m in meta.materials if m.category in {"manuscript_draft", "published_paper"}), None)
        if manuscript is None:
            raise RuntimeError(f"No manuscript material found for {project_id}")
        manuscript_path = store.material_path(pdir, manuscript)
        manuscript_doc = parse_file(manuscript_path)

        support_docs = []
        parse_failures = []
        for material in meta.materials:
            support_path = store.material_path(pdir, material)
            if "other" not in support_path.parts:
                continue
            try:
                support_docs.append(parse_file(support_path))
            except Exception as exc:
                parse_failures.append({"path": str(support_path), "error": str(exc)})

        project_out = audit_root / project_id
        project_out.mkdir(parents=True, exist_ok=True)

        support_ingest = build_support_ingest_report(manuscript_doc, support_docs, parse_failures=parse_failures)
        selected_support_docs, _, _ = filter_support_docs_for_grounding(manuscript_doc, support_docs)
        consistency = internal_consistency_checks(manuscript_doc)
        assertion_ledger = extract_assertion_ledger(manuscript_doc)
        claim_map = build_claim_to_citation_map(manuscript_doc, assertion_ledger)
        citation_ledger = build_citation_verification_ledger(manuscript_doc, assertion_ledger, selected_support_docs, pdir)
        enriched = enrich_assertion_ledger(assertion_ledger, claim_map, citation_ledger, selected_support_docs, manuscript_doc.cleaned_text)
        assertion_ledger = enriched["assertion_ledger"]
        support_usage = enriched["support_usage_ledger"]
        claim_summary = enriched["claim_verification_summary"]
        compliance = build_format_compliance_report(manuscript_doc)

        _write_json(project_out / "support_ingest_report.json", support_ingest)
        (project_out / "support_relevance_report.md").write_text(build_support_relevance_report_md(support_ingest), encoding="utf-8")
        _write_json(project_out / "internal_consistency_checks.json", consistency)
        _write_json(project_out / "assertion_ledger.json", assertion_ledger)
        (project_out / "assertion_review.md").write_text(build_assertion_review_md(assertion_ledger), encoding="utf-8")
        _write_json(project_out / "claim_to_citation_map.json", claim_map)
        _write_json(project_out / "citation_verification_ledger.json", citation_ledger)
        (project_out / "citation_accuracy_report.md").write_text(build_citation_accuracy_report_md(citation_ledger), encoding="utf-8")
        _write_json(project_out / "support_usage_ledger.json", support_usage)
        _write_json(project_out / "claim_verification_summary.json", claim_summary)
        _write_json(project_out / "format_compliance_report.json", compliance)

        project_summary = {
            "project_id": project_id,
            "support_docs_available": support_ingest.get("available_support_docs", 0),
            "support_docs_selected": support_ingest.get("selected_support_docs", 0),
            "claims_extracted": assertion_ledger.get("claim_count", 0),
            "claims_checked": claim_summary.get("claims_checked", 0),
            "likely_overstated": claim_summary.get("likely_overstated", 0),
            "references_extracted": citation_ledger.get("reference_count", 0),
            "references_linked_to_claims": citation_ledger.get("linked_reference_count", 0),
            "compliance_findings": compliance.get("finding_count", 0),
        }
        _write_md(project_out / "summary.md", "Support / Claim / Citation Validation Summary", project_summary)
        summary.append(project_summary)

    _write_json(audit_root / "summary.json", {"projects": summary})
    _write_md(
        audit_root / "summary.md",
        "Support / Claim / Citation Validation",
        {
            "projects": summary,
            "note": "This audit validates support-ingest, claim extraction, citation linkage, and compliance artifacts directly on the approved project materials.",
        },
    )


if __name__ == "__main__":
    main()
