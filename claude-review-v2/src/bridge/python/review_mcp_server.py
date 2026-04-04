import json
import os
import re
import socket
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

try:
    from ai_reviewer.ingest.loaders import collect_paths as ai_collect_paths
    from ai_reviewer.ingest.loaders import parse_file as ai_parse_file
except Exception:
    ai_collect_paths = None
    ai_parse_file = None

SERVER_NAME = "manuscript-review-server"
SERVER_VERSION = "0.2.1"
BLOCKED_PROJECT_SNIPPETS = ("pampa", "horseshoe")
MANUSCRIPT_SUFFIXES = {".docx", ".pdf"}

TOOL_EVENT_LOG: list[dict[str, Any]] = []
NETWORK_EVENT_LOG: list[dict[str, Any]] = []
LAST_RENDER_TOOL_OFFSET = 0
LAST_RENDER_NETWORK_OFFSET = 0


@dataclass
class ParsedDoc:
    cleaned_text: str
    headings: list[str]
    page_count: int | None
    file_size_bytes: int
    parse_engine: str
    parse_warnings: list[str]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_blocked_name(name: str) -> bool:
    lowered = (name or "").strip().lower()
    return any(snippet in lowered for snippet in BLOCKED_PROJECT_SNIPPETS)


def _is_blocked_path(path: Path) -> bool:
    return any(_is_blocked_name(part) for part in path.parts)


def _log_tool_event(tool: str, status: str, meta: dict[str, Any] | None = None) -> None:
    TOOL_EVENT_LOG.append(
        {
            "timestamp": _now_iso(),
            "tool": tool,
            "status": status,
            "meta": meta or {},
        }
    )


def _log_network_event(action: str, host: str, protocol: str = "tcp", status: str = "ok") -> None:
    NETWORK_EVENT_LOG.append(
        {
            "timestamp": _now_iso(),
            "action": action,
            "host": host,
            "protocol": protocol,
            "status": status,
        }
    )


def _manuscripts_in_dir(cwd: Path) -> list[Path]:
    manuscripts: list[Path] = []
    for item in _collect_paths(cwd):
        if _is_blocked_path(item):
            continue
        if item.suffix.lower() in MANUSCRIPT_SUFFIXES:
            manuscripts.append(item)
    return sorted(set(manuscripts))


def _collect_paths(root: Path) -> list[Path]:
    if ai_collect_paths is not None:
        return ai_collect_paths(root)
    return [p for p in root.rglob("*") if p.is_file()]


def _parse_docx_fallback(path: Path) -> ParsedDoc:
    warnings: list[str] = []
    try:
        with zipfile.ZipFile(path) as zf:
            xml_data = zf.read("word/document.xml")
    except Exception as exc:
        return ParsedDoc(
            cleaned_text="",
            headings=[],
            page_count=None,
            file_size_bytes=path.stat().st_size,
            parse_engine="zip-docx-fallback",
            parse_warnings=[f"docx parse failed: {exc}"],
        )

    text_nodes = ET.fromstring(xml_data).findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
    parts = [(node.text or "").strip() for node in text_nodes if (node.text or "").strip()]
    text = "\n".join(parts)
    if not text:
        warnings.append("No text nodes found in DOCX XML.")
    return ParsedDoc(
        cleaned_text=text,
        headings=[],
        page_count=None,
        file_size_bytes=path.stat().st_size,
        parse_engine="zip-docx-fallback",
        parse_warnings=warnings,
    )


def _parse_pdf_fallback(path: Path) -> ParsedDoc:
    warnings = ["Using heuristic byte-level PDF fallback parser; install pypdf for better extraction."]
    raw = path.read_bytes()
    candidates = re.findall(rb"\((.{1,256}?)\)", raw, flags=re.DOTALL)
    parts = []
    for item in candidates:
        cleaned = item.replace(b"\\n", b" ").replace(b"\\r", b" ").replace(b"\\t", b" ")
        try:
            txt = cleaned.decode("utf-8", errors="ignore")
        except Exception:
            continue
        txt = re.sub(r"\s+", " ", txt).strip()
        if len(txt) >= 3:
            parts.append(txt)
    text = "\n".join(parts[:5000])
    if not text:
        warnings.append("No extractable text found in PDF bytes.")
    return ParsedDoc(
        cleaned_text=text,
        headings=[],
        page_count=None,
        file_size_bytes=path.stat().st_size,
        parse_engine="pdf-byte-fallback",
        parse_warnings=warnings,
    )


