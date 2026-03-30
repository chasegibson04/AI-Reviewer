import json
from pathlib import Path

from ai_reviewer.ingest.loaders import parse_file
from ai_reviewer.review.verification import (
    build_citation_verification_ledger,
    build_claim_to_citation_map,
    build_format_compliance_report,
    build_support_ingest_report,
    enrich_assertion_ledger,
    extract_assertion_ledger,
)


def test_extract_assertion_ledger_and_claim_map(tmp_path: Path):
    manuscript = tmp_path / "paper.md"
    manuscript.write_text(
        "# Title\n\nAbstract\nThis work clearly demonstrates superior performance in all cases [1].\n\nResults\nWe increased yield under the tested conditions across the evaluated reaction set and documented the comparison explicitly.\n\nReferences\n1. Example ref. https://doi.org/10.1000/xyz123\n",
        encoding="utf-8",
    )
    doc = parse_file(manuscript)

    ledger = extract_assertion_ledger(doc)
    assert ledger["claim_count"] >= 2
    assert any(claim["priority"] == "high" for claim in ledger["claims"])

    claim_map = build_claim_to_citation_map(doc, ledger)
    assert any(row["linked_references"] for row in claim_map["claim_links"])


def test_citation_verification_distinguishes_existence_from_support(tmp_path: Path):
    manuscript = tmp_path / "paper.md"
    manuscript.write_text(
        "# Title\n\nAbstract\nThis work clearly demonstrates superior performance in all cases [1].\n\nReferences\n1. Example ref. https://doi.org/10.1000/xyz123\n",
        encoding="utf-8",
    )
    support = tmp_path / "support.md"
    support.write_text("# Support\n\nExample ref discusses related performance.", encoding="utf-8")
    doc = parse_file(manuscript)
    support_doc = parse_file(support)

    ledger = extract_assertion_ledger(doc)
    citation_ledger = build_citation_verification_ledger(doc, ledger, [support_doc], tmp_path)
    entry = citation_ledger["entries"][0]
    assert "citation_exists" in entry["verification_labels"]
    assert "support_not_verified" in entry["verification_labels"]
    assert entry["support_judgment"] == "citation_exists_but_support_not_verified"


def test_support_ingest_and_claim_enrichment_emit_usage_rows(tmp_path: Path):
    manuscript = tmp_path / "paper.md"
    manuscript.write_text(
        "# Title\n\nResults\nThe tested reaction increased yield substantially relative to baseline.\n",
        encoding="utf-8",
    )
    support = tmp_path / "support.md"
    support.write_text(
        "# Support\n\nThis support paper discusses the tested reaction and increased yield relative to baseline.\n",
        encoding="utf-8",
    )
    doc = parse_file(manuscript)
    support_doc = parse_file(support)

    report = build_support_ingest_report(doc, [support_doc])
    assert report["selected_support_docs"] == 1

    assertion_ledger = extract_assertion_ledger(doc)
    claim_map = build_claim_to_citation_map(doc, assertion_ledger)
    citation_ledger = build_citation_verification_ledger(doc, assertion_ledger, [support_doc], tmp_path)
    enriched = enrich_assertion_ledger(assertion_ledger, claim_map, citation_ledger, [support_doc], doc.cleaned_text)
    assert enriched["support_usage_ledger"]["usage_count"] >= 1
    assert enriched["claim_verification_summary"]["claims_checked"] >= 1


def test_format_compliance_report_surfaces_missing_items(tmp_path: Path):
    manuscript = tmp_path / "paper.md"
    manuscript.write_text("# Very Long Title With Too Many Words For A Short Journal Communication\n\nResults only.", encoding="utf-8")
    doc = parse_file(manuscript)
    payload = build_format_compliance_report(doc)
    messages = [row["message"] for row in payload["findings"]]
    assert any("Abstract heading was not detected" in message for message in messages)
    assert any("Discussion/conclusion heading was not detected" in message for message in messages)
