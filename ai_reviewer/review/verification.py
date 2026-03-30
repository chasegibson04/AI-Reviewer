from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ai_reviewer.ingest.types import ParsedDocument
from ai_reviewer.review.citation_fetcher import extract_doi, parse_references


_HEADING_RE = re.compile(
    r"^\s{0,3}(#+\s+)?(abstract|introduction|background|methods?|experimental|results?|discussion|conclusions?|references)\b",
    re.IGNORECASE,
)
_NUMERIC_CITATION_RE = re.compile(r"\[(\d{1,3})\]")
_AUTHOR_YEAR_CITATION_RE = re.compile(r"\(([A-Z][A-Za-z'`-]+(?:\s+et al\.)?,?\s+\d{4}[a-z]?)\)")
_OVERCLAIM_MARKERS = [
    "first",
    "all ",
    "every ",
    "always",
    "never",
    "prove",
    "proves",
    "clearly shows",
    "clearly demonstrate",
    "demonstrates",
    "superior",
    "outperforms",
    "best",
    "novel",
]
_RESULT_MARKERS = ["yield", "result", "results", "performed", "improved", "decreased", "increased", "produced"]
_METHOD_MARKERS = ["we used", "we performed", "was added", "were added", "reaction", "procedure", "assay", "protocol"]
_INTERPRETATION_MARKERS = ["suggest", "indicate", "consistent with", "therefore", "thus", "implies"]


def _safe_name(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _simple_keywords(text: str, top_n: int = 24) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", (text or "").lower())
    stop = {
        "with",
        "that",
        "this",
        "from",
        "were",
        "their",
        "which",
        "using",
        "into",
        "between",
        "results",
        "methods",
        "introduction",
        "table",
        "figure",
        "analysis",
        "paper",
        "study",
        "these",
        "those",
    }
    freq: dict[str, int] = {}
    for word in words:
        if word in stop:
            continue
        freq[word] = freq.get(word, 0) + 1
    return [key for key, _ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:top_n]]


def token_overlap(a: str, b: str) -> float:
    sa = set(_simple_keywords(a, top_n=32))
    sb = set(_simple_keywords(b, top_n=32))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / float(len(sa | sb))


def support_overlap_score(manuscript_text: str, support_text: str) -> float:
    return token_overlap((manuscript_text or "")[:40000], (support_text or "")[:40000])


def support_verification_entry(
    source: str,
    score: float,
    selected: bool,
    reason: str | None = None,
    provenance: str = "project_support_material",
) -> dict[str, Any]:
    labels = [
        "support_relationship_plausible" if selected else "support_relationship_not_verified",
        "internal_consistency_check_only",
        "needs_human_verification",
    ]
    return {
        "source": source,
        "score": round(score, 4),
        "selected": selected,
        "reason": reason,
        "verification": {
            "labels": labels,
            "verification_scope": "internal_consistency_check_only",
            "selection_basis": "lexical_overlap_only",
            "provenance": provenance,
        },
    }


def filter_support_docs_for_grounding(
    manuscript: ParsedDocument,
    support_docs: list[ParsedDocument],
) -> tuple[list[ParsedDocument], list[dict[str, Any]], list[dict[str, Any]]]:
    selected_docs: list[ParsedDocument] = []
    skipped: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    manuscript_text = (manuscript.cleaned_text or "")[:40000]
    for sdoc in support_docs:
        name = sdoc.source_path.name.lower()
        if any(marker in name for marker in ["openai gym", "gym_", "biogpt"]):
            skipped.append(support_verification_entry(sdoc.source_path.name, 0.0, selected=False, reason="blocked_filename_marker"))
            continue
        score = support_overlap_score(manuscript_text, (sdoc.cleaned_text or "")[:40000])
        if score >= 0.95:
            skipped.append(support_verification_entry(sdoc.source_path.name, score, selected=False, reason="manuscript_like_duplicate"))
            continue
        if score < 0.04:
            skipped.append(support_verification_entry(sdoc.source_path.name, score, selected=False, reason="low_overlap"))
            continue
        selected_docs.append(sdoc)
        selected.append(support_verification_entry(sdoc.source_path.name, score, selected=True, reason=None))
    return selected_docs, skipped, selected