def _parse_manuscript(path: Path) -> ParsedDoc:
    if ai_parse_file is not None:
        parsed = ai_parse_file(path)
        return ParsedDoc(
            cleaned_text=parsed.cleaned_text,
            headings=list(parsed.headings),
            page_count=parsed.page_count,
            file_size_bytes=parsed.file_size_bytes,
            parse_engine=parsed.parse_engine,
            parse_warnings=list(parsed.parse_warnings),
        )
    if path.suffix.lower() == ".docx":
        return _parse_docx_fallback(path)
    if path.suffix.lower() == ".pdf":
        return _parse_pdf_fallback(path)
    raise ValueError(f"Unsupported manuscript type: {path.suffix}")


def _check_ollama() -> bool:
    try:
        with socket.create_connection(("localhost", 11434), timeout=1):
            _log_network_event("ollama_healthcheck", "localhost", status="ok")
            return True
    except Exception:
        _log_network_event("ollama_healthcheck", "localhost", status="fail")
        return False


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _clean_for_analysis(text: str) -> str:
    normalized = text.replace("\u00a0", " ").replace("\x00", " ")
    normalized = re.sub(r"[^\S\r\n]+", " ", normalized)
    normalized = re.sub(r"[\t\r]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _simple_section_map(content: str, headings: list[str] | None = None) -> dict[str, str]:
    content = _clean_for_analysis(content)
    section_map: dict[str, str] = {}
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]

    heading_patterns: list[tuple[str, str]] = [
        (r"\babstract\b", "Abstract"),
        (r"\bintroduction\b", "Introduction"),
        (r"\bbackground\b", "Background"),
        (r"\b(materials?\s+and\s+)?methods?\b", "Methods"),
        (r"\bexperimental\s+setup\b", "Methods"),
        (r"\bresults?\b", "Results"),
        (r"\bdiscussion\b", "Discussion"),
        (r"\bconclusions?\b", "Conclusions"),
        (r"\breferences?\b", "References"),
    ]

    for idx, line in enumerate(lines, start=1):
        low = line.lower()
        heading_like = bool(re.match(r"^(\d+(\.\d+)*)\s+[a-zA-Z]", low)) or (len(line) < 80 and line == line.upper())
        if not heading_like:
            continue
        for pattern, label in heading_patterns:
            if re.search(pattern, low) and label not in section_map:
                section_map[label] = f"line:{idx}"

    for supplied in headings or []:
        low = str(supplied).strip().lower()
        for pattern, label in heading_patterns:
            if re.search(pattern, low) and label not in section_map:
                section_map[label] = "heading:metadata"

    if not section_map:
        low_content = content.lower()
        for pattern, label in heading_patterns:
            match = re.search(pattern, low_content)
            if match and label not in section_map:
                prefix = content[: match.start()]
                line_no = prefix.count("\n") + 1
                section_map[label] = f"line:{line_no}"

    if not section_map:
        section_map["Body"] = "line:1"
    return section_map


def _word_freq(text: str, top_n: int = 20) -> list[tuple[str, int]]:
    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b", text.lower())
    stop = {
        "the", "and", "for", "with", "from", "that", "this", "were", "have", "into", "using",
        "results", "method", "methods", "introduction", "discussion", "conclusion", "figure", "table",
    }
    freq: dict[str, int] = {}
    for token in tokens:
        if token in stop:
            continue
        freq[token] = freq.get(token, 0) + 1
    return sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:top_n]


def _analyze_terminology(content: str) -> dict[str, Any]:
    content = _clean_for_analysis(content)
    acronyms = re.findall(r"\b[A-Z]{2,6}\b", content)
    freq = _word_freq(content)
    repeated = [w for w, c in freq if c >= 8]
    findings = []
    if repeated:
        findings.append(f"High-frequency technical terms: {', '.join(repeated[:10])}")
    if len(acronyms) > len(set(acronyms)):
        findings.append("Acronym reuse detected; verify first-use definitions are present and consistent.")
    if not findings:
        findings.append("Terminology appears broadly consistent; no obvious drift detected in heuristic pass.")
    return {
        "findings": findings,
        "top_terms": [{"term": w, "count": c} for w, c in freq[:15]],
        "acronym_count": len(acronyms),
    }