def extract_named_section(text: str, heading_pattern: str, fallback_chars: int = 0) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    capture = False
    captured: list[str] = []
    pattern = re.compile(heading_pattern, re.IGNORECASE)
    for line in lines:
        stripped = line.strip()
        if not capture and pattern.match(stripped):
            capture = True
            continue
        if capture:
            if _HEADING_RE.match(stripped):
                break
            captured.append(stripped)
    section_text = "\n".join([ln for ln in captured if ln]).strip()
    if section_text:
        return section_text
    if fallback_chars > 0:
        return text[:fallback_chars].strip()
    return ""


def internal_consistency_checks_from_text(text: str) -> dict[str, Any]:
    abstract_text = extract_named_section(text, r"^\s*abstract\b", fallback_chars=2200)
    conclusion_text = extract_named_section(text, r"^\s*conclusions?\b", fallback_chars=0)
    if not conclusion_text:
        conclusion_text = extract_named_section(text, r"^\s*discussion\b", fallback_chars=0)
    body_text = text
    if abstract_text and abstract_text in body_text:
        body_text = body_text.replace(abstract_text, "", 1)
    if conclusion_text and conclusion_text in body_text:
        body_text = body_text.replace(conclusion_text, "", 1)
    findings: list[dict[str, Any]] = []
    broad_markers = ["always", "never", "all ", "every ", "proves", "clearly demonstrates"]
    abstract_low = abstract_text.lower()
    body_low = body_text.lower()
    conclusion_low = conclusion_text.lower()
    if abstract_text and any(marker in abstract_low for marker in broad_markers) and not any(marker in body_low for marker in broad_markers):
        findings.append(
            {
                "label": "abstract_scope_broader_than_body",
                "severity": "medium",
                "details": "Opening summary uses broader certainty language than the body text.",
            }
        )
    if conclusion_text and any(marker in conclusion_low for marker in broad_markers) and not any(marker in body_low for marker in broad_markers):
        findings.append(
            {
                "label": "conclusion_scope_broader_than_body",
                "severity": "medium",
                "details": "Conclusion/discussion appears broader than the body evidence language.",
            }
        )
    return {
        "labels": ["internal_consistency_check_only"],
        "verification_scope": "internal_consistency_check_only",
        "abstract_present": bool(abstract_text),
        "conclusion_present": bool(conclusion_text),
        "finding_count": len(findings),
        "findings": findings,
        "needs_human_verification": bool(findings),
    }


def internal_consistency_checks(doc: ParsedDocument) -> dict[str, Any]:
    return internal_consistency_checks_from_text(doc.cleaned_text or "")


def _iter_section_sentences(text: str) -> list[dict[str, str]]:
    current_section = "front_matter"
    current_block: list[str] = []
    blocks: list[tuple[str, str]] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            if current_block:
                blocks.append((current_section, " ".join(current_block).strip()))
                current_block = []
            continue
        heading = _HEADING_RE.match(line)
        if heading:
            if current_block:
                blocks.append((current_section, " ".join(current_block).strip()))
                current_block = []
            current_section = heading.group(2).lower()
            continue
        current_block.append(line)
    if current_block:
        blocks.append((current_section, " ".join(current_block).strip()))

    out: list[dict[str, str]] = []
    for section, block in blocks:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", block) if s.strip()]
        for sentence in sentences:
            out.append({"section": section, "sentence": sentence, "paragraph": block[:1000]})
    return out


def _claim_type_for_sentence(section: str, sentence: str, citation_markers: list[str]) -> str:
    low = sentence.lower()
    if section.startswith("abstract"):
        return "abstract_claim"
    if section.startswith("conclusion") or section.startswith("discussion"):
        return "interpretation_claim"
    if citation_markers:
        return "citation_dependent_claim"
    if any(marker in low for marker in _METHOD_MARKERS):
        return "methods_claim"
    if any(marker in low for marker in _RESULT_MARKERS):
        return "result_claim"
    if any(marker in low for marker in _INTERPRETATION_MARKERS):
        return "interpretation_claim"
    if any(marker in low for marker in _OVERCLAIM_MARKERS):
        return "novelty_or_scope_claim"
    return "background_claim"