def _analyze_coherence(content: str) -> dict[str, Any]:
    content = _clean_for_analysis(content)
    sections = _simple_section_map(content)
    transitions = ["however", "therefore", "in contrast", "moreover", "consequently", "in summary", "overall"]
    transition_hits = {t: len(re.findall(rf"\b{re.escape(t)}\b", content.lower())) for t in transitions}
    weak = [k for k, v in transition_hits.items() if v == 0]
    sentences = _split_sentences(content)
    avg_len = 0.0
    if sentences:
        avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
    findings = []
    if weak:
        findings.append(f"Missing explicit transition markers for: {', '.join(weak[:4])}")
    if "Introduction" in sections and "Methods" not in sections:
        findings.append("Introduction detected without a clear Methods heading.")
    if avg_len > 32:
        findings.append("Average sentence length is high; prose may be hard to follow in dense sections.")
    if not findings:
        findings.append("Coherence heuristic found expected section flow and transition markers.")
    return {
        "findings": findings,
        "section_map": sections,
        "transition_markers": transition_hits,
        "avg_sentence_length": round(avg_len, 2),
    }


def _analyze_methods(content: str) -> dict[str, Any]:
    content = _clean_for_analysis(content)
    low = content.lower()
    required_signals = {
        "sample_size": bool(re.search(r"\b(n\s*=\s*\d+|sample size|participants?)\b", low)),
        "controls": bool(re.search(r"\b(control|baseline|ablation)\b", low)),
        "statistics": bool(re.search(r"\b(p\s*[<=>]|confidence interval|anova|t-test|regression)\b", low)),
        "reproducibility": bool(re.search(r"\b(code|repository|supplementary|protocol|reproduce)\b", low)),
    }
    missing = [k for k, ok in required_signals.items() if not ok]
    skepticism = max(0.0, min(1.0, 1.0 - (len(missing) / max(len(required_signals), 1))))
    findings = [f"Missing explicit methods evidence: {', '.join(missing)}"] if missing else ["Methods coverage appears complete in heuristic checks."]
    if required_signals["statistics"] and not required_signals["controls"]:
        findings.append("Statistical language exists, but control/baseline evidence is weak.")
    return {
        "findings": findings,
        "signal_checks": required_signals,
        "skepticism_score": round(skepticism, 3),
    }


def _analyze_figures_tables(content: str) -> dict[str, Any]:
    content = _clean_for_analysis(content)
    figure_refs = re.findall(r"\b(fig(?:ure)?\.?\s*\d+[a-z]?)\b", content, flags=re.IGNORECASE)
    table_refs = re.findall(r"\b(table\s*\d+[a-z]?)\b", content, flags=re.IGNORECASE)
    findings = []
    if not figure_refs and not table_refs:
        findings.append("No figure/table references detected.")
    if len(set(figure_refs)) != len(figure_refs):
        findings.append("Repeated figure references detected; verify numbering and callout uniqueness.")
    if len(set(table_refs)) != len(table_refs):
        findings.append("Repeated table references detected; verify numbering and callout uniqueness.")
    if not findings:
        findings.append("Figure/table references detected with no obvious numbering duplication.")
    return {
        "findings": findings,
        "figure_references": sorted(set(figure_refs)),
        "table_references": sorted(set(table_refs)),
    }


def _analyze_citations(content: str) -> dict[str, Any]:
    content = _clean_for_analysis(content)
    bracketed = re.findall(r"\[[0-9]{1,3}(?:\s*,\s*[0-9]{1,3})*\]", content)
    paren_year = re.findall(r"\(([A-Z][A-Za-z]+(?:\s+et\s+al\.)?,?\s+[12][0-9]{3}[a-z]?)\)", content)
    doi_hits = re.findall(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b", content)
    findings = []
    if not bracketed and not paren_year:
        findings.append("No conventional in-text citation markers detected.")
    if len(doi_hits) == 0:
        findings.append("No DOI strings detected in manuscript text.")
    if not findings:
        findings.append("Citation markers and DOI-like identifiers detected.")
    return {
        "findings": findings,
        "citation_marker_count": len(bracketed) + len(paren_year),
        "doi_count": len(doi_hits),
    }


def _analyze_journal_format(content: str) -> dict[str, Any]:
    content = _clean_for_analysis(content)
    low = content.lower()
    checks = {
        "has_abstract": bool(re.search(r"\babstract\b", low)),
        "has_references": bool(re.search(r"\breferences?\b", low)),
        "has_keywords": bool(re.search(r"\bkeywords?\b", low)),
        "has_methods": bool(re.search(r"\bmethods?|experimental\b", low)),
    }
    missing = [k for k, ok in checks.items() if not ok]
    findings = [f"Missing common manuscript sections: {', '.join(missing)}"] if missing else ["Core manuscript sections found by heuristic checks."]
    return {
        "findings": findings,
        "checks": checks,
    }


def _generate_line_edits(content: str) -> dict[str, Any]:
    content = _clean_for_analysis(content)
    edits = []
    for idx, sentence in enumerate(_split_sentences(content)[:200], start=1):
        if len(sentence.split()) < 35:
            continue
        shorter = re.sub(r"\s+", " ", sentence).strip()
        shorter = shorter.replace(" however ", " but ").replace(" therefore ", " so ")
        edits.append({"line_id": idx, "issue": "Long sentence", "original": sentence, "suggested": shorter})
        if len(edits) >= 12:
            break
    if not edits:
        edits.append({"line_id": 1, "issue": "No obvious long-sentence issues", "original": "", "suggested": ""})
    return {"line_edits": edits}


def _arbitrate(findings: list[str], profile: str = "balanced_local") -> dict[str, Any]:
    severity = "minor_revision"
    high_risk_tokens = ["missing", "unsupported", "contradicted", "no conventional", "no figure", "no table"]
    score = sum(1 for item in findings for token in high_risk_tokens if token in item.lower())
    if profile in {"one_big_model", "full_manuscript_final_pass"}:
        score += 1
    if score >= 4:
        severity = "major_revision"
    if score >= 7:
        severity = "reject"
    return {
        "recommendation": severity,
        "summary": "\n".join(f"- {f}" for f in findings[:20]),
        "score": score,
        "profile": profile,
    }


def _consume_render_logs() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    global LAST_RENDER_TOOL_OFFSET, LAST_RENDER_NETWORK_OFFSET
    window = TOOL_EVENT_LOG[LAST_RENDER_TOOL_OFFSET:]
    start_idx = 0
    for idx in range(len(window) - 1, -1, -1):
        row = window[idx]
        if row.get("status") == "start" and row.get("tool") in {"parse_pdf", "parse_docx"}:
            start_idx = idx
            break
    tool_rows = window[start_idx:]
    network_rows = NETWORK_EVENT_LOG[LAST_RENDER_NETWORK_OFFSET:]
    LAST_RENDER_TOOL_OFFSET = len(TOOL_EVENT_LOG)
    LAST_RENDER_NETWORK_OFFSET = len(NETWORK_EVENT_LOG)
    return tool_rows, network_rows


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _build_artifacts(review_data: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    section_map = review_data.get("section_map") or {}
    comments = review_data.get("comments") or []
    suggested_changes = review_data.get("suggested_changes") or []
    source_mode = review_data.get("source_mode") or {"mode": "unknown", "base_type": "unknown"}

    if not isinstance(comments, list):
        comments = [str(comments)]
    if not isinstance(suggested_changes, list):
        suggested_changes = [suggested_changes]

    if not suggested_changes:
        suggested_changes = [
            {
                "id": f"edit-{i+1}",
                "target": "body",
                "original": str(comment)[:240],
                "suggested": str(comment)[:240],
            }
            for i, comment in enumerate(comments[:8])
        ]

    support_ingest_report = review_data.get("support_ingest_report") or {
        "available_support_docs": 0,
        "selected_support_docs": 0,
        "selection_basis": "none",
    }
    support_usage_ledger = review_data.get("support_usage_ledger") or {"used_sources": [], "unused_sources": []}
    assertion_ledger = review_data.get("assertion_ledger") or {"claim_count": 0, "claims": []}
    claim_verification_summary = review_data.get("claim_verification_summary") or {
        "claim_count": assertion_ledger.get("claim_count", 0),
        "claims_checked": 0,
        "likely_overstated": 0,
        "status": "heuristic_only",
    }
    citation_verification_ledger = review_data.get("citation_verification_ledger") or {"entries": [], "status": "heuristic_only"}
    format_compliance_report = review_data.get("format_compliance_report") or {"checks": {}, "findings": []}
    terminology_definition_report = review_data.get("terminology_definition_report") or {"defined_terms": [], "findings": []}
    coherence_transition_report = review_data.get("coherence_transition_report") or {"transition_markers": {}, "findings": []}
    figure_table_reference_report = review_data.get("figure_table_reference_report") or {
        "figure_references": [],
        "table_references": [],
        "findings": [],
    }
    routing_trace = review_data.get("routing_trace") or {
        "profile": review_data.get("profile", "balanced_local"),
        "transport": "local_mcp_bridge",
        "stages": review_data.get("stages", []),
        "model_target": review_data.get("model_target", "unknown"),
    }

    run_summary = {
        "timestamp": _now_iso(),
        "status": "completed",
        "profile": review_data.get("profile", "balanced_local"),
        "mode": review_data.get("mode", "unspecified"),
        "model_target": review_data.get("model_target", routing_trace.get("model_target", "unknown")),
        "comment_count": len(comments),
        "suggested_change_count": len(suggested_changes),
        "artifact_version": "v2-review-bridge",
    }

    transcript_lines = ["# Session Transcript", "", "## Run Summary", json.dumps(run_summary, indent=2), "", "## Top Findings"]
    for comment in comments[:25]:
        transcript_lines.append(f"- {comment}")

    payloads = {
        "source_mode.json": source_mode,
        "section_map.json": section_map,
        "manuscript_comment_manifest.json": comments,
        "manuscript_suggested_changes_manifest.json": suggested_changes,
        "support_ingest_report.json": support_ingest_report,
        "support_usage_ledger.json": support_usage_ledger,
        "assertion_ledger.json": assertion_ledger,
        "claim_verification_summary.json": claim_verification_summary,
        "citation_verification_ledger.json": citation_verification_ledger,
        "format_compliance_report.json": format_compliance_report,
        "terminology_definition_report.json": terminology_definition_report,
        "coherence_transition_report.json": coherence_transition_report,
        "figure_table_reference_report.json": figure_table_reference_report,
        "routing_trace.json": routing_trace,
        "run_summary.json": run_summary,
    }

    for name, payload in payloads.items():
        _write_json(output_dir / name, payload)
    run_tool_rows = review_data.get("tool_events")
    run_network_rows = review_data.get("network_events")
    if isinstance(run_tool_rows, list) and isinstance(run_network_rows, list):
        _write_jsonl(output_dir / "tool_event_log.jsonl", run_tool_rows)
        _write_jsonl(output_dir / "network_event_log.jsonl", run_network_rows)
    else:
        tool_rows, network_rows = _consume_render_logs()
        _write_jsonl(output_dir / "tool_event_log.jsonl", tool_rows)
        _write_jsonl(output_dir / "network_event_log.jsonl", network_rows)
    (output_dir / "session_transcript.md").write_text("\n".join(transcript_lines) + "\n", encoding="utf-8")

    return {"status": "success", "artifacts": sorted([p.name for p in output_dir.iterdir() if p.is_file()])}


def _validate_artifacts(output_dir: Path) -> dict[str, Any]:
    required = [
        "source_mode.json",
        "section_map.json",
        "manuscript_comment_manifest.json",
        "manuscript_suggested_changes_manifest.json",
        "support_ingest_report.json",
        "support_usage_ledger.json",
        "assertion_ledger.json",
        "claim_verification_summary.json",
        "citation_verification_ledger.json",
        "format_compliance_report.json",
        "terminology_definition_report.json",
        "coherence_transition_report.json",
        "figure_table_reference_report.json",
        "routing_trace.json",
        "tool_event_log.jsonl",
        "network_event_log.jsonl",
        "run_summary.json",
        "session_transcript.md",
    ]

    missing = [name for name in required if not (output_dir / name).exists()]
    json_errors: list[str] = []

    for name in required:
        path = output_dir / name
        if not path.exists() or path.suffix not in {".json", ".jsonl"}:
            continue
        try:
            if path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
            else:
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        json.loads(line)
        except Exception as exc:
            json_errors.append(f"{name}: {exc}")

    front_matter_violations = []
    suggest_path = output_dir / "manuscript_suggested_changes_manifest.json"
    if suggest_path.exists():
        try:
            payload = json.loads(suggest_path.read_text(encoding="utf-8"))
            for idx, item in enumerate(payload if isinstance(payload, list) else []):
                target = str(item.get("target", "")).lower()
                if any(tok in target for tok in ["title", "author", "affiliation", "journal", "doi"]):
                    front_matter_violations.append({"index": idx, "target": target})
        except Exception:
            pass

    remote_network_events = []
    network_path = output_dir / "network_event_log.jsonl"
    if network_path.exists():
        for line in network_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                evt = json.loads(line)
            except Exception:
                continue
            host = str(evt.get("host", "")).lower()
            if host not in {"localhost", "127.0.0.1", "::1", ""}:
                remote_network_events.append(evt)

    valid = not missing and not json_errors and not front_matter_violations and not remote_network_events
    payload = {
        "valid": valid,
        "missing": missing,
        "json_errors": json_errors,
        "front_matter_violations": front_matter_violations,
        "remote_network_events": remote_network_events,
    }
    _write_json(output_dir / "validation_report.json", payload)
    return payload


def _resolve_run_path(run_id: str, cwd: Path | None = None) -> Path | None:
    candidate = Path(run_id)
    if candidate.exists() and candidate.is_dir():
        return candidate.resolve()

    base = cwd or Path.cwd()
    roots = [base, base / "projects", base / "outputs"]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("run_summary.json"):
            run_dir = path.parent
            if run_dir.name == run_id:
                return run_dir.resolve()
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if str(payload.get("run_id", "")) == run_id:
                    return run_dir.resolve()
            except Exception:
                continue
    return None


def _load_run_snapshot(run_dir: Path) -> dict[str, Any]:
    def _load(name: str, default: Any) -> Any:
        path = run_dir / name
        if not path.exists():
            return default
        try:
            if path.suffix == ".json":
                return json.loads(path.read_text(encoding="utf-8"))
            return path.read_text(encoding="utf-8")
        except Exception:
            return default

    return {
        "run_dir": str(run_dir),
        "run_summary": _load("run_summary.json", {}),
        "section_map": _load("section_map.json", {}),
        "comments": _load("manuscript_comment_manifest.json", []),
        "suggested_changes": _load("manuscript_suggested_changes_manifest.json", []),
    }


def _tool_specs() -> list[dict[str, Any]]:
    return [
        {"name": "inspect_project", "description": "Summarize environment status and manuscript detection.", "inputSchema": {"type": "object", "properties": {"cwd": {"type": "string"}}, "required": ["cwd"]}},
        {"name": "discover_manuscript", "description": "Search for manuscript files in project.", "inputSchema": {"type": "object", "properties": {"cwd": {"type": "string"}}, "required": ["cwd"]}},
        {"name": "parse_docx", "description": "Extract text and metadata from .docx.", "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}},
        {"name": "parse_pdf", "description": "Extract text and metadata from .pdf.", "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}},
        {"name": "map_sections", "description": "Map manuscript sections.", "inputSchema": {"type": "object", "properties": {"content": {"type": "string"}, "headings": {"type": "array", "items": {"type": "string"}}}, "required": ["content"]}},
        {"name": "digest_manuscript", "description": "Create manuscript digest.", "inputSchema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}},
        {"name": "analyze_terminology", "description": "Analyze terminology consistency.", "inputSchema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}},
        {"name": "analyze_coherence", "description": "Analyze narrative coherence.", "inputSchema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}},
        {"name": "analyze_methods", "description": "Analyze methods rigor.", "inputSchema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}},
        {"name": "analyze_figures_tables", "description": "Analyze figure/table references.", "inputSchema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}},
        {"name": "analyze_citations", "description": "Analyze citations.", "inputSchema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}},
        {"name": "analyze_journal_format", "description": "Analyze journal formatting.", "inputSchema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}},
        {"name": "generate_line_edits", "description": "Generate line-level edits.", "inputSchema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}},
        {"name": "arbitrate_review", "description": "Synthesize findings.", "inputSchema": {"type": "object", "properties": {"findings": {"type": "array", "items": {"type": "string"}}, "profile": {"type": "string"}}, "required": ["findings"]}},
        {"name": "render_outputs", "description": "Render artifacts.", "inputSchema": {"type": "object", "properties": {"review_data": {"type": "object"}, "output_dir": {"type": "string"}}, "required": ["review_data", "output_dir"]}},
        {"name": "validate_outputs", "description": "Validate artifacts.", "inputSchema": {"type": "object", "properties": {"output_dir": {"type": "string"}}, "required": ["output_dir"]}},
        {"name": "replay_run", "description": "Replay prior run.", "inputSchema": {"type": "object", "properties": {"run_id": {"type": "string"}, "cwd": {"type": "string"}}, "required": ["run_id"]}},
        {"name": "diff_run", "description": "Diff two runs.", "inputSchema": {"type": "object", "properties": {"run_id_a": {"type": "string"}, "run_id_b": {"type": "string"}, "cwd": {"type": "string"}}, "required": ["run_id_a", "run_id_b"]}},
        {"name": "benchmark_project", "description": "Benchmark project parsing throughput.", "inputSchema": {"type": "object", "properties": {"project_id": {"type": "string"}, "cwd": {"type": "string"}}, "required": ["project_id"]}},
    ]


def _tool_response(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


def _dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    _log_tool_event(name, "start", {"arguments": list(arguments.keys())})
    try:
        if name == "inspect_project":
            cwd = Path(arguments.get("cwd", os.getcwd())).resolve()
            manuscripts = _manuscripts_in_dir(cwd)
            payload = {
                "cwd": str(cwd),
                "manuscript_count": len(manuscripts),
                "manuscripts": [str(m) for m in manuscripts],
                "ollama_running": _check_ollama(),
                "blocked_project_policy": list(BLOCKED_PROJECT_SNIPPETS),
                "timestamp": _now_iso(),
            }
            _log_tool_event(name, "ok", {"manuscript_count": len(manuscripts)})
            return payload

        if name == "discover_manuscript":
            cwd = Path(arguments.get("cwd", os.getcwd())).resolve()
            manuscripts = _manuscripts_in_dir(cwd)
            payload = {
                "manuscripts": [{"path": str(m), "type": m.suffix.lower().lstrip(".")} for m in manuscripts],
                "blocked_project_policy": list(BLOCKED_PROJECT_SNIPPETS),
            }
            _log_tool_event(name, "ok", {"count": len(manuscripts)})
            return payload

        if name in {"parse_docx", "parse_pdf"}:
            file_path = Path(arguments["file_path"]).resolve()
            if _is_blocked_path(file_path):
                raise ValueError(f"Path blocked by policy: {file_path}")
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            doc = _parse_manuscript(file_path)
            extracted_text = doc.cleaned_text[:20000]
            payload = {
                "content": extracted_text,
                "content_preview": extracted_text[:2000] + ("..." if len(extracted_text) > 2000 else ""),
                "full_content_length": len(doc.cleaned_text),
                "metadata": {
                    "headings": doc.headings,
                    "page_count": doc.page_count,
                    "file_size": doc.file_size_bytes,
                    "parse_engine": doc.parse_engine,
                    "warnings": doc.parse_warnings,
                    "content_truncated": len(doc.cleaned_text) > len(extracted_text),
                },
            }
            _log_tool_event(name, "ok", {"chars": len(doc.cleaned_text)})
            return payload

        if name == "map_sections":
            content = str(arguments.get("content", ""))
            headings = arguments.get("headings") if isinstance(arguments.get("headings"), list) else None
            section_map = _simple_section_map(content, headings=headings)
            payload = {"section_map": section_map, "section_count": len(section_map)}
            _log_tool_event(name, "ok", {"section_count": len(section_map)})
            return payload

        if name == "digest_manuscript":
            content = str(arguments.get("content", ""))
            sentences = _split_sentences(content)
            digest = " ".join(sentences[:6])[:2500]
            key_terms = [w for w, _ in _word_freq(content, top_n=15)]
            payload = {"digest": digest, "key_terms": key_terms, "word_count": len(content.split())}
            _log_tool_event(name, "ok", {"word_count": payload["word_count"]})
            return payload

        if name == "analyze_terminology":
            payload = _analyze_terminology(str(arguments.get("content", "")))
            _log_tool_event(name, "ok", {"findings": len(payload.get("findings", []))})
            return payload

        if name == "analyze_coherence":
            payload = _analyze_coherence(str(arguments.get("content", "")))
            _log_tool_event(name, "ok", {"findings": len(payload.get("findings", []))})
            return payload

        if name == "analyze_methods":
            payload = _analyze_methods(str(arguments.get("content", "")))
            _log_tool_event(name, "ok", {"skepticism_score": payload.get("skepticism_score")})
            return payload

        if name == "analyze_figures_tables":
            payload = _analyze_figures_tables(str(arguments.get("content", "")))
            _log_tool_event(name, "ok", {"figures": len(payload.get("figure_references", []))})
            return payload

        if name == "analyze_citations":
            payload = _analyze_citations(str(arguments.get("content", "")))
            _log_tool_event(name, "ok", {"citation_markers": payload.get("citation_marker_count", 0)})
            return payload

        if name == "analyze_journal_format":
            payload = _analyze_journal_format(str(arguments.get("content", "")))
            _log_tool_event(name, "ok", {"findings": len(payload.get("findings", []))})
            return payload

        if name == "generate_line_edits":
            payload = _generate_line_edits(str(arguments.get("content", "")))
            _log_tool_event(name, "ok", {"line_edits": len(payload.get("line_edits", []))})
            return payload

        if name == "arbitrate_review":
            findings = arguments.get("findings")
            findings_list = [str(x) for x in findings] if isinstance(findings, list) else [str(findings or "")]
            profile = str(arguments.get("profile", "balanced_local"))
            payload = _arbitrate(findings_list, profile=profile)
            _log_tool_event(name, "ok", {"recommendation": payload.get("recommendation")})
            return payload

        if name == "render_outputs":
            review_data = arguments.get("review_data")
            if not isinstance(review_data, dict):
                raise ValueError("review_data must be an object")
            output_dir = Path(arguments["output_dir"]).resolve()
            payload = _build_artifacts(review_data, output_dir)
            _log_tool_event(name, "ok", {"artifact_count": len(payload.get("artifacts", []))})
            return payload

        if name == "validate_outputs":
            output_dir = Path(arguments["output_dir"]).resolve()
            payload = _validate_artifacts(output_dir)
            _log_tool_event(name, "ok", {"valid": payload.get("valid")})
            return payload

        if name == "replay_run":
            run_id = str(arguments["run_id"])
            run_dir = _resolve_run_path(run_id, Path(arguments["cwd"]).resolve() if arguments.get("cwd") else None)
            if run_dir is None:
                raise FileNotFoundError(f"Run not found: {run_id}")
            payload = _load_run_snapshot(run_dir)
            _log_tool_event(name, "ok", {"run_dir": str(run_dir)})
            return payload

        if name == "diff_run":
            cwd = Path(arguments["cwd"]).resolve() if arguments.get("cwd") else None
            run_a = _resolve_run_path(str(arguments["run_id_a"]), cwd)
            run_b = _resolve_run_path(str(arguments["run_id_b"]), cwd)
            if run_a is None or run_b is None:
                raise FileNotFoundError("One or both run IDs were not found")
            snap_a = _load_run_snapshot(run_a)
            snap_b = _load_run_snapshot(run_b)
            comments_a = snap_a.get("comments", []) if isinstance(snap_a.get("comments", []), list) else []
            comments_b = snap_b.get("comments", []) if isinstance(snap_b.get("comments", []), list) else []
            payload = {
                "run_a": str(run_a),
                "run_b": str(run_b),
                "comment_count_a": len(comments_a),
                "comment_count_b": len(comments_b),
                "comment_delta": len(comments_b) - len(comments_a),
                "section_count_a": len(snap_a.get("section_map", {})) if isinstance(snap_a.get("section_map", {}), dict) else 0,
                "section_count_b": len(snap_b.get("section_map", {})) if isinstance(snap_b.get("section_map", {}), dict) else 0,
            }
            _log_tool_event(name, "ok", {"comment_delta": payload["comment_delta"]})
            return payload

        if name == "benchmark_project":
            project_id = str(arguments["project_id"]).strip()
            if _is_blocked_name(project_id):
                raise ValueError(f"Project is blocked by policy: {project_id}")
            cwd = Path(arguments.get("cwd", os.getcwd())).resolve()
            project_dir = cwd / "projects" / project_id
            if not project_dir.exists():
                raise FileNotFoundError(f"Project not found: {project_dir}")
            if _is_blocked_path(project_dir):
                raise ValueError(f"Project is blocked by policy: {project_id}")
            candidates = [p for p in _manuscripts_in_dir(project_dir) if p.suffix.lower() in MANUSCRIPT_SUFFIXES]
            parse_stats = []
            for manuscript in candidates[:5]:
                t_parse = time.perf_counter()
                doc = _parse_manuscript(manuscript)
                parse_stats.append({
                    "file": str(manuscript),
                    "seconds": round(time.perf_counter() - t_parse, 4),
                    "chars": len(doc.cleaned_text),
                    "warnings": len(doc.parse_warnings),
                })
            payload = {
                "project_id": project_id,
                "manuscripts_benchmarked": len(parse_stats),
                "parse_stats": parse_stats,
                "total_seconds": round(sum(item["seconds"] for item in parse_stats), 4),
            }
            _log_tool_event(name, "ok", {"manuscripts": len(parse_stats)})
            return payload

        raise ValueError(f"Unknown tool: {name}")

    except Exception as exc:
        _log_tool_event(name, "error", {"error": str(exc)})
        return {"error": str(exc)}
    finally:
        _log_tool_event(name, "complete", {"elapsed_ms": round((time.perf_counter() - t0) * 1000, 2)})


def _handle_request(req: dict[str, Any]) -> dict[str, Any]:
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": _tool_specs()}}

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        result_payload = _dispatch_tool(str(tool_name), arguments)
        return {"jsonrpc": "2.0", "id": req_id, "result": _tool_response(result_payload)}

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> None:
    while True:
        raw = sys.stdin.readline()
        if not raw:
            break
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
            resp = _handle_request(req)
        except Exception as exc:
            resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(exc)},
            }
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