def _clean_sentence_for_claims(sentence: str) -> str:
    cleaned = sentence or ""
    cleaned = re.sub(r"\*\*==> picture .*? <==\*\*", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"Received:?.*?Accepted:?.*?Published online:?.*?(Check for updates)?", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"Read Online.*?Supporting Information", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"https?://\S+", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bpubs\.acs\.org/\S+\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bnature synthesis\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bArticle\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r">\s*\d+\w*\s+[A-Z][^.]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _priority_for_claim(section: str, sentence: str, claim_type: str, citation_markers: list[str]) -> str:
    low = sentence.lower()
    high = (
        section.startswith("abstract")
        or section.startswith("conclusion")
        or claim_type in {"result_claim", "interpretation_claim", "novelty_or_scope_claim"}
        or bool(citation_markers)
        or any(marker in low for marker in _OVERCLAIM_MARKERS)
    )
    return "high" if high else "medium"


def extract_assertion_ledger(doc: ParsedDocument, max_claims: int = 80) -> dict[str, Any]:
    refs = parse_references(doc.raw_text or doc.cleaned_text, max_refs=500)
    claims: list[dict[str, Any]] = []
    for idx, row in enumerate(_iter_section_sentences(doc.cleaned_text), start=1):
        sentence = _clean_sentence_for_claims(row["sentence"])
        if len(sentence) < 60:
            continue
        section_low = row["section"].lower()
        if section_low in {"references", "reference"}:
            continue
        if section_low == "front_matter" and ("##" in sentence or sentence.count("**") >= 4):
            continue
        if re.search(r"\b(department|university|present address|corresponding author|published online|received:?|accepted:?|check for updates)\b", sentence, re.IGNORECASE):
            continue
        citation_markers = [f"[{m}]" for m in _NUMERIC_CITATION_RE.findall(sentence)]
        citation_markers.extend(_AUTHOR_YEAR_CITATION_RE.findall(sentence))
        low = sentence.lower()
        if "supporting information" in low or "author contributions" in low or "acknowledgements" in low:
            continue
        if not (
            row["section"].startswith(("abstract", "results", "discussion", "conclusion", "introduction"))
            or (section_low == "front_matter" and any(marker in low for marker in _RESULT_MARKERS + _INTERPRETATION_MARKERS + _OVERCLAIM_MARKERS))
            or citation_markers
            or any(marker in low for marker in _OVERCLAIM_MARKERS + _RESULT_MARKERS + _INTERPRETATION_MARKERS)
        ):
            continue
        claim_type = _claim_type_for_sentence(row["section"], sentence, citation_markers)
        if section_low == "front_matter" and claim_type == "background_claim":
            claim_type = "abstract_claim"
        claims.append(
            {
                "claim_id": f"CLAIM-{idx:03d}",
                "section": row["section"],
                "claim_text": sentence[:600],
                "paragraph_excerpt": row["paragraph"][:900],
                "claim_type": claim_type,
                "priority": _priority_for_claim(row["section"], sentence, claim_type, citation_markers),
                "citation_markers": citation_markers,
                "trigger_terms": [marker for marker in _OVERCLAIM_MARKERS if marker in low],
                "reference_indices": [int(x) for x in _NUMERIC_CITATION_RE.findall(sentence) if x.isdigit() and int(x) <= len(refs)],
                "status": "unresolved_needs_human_review",
                "verification_labels": ["internal_consistency_check_only", "needs_human_verification"],
            }
        )
        if len(claims) >= max_claims:
            break
    return {
        "claim_count": len(claims),
        "claims": claims,
        "reference_count": len(refs),
        "verification_policy": {
            "internally_supported": "Claim wording appears consistent with other manuscript text or repeated manuscript evidence.",
            "cited_support_plausible": "Nearby citation or relevant support paper exists, but direct claim support was not proven.",
            "cited_support_verified": "Reserved for cases where local evidence alignment is strong and explicitly traceable.",
            "citation_exists_but_support_not_verified": "Reference appears to exist, but support for the specific claim was not established.",
            "likely_overstated": "Claim language appears stronger than the manuscript or supplied support warrants.",
            "unresolved_needs_human_review": "Manual review is still needed.",
        },
    }


def build_support_ingest_report(
    manuscript: ParsedDocument,
    support_docs: list[ParsedDocument],
    parse_failures: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    docs: list[dict[str, Any]] = []
    selected = 0
    skipped = 0
    for sdoc in support_docs:
        score = support_overlap_score(manuscript.cleaned_text, sdoc.cleaned_text)
        reason = None
        status = "selected"
        if score >= 0.95:
            status = "skipped"
            reason = "manuscript_like_duplicate"
            skipped += 1
        elif score < 0.04:
            status = "skipped"
            reason = "low_overlap"
            skipped += 1
        else:
            selected += 1
        docs.append(
            {
                "source": sdoc.source_path.name,
                "path": str(sdoc.source_path),
                "parse_status": "parsed",
                "score": round(score, 4),
                "status": status,
                "reason": reason,
                "heading_count": len(sdoc.headings),
                "keyword_inventory": _simple_keywords(sdoc.cleaned_text, top_n=12),
                "document_type": sdoc.document_type,
            }
        )
    for failure in parse_failures or []:
        docs.append(
            {
                "source": Path(failure.get("path", "unknown")).name,
                "path": failure.get("path", ""),
                "parse_status": "failed",
                "status": "skipped",
                "reason": failure.get("error", "parse_failed"),
            }
        )
    return {
        "available_support_docs": len(docs),
        "parsed_support_docs": len([d for d in docs if d.get("parse_status") == "parsed"]),
        "selected_support_docs": selected,
        "skipped_support_docs": skipped + len(parse_failures or []),
        "documents": docs,
        "policy": {
            "selection_basis": "lexical_overlap_plus_duplicate_blocking",
            "goal": "Support documents provide contextual evidence cues without replacing manuscript-specific judgment.",
        },
    }


def _local_support_presence(reference: str, support_docs: list[ParsedDocument]) -> tuple[bool, str | None, float]:
    best_name = None
    best_score = 0.0
    for sdoc in support_docs:
        score = token_overlap(reference, f"{sdoc.source_path.name} {(sdoc.cleaned_text or '')[:2500]}")
        if score > best_score:
            best_score = score
            best_name = sdoc.source_path.name
    return best_score >= 0.12, best_name, round(best_score, 4)


def build_claim_to_citation_map(doc: ParsedDocument, assertion_ledger: dict[str, Any]) -> dict[str, Any]:
    refs = parse_references(doc.raw_text or doc.cleaned_text, max_refs=500)
    rows: list[dict[str, Any]] = []
    for claim in assertion_ledger.get("claims", []):
        linked: list[dict[str, Any]] = []
        for idx in claim.get("reference_indices", []):
            if 1 <= idx <= len(refs):
                linked.append({"reference_index": idx, "reference": refs[idx - 1]})
        rows.append(
            {
                "claim_id": claim.get("claim_id"),
                "claim_text": claim.get("claim_text"),
                "section": claim.get("section"),
                "citation_markers": claim.get("citation_markers", []),
                "linked_references": linked,
            }
        )
    return {"claim_links": rows, "reference_count": len(refs)}


def load_citation_fetch_report(start_dir: Path) -> dict[str, Any] | None:
    cur = start_dir
    checked: set[Path] = set()
    for candidate_root in [cur, *cur.parents]:
        if candidate_root in checked:
            continue
        checked.add(candidate_root)
        candidate = candidate_root / "artifacts" / "citation_fetch_report.json"
        if candidate.exists():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                return None
    for candidate_root in [cur, *cur.parents]:
        runs_dir = candidate_root / "runs"
        if not runs_dir.exists():
            continue
        reports = sorted(runs_dir.glob("*/artifacts/citation_fetch_report.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for report_path in reports[:5]:
            try:
                return json.loads(report_path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return None


def build_citation_verification_ledger(
    doc: ParsedDocument,
    assertion_ledger: dict[str, Any],
    support_docs: list[ParsedDocument],
    run_dir: Path,
) -> dict[str, Any]:
    refs = parse_references(doc.raw_text or doc.cleaned_text, max_refs=500)
    fetch_report = load_citation_fetch_report(run_dir)
    fetch_entries = fetch_report.get("entries", []) if isinstance(fetch_report, dict) else []
    fetch_by_doi = {
        str(entry.get("doi", "")).lower(): entry
        for entry in fetch_entries
        if str(entry.get("doi", "")).strip()
    }
    ledger: list[dict[str, Any]] = []
    claims_by_ref: dict[int, list[str]] = {}
    for claim in assertion_ledger.get("claims", []):
        for idx in claim.get("reference_indices", []):
            claims_by_ref.setdefault(int(idx), []).append(str(claim.get("claim_id")))
    for idx, reference in enumerate(refs, start=1):
        doi = extract_doi(reference)
        fetch_entry = fetch_by_doi.get((doi or "").lower()) if doi else None
        local_present, local_name, local_score = _local_support_presence(reference, support_docs)
        labels = ["reference_extracted"]
        if doi or fetch_entry:
            labels.append("citation_exists")
        if fetch_entry and fetch_entry.get("verification", {}).get("metadata_match_likely"):
            labels.append("metadata_match_likely")
        elif doi:
            labels.append("metadata_match_likely")
        if local_present:
            labels.append("source_present_in_materials_other")
            labels.append("cited_paper_plausibly_relevant")
        if fetch_entry and str(fetch_entry.get("status", "")).startswith("downloaded:"):
            labels.append("source_fetched_via_oa")
        if claims_by_ref.get(idx):
            labels.append("linked_to_manuscript_claim")
        labels.append("support_not_verified")
        labels.append("needs_human_verification")
        ledger.append(
            {
                "reference_index": idx,
                "reference": reference,
                "doi": doi,
                "claim_ids": claims_by_ref.get(idx, []),
                "local_source_present": local_present,
                "local_source_name": local_name,
                "local_relevance_score": local_score,
                "fetch_status": fetch_entry.get("status") if fetch_entry else None,
                "fetch_verification": fetch_entry.get("verification") if fetch_entry else None,
                "verification_labels": labels,
                "support_judgment": (
                    "citation_exists_but_support_not_verified"
                    if "citation_exists" in labels
                    else "unresolved_needs_human_review"
                ),
            }
        )
    return {
        "reference_count": len(refs),
        "linked_reference_count": len([row for row in ledger if row.get("claim_ids")]),
        "entries": ledger,
        "query_policy": (
            fetch_report.get("query_policy") if isinstance(fetch_report, dict) else {
                "raw_manuscript_text_allowed": False,
                "long_excerpt_allowed": False,
                "query_audit_mode": "type_and_length_only",
            }
        ),
    }


def enrich_assertion_ledger(
    assertion_ledger: dict[str, Any],
    citation_map: dict[str, Any],
    citation_ledger: dict[str, Any],
    support_docs: list[ParsedDocument],
    manuscript_text: str,
) -> dict[str, Any]:
    citation_by_index = {int(entry["reference_index"]): entry for entry in citation_ledger.get("entries", [])}
    claim_links = {row.get("claim_id"): row for row in citation_map.get("claim_links", [])}
    usage_rows: list[dict[str, Any]] = []
    checked = 0
    likely_overstated = 0
    for claim in assertion_ledger.get("claims", []):
        claim_text = str(claim.get("claim_text", ""))
        section = str(claim.get("section", ""))
        low = claim_text.lower()
        refs = claim_links.get(claim.get("claim_id"), {}).get("linked_references", [])
        top_support: list[dict[str, Any]] = []
        for sdoc in support_docs:
            score = token_overlap(claim_text, sdoc.cleaned_text[:8000])
            if score >= 0.08:
                top_support.append({"source": sdoc.source_path.name, "score": round(score, 4)})
        top_support = sorted(top_support, key=lambda row: row["score"], reverse=True)[:3]
        labels = ["statement_checked_only_internally"]
        status = "internally_supported"
        if refs:
            labels.append("citation_link_present")
            status = "citation_exists_but_support_not_verified"
        if top_support:
            labels.append("support_relationship_plausible")
            if status == "internally_supported":
                status = "cited_support_plausible"
        if any(marker in low for marker in _OVERCLAIM_MARKERS) and section.startswith(("abstract", "discussion", "conclusion")):
            labels.append("likely_overstated")
            status = "likely_overstated"
            likely_overstated += 1
        if refs and all(citation_by_index.get(int(ref["reference_index"]), {}).get("local_source_present") for ref in refs if isinstance(ref, dict)):
            labels.append("cited_source_retrieved_locally")
        claim["verification_labels"] = labels
        claim["status"] = status
        claim["support_sources"] = top_support
        claim["linked_references"] = refs
        checked += 1
        for support_row in top_support:
            usage_rows.append(
                {
                    "claim_id": claim.get("claim_id"),
                    "claim_text": claim_text[:220],
                    "source": support_row["source"],
                    "score": support_row["score"],
                    "usage_type": "claim_plausibility_context",
                    "status": status,
                }
            )
    assertion_ledger["claims_checked"] = checked
    assertion_ledger["likely_overstated_count"] = likely_overstated
    return {
        "assertion_ledger": assertion_ledger,
        "support_usage_ledger": {
            "usage_count": len(usage_rows),
            "entries": usage_rows,
            "policy": {
                "meaning": "Support material may inform plausibility/context checks but does not override manuscript-grounded judgment.",
                "contamination_control": "Every usage row is tied back to a manuscript claim_id.",
            },
        },
        "claim_verification_summary": {
            "claim_count": len(assertion_ledger.get("claims", [])),
            "claims_checked": checked,
            "internally_supported": len([c for c in assertion_ledger.get("claims", []) if c.get("status") == "internally_supported"]),
            "cited_support_plausible": len([c for c in assertion_ledger.get("claims", []) if c.get("status") == "cited_support_plausible"]),
            "citation_exists_but_support_not_verified": len([c for c in assertion_ledger.get("claims", []) if c.get("status") == "citation_exists_but_support_not_verified"]),
            "likely_overstated": likely_overstated,
            "unresolved_needs_human_review": len([c for c in assertion_ledger.get("claims", []) if c.get("status") == "unresolved_needs_human_review"]),
        },
    }


def build_support_relevance_report_md(support_ingest: dict[str, Any]) -> str:
    lines = ["# Support Relevance Report", ""]
    lines.append(f"- Available support docs: {support_ingest.get('available_support_docs', 0)}")
    lines.append(f"- Parsed support docs: {support_ingest.get('parsed_support_docs', 0)}")
    lines.append(f"- Selected support docs: {support_ingest.get('selected_support_docs', 0)}")
    lines.append("")
    for item in support_ingest.get("documents", []):
        lines.append(f"## {item.get('source', 'unknown')}")
        lines.append(f"- parse_status: {item.get('parse_status')}")
        lines.append(f"- status: {item.get('status')}")
        if item.get("score") is not None:
            lines.append(f"- score: {item.get('score')}")
        if item.get("reason"):
            lines.append(f"- reason: {item.get('reason')}")
        if item.get("keyword_inventory"):
            lines.append(f"- keywords: {', '.join(item.get('keyword_inventory', [])[:10])}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_assertion_review_md(assertion_ledger: dict[str, Any]) -> str:
    lines = ["# Assertion Review", ""]
    for claim in assertion_ledger.get("claims", [])[:60]:
        lines.append(f"## {claim.get('claim_id')}")
        lines.append(f"- section: {claim.get('section')}")
        lines.append(f"- type: {claim.get('claim_type')}")
        lines.append(f"- priority: {claim.get('priority')}")
        lines.append(f"- status: {claim.get('status')}")
        lines.append(f"- claim: {claim.get('claim_text')}")
        if claim.get("linked_references"):
            lines.append(f"- linked_references: {len(claim.get('linked_references', []))}")
        if claim.get("support_sources"):
            rendered = ", ".join(f"{row['source']} ({row['score']})" for row in claim.get("support_sources", []))
            lines.append(f"- support_sources: {rendered}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_citation_accuracy_report_md(citation_ledger: dict[str, Any]) -> str:
    lines = ["# Citation Accuracy Report", ""]
    for entry in citation_ledger.get("entries", [])[:100]:
        lines.append(f"## Reference {entry.get('reference_index')}")
        lines.append(f"- support_judgment: {entry.get('support_judgment')}")
        labels = entry.get("verification_labels", [])
        lines.append(f"- labels: {', '.join(labels)}")
        if entry.get("doi"):
            lines.append(f"- doi: {entry.get('doi')}")
        if entry.get("local_source_name"):
            lines.append(f"- local_source_name: {entry.get('local_source_name')}")
        lines.append(f"- reference: {entry.get('reference')}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_format_compliance_report(
    manuscript: ParsedDocument,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    constraints = constraints or {"enabled": False, "priorities": [], "required_reporting_items": []}
    text = manuscript.cleaned_text or ""
    low = text.lower()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = lines[0] if lines else ""
    findings: list[dict[str, Any]] = []

    # 1. Structural Completeness
    required_sections = ["abstract", "introduction", "methods", "results", "discussion", "references"]
    for section in required_sections:
        found = False
        if section == "methods":
            if any(k in low for k in ["methods", "experimental", "procedure", "materials and methods"]):
                found = True
        elif section == "abstract":
            if "abstract" in low or (len(lines) > 2 and len(lines[1].split()) > 40):
                 found = True
        elif section == "references":
            if "references" in low or "bibliography" in low or re.search(r"\[1\]|1\.\s+[A-Z]", text[-5000:]):
                found = True
        else:
            if section in low:
                found = True
        if not found:
            findings.append({
                "severity": "medium",
                "category": "required_section",
                "message": f"Required section likely missing or not clearly labeled: {section.capitalize()}"
            })

    # 2. Title and Abstract Heuristics
    title_words = len(title.split())
    if title_words > 25:
        findings.append({
            "severity": "low",
            "category": "title_length",
            "message": f"Title is exceptionally long ({title_words} words). Standard limit is usually <20."
        })
    if "abstract" in low:
        # Simple heuristic for abstract length: look for text between Abstract and Intro
        abs_match = re.search(r"abstract\b(.*?)(introduction|background|methods|results|#|\n\n\n)", low, re.S)
        if abs_match:
            abs_text = abs_match.group(1).strip()
            abs_words = len(abs_text.split())
            if abs_words > 450:
                 findings.append({
                    "severity": "medium",
                    "category": "formatting",
                    "message": f"Abstract appears too long ({abs_words} words). Standard limit is usually 250-300."
                })

    # 3. Context Pack Constraints
    for word in constraints.get("forbidden_title_words", []) or []:
        if word and word.lower() in title.lower():
            findings.append({"severity": "high", "category": "title_rule", "message": f"Title contains forbidden word from context pack: '{word}'."})
    max_words = constraints.get("max_word_count")
    if isinstance(max_words, int) and max_words > 0:
        wc = len(re.findall(r"\w+", text))
        if wc > max_words:
            findings.append({"severity": "medium", "category": "word_count", "message": f"Manuscript appears to exceed context-pack word limit ({wc} > {max_words})."})
    for req in constraints.get("required_reporting_items", []) or []:
        key = req.replace("_statement", "").replace("_", " ")
        if key not in low:
            findings.append({"severity": "medium", "category": "required_reporting", "message": f"Context-pack required item may be missing: {req}."})

    # 4. Standard Reporting Items
    for phrase, label in [
        ("data availability", "data_availability"),
        ("code availability", "code_availability"),
        ("limitations", "limitations_statement"),
        ("conflict of interest", "conflict_of_interest"),
        ("competing interests", "competing_interests"),
    ]:
        if phrase not in low:
            findings.append({"severity": "low", "category": "reporting_item", "message": f"Potentially missing reporting item: {label}."})

    # 5. Citation Numbering Heuristics
    if "[" in text and "1" in text:
        citations = re.findall(r"\[(\d{1,3})\]", text)
        if citations:
            nums = sorted(list(set(int(n) for n in citations)))
            if nums and nums[0] > 1 and nums[0] < 10: # Only flag if it's a small offset
                findings.append({
                    "severity": "low",
                    "category": "citation",
                    "message": f"First citation index is [{nums[0]}], expected [1]."
                })
            # Check for large gaps in numbering
            for i in range(len(nums) - 1):
                if nums[i+1] - nums[i] > 15:
                    findings.append({
                        "severity": "low",
                        "category": "citation",
                        "message": f"Large gap in citation numbering detected between [{nums[i]}] and [{nums[i+1]}]. Verify completeness."
                    })

    return {
        "enabled": True,
        "context_pack_enabled": bool(constraints.get("enabled")),
        "applied_priorities": constraints.get("priorities", []),
        "finding_count": len(findings),
        "findings": findings,
        "policy": {
            "meaning": "Format/compliance checks are heuristic and do not replace manuscript-specific editorial review.",
        },
    }
