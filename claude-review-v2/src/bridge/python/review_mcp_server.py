import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
try:
    from .color_palette_audit import ColorPaletteError, audit_pdf_color_palette
except ImportError:
    from color_palette_audit import ColorPaletteError, audit_pdf_color_palette

try:
    from ai_reviewer.ingest.loaders import collect_paths as ai_collect_paths
    from ai_reviewer.ingest.loaders import parse_file as ai_parse_file
except Exception:
    ai_collect_paths = None
    ai_parse_file = None

SERVER_NAME = "manuscript-review-server"
SERVER_VERSION = "0.3.0"
BLOCKED_PROJECT_SNIPPETS = ("pampa", "horseshoe", "test-d2b")
MANUSCRIPT_SUFFIXES = {".docx", ".pdf"}
DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
MAX_STAGE_COMMENT_COUNT = 14
INGEST_SCHEMA_VERSION = "support_ingest_v2"
MAX_SUPPORT_DOCS = 24
MAX_CITATION_VERIFICATION_SENTENCES = 120
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SUPPORT_CACHE_ROOT = PROJECT_ROOT / ".runtime" / "support_ingest_cache"
COLOR_PALETTE_OUTPUT_ROOT = PROJECT_ROOT / "test_outputs" / "color_palette_audits"

STAGE_ORDER = [
    "structural_review",
    "high_level_review",
    "hostile_review",
    "methods_verification",
    "line_by_line_edits",
    "style_alignment",
    "reconciliation",
    "final_arbitration",
]

STAGE_TO_MODEL_CANDIDATES = {
    "structural_review": ["qwen3:8b", "qwen2.5:7b-instruct", "qwen2.5:7b", "llama3.1:8b"],
    "high_level_review": ["mistral-small3.2", "mistral:7b", "llama3.1:8b"],
    "hostile_review": ["phi4-reasoning", "phi4:14b", "qwen2.5-coder:14b", "qwen2.5-coder:7b"],
    "methods_verification": ["qwen2.5-coder:14b", "qwen2.5-coder:7b", "mistral-small3.2"],
    "line_by_line_edits": ["qwen2.5:7b-instruct", "qwen2.5-coder:7b", "llama3.1:8b"],
    "style_alignment": ["mistral-small3.2", "llama3.1:8b"],
    "reconciliation": ["gemma4:26b", "gemma4:31b", "qwen2.5-coder:32b", "llama3.1:8b"],
    "final_arbitration": ["gemma4:26b", "gemma4:31b", "qwen2.5-coder:32b", "mistral-small3.2"],
}

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


def _ensure_local_output_root(path: Path) -> Path:
    candidate = path.resolve()
    try:
        candidate.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError(f"Output path must stay inside claude-review-v2: {candidate}") from exc
    return candidate


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
    warnings = []
    text = ""
    parse_engine = "pdf-byte-fallback"
    try:
        # Prefer pdftotext when present; it is substantially cleaner than the
        # byte-level fallback for citation parsing and sentence-level comments.
        proc = subprocess.run(
            ["pdftotext", "-layout", "-nopgbrk", str(path), "-"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if proc.returncode == 0 and proc.stdout:
            text = _clean_for_analysis(proc.stdout)
            parse_engine = "pdftotext-cli-fallback"
        else:
            warnings.append("pdftotext failed; using byte-level fallback parser.")
    except Exception as exc:
        warnings.append(f"pdftotext unavailable/failed ({exc}); using byte-level fallback parser.")

    if not text:
        warnings.append("Using heuristic byte-level PDF fallback parser; install pypdf for better extraction.")
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
            if len(txt) < 3:
                continue
            # Drop obviously noisy fragments from byte-level extraction.
            letters = len(re.findall(r"[A-Za-z]", txt))
            if letters < 4:
                continue
            if len(txt) > 36 and (letters / max(len(txt), 1)) < 0.4:
                continue
            parts.append(txt)
        text = "\n".join(parts[:5000])
    if not text:
        warnings.append("No extractable text found in PDF bytes.")
    return ParsedDoc(
        cleaned_text=text,
        headings=[],
        page_count=None,
        file_size_bytes=path.stat().st_size,
        parse_engine=parse_engine,
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


def _normalize_model_name(name: str) -> str:
    return (name or "").strip().lower()


def _contains_prefix(models: list[str], prefix: str) -> bool:
    pref = _normalize_model_name(prefix)
    return any(_normalize_model_name(model).startswith(pref) for model in models)


def _first_model_by_prefix(models: list[str], candidates: list[str]) -> str | None:
    normalized = [(_normalize_model_name(model), model) for model in models]
    for candidate in candidates:
        cand = _normalize_model_name(candidate)
        for model_low, model_raw in normalized:
            if model_low.startswith(cand):
                return model_raw
    return None


def _parse_model_size_billions(model_name: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*b", model_name.lower())
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None


def _largest_model(models: list[str]) -> str | None:
    ranked: list[tuple[float, str]] = []
    for model in models:
        size = _parse_model_size_billions(model)
        if size is not None:
            ranked.append((size, model))
    if ranked:
        ranked.sort(reverse=True)
        return ranked[0][1]
    return models[0] if models else None


def _safe_json_loads(text: str) -> Any | None:
    try:
        return json.loads(text)
    except Exception:
        return None


def _extract_json_object(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    parsed = _safe_json_loads(candidate)
    if isinstance(parsed, dict):
        return parsed
    fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, flags=re.IGNORECASE)
    if fence_match:
        parsed = _safe_json_loads(fence_match.group(1))
        if isinstance(parsed, dict):
            return parsed
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        parsed = _safe_json_loads(brace_match.group(0))
        if isinstance(parsed, dict):
            return parsed
    return None


def _extract_best_effort_object(text: str) -> dict[str, Any] | None:
    parsed = _extract_json_object(text)
    if parsed is not None:
        return parsed

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    kv: dict[str, Any] = {}
    for line in lines[:24]:
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_ -]{1,40})\s*:\s*(.+)$", line)
        if not match:
            continue
        key = re.sub(r"\s+", "_", match.group(1).strip().lower())
        value = match.group(2).strip()
        if key and value and key not in kv:
            kv[key] = value
    if kv:
        return kv

    bullet_rows: list[str] = []
    for line in lines[:20]:
        bullet = re.match(r"^(?:[-*]|\d+\.)\s+(.+)$", line)
        if bullet:
            item = bullet.group(1).strip()
            if item:
                bullet_rows.append(item)
    if bullet_rows:
        return {"findings": bullet_rows[:6]}
    return None


def _truncate_chars(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def _compact_prompt(text: str, max_chars: int, expect_json: bool = False) -> str:
    base = text.strip()
    if len(base) <= max_chars:
        return base
    head_keep = max(600, int(max_chars * 0.6))
    tail_keep = max(240, int(max_chars * 0.25))
    compacted = (
        base[:head_keep]
        + "\n\n[...prompt truncated for runtime stability...]\n\n"
        + base[-tail_keep:]
    )
    if expect_json:
        compacted = (
            "Return exactly one JSON object and no prose.\n"
            + compacted
        )
    return compacted[:max_chars]


def _sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def _sha1_file_prefix(path: Path, max_bytes: int = 1_048_576) -> str:
    hasher = hashlib.sha1()
    with path.open("rb") as handle:
        hasher.update(handle.read(max_bytes))
    return hasher.hexdigest()


def _file_fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size_bytes": stat.st_size,
        "mtime_ns": int(stat.st_mtime_ns),
        "sha1_prefix": _sha1_file_prefix(path),
    }


def _safe_slug(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned[:80] or "item"


def _references_split(content: str) -> tuple[str, str]:
    cleaned = _clean_for_analysis(content)
    heading_matches = list(
        re.finditer(
            r"(?im)^\s*(?:[■•*]+[\s]*)?(references|bibliography)\b[\s:.-]*$",
            cleaned,
        )
    )
    if heading_matches:
        heading = heading_matches[-1]
        return cleaned[: heading.start()].strip(), cleaned[heading.end() :].strip()

    decorated_line_matches = list(
        re.finditer(
            r"(?im)^\s*(?:[■•*]+[\s]*)?(references|bibliography)\b.*$",
            cleaned,
        )
    )
    if decorated_line_matches:
        preferred = None
        min_idx = int(len(cleaned) * 0.55)
        for match in decorated_line_matches:
            if match.start() >= min_idx:
                preferred = match
        chosen = preferred or decorated_line_matches[-1]
        return cleaned[: chosen.start()].strip(), cleaned[chosen.start() :].strip()

    # Fallback for PDFs where the heading is lost but numbered references
    # appear as "(1) ...", "(2) ...", ... near the end of extracted text.
    paren_ref_matches = list(re.finditer(r"(?m)^\s*\(\d{1,3}\)\s+", cleaned))
    if len(paren_ref_matches) >= 2:
        min_start = int(len(cleaned) * 0.2)
        chosen_start = None
        for match in paren_ref_matches:
            if match.start() < min_start:
                continue
            tail = cleaned[match.start() :]
            tail_ref_count = len(re.findall(r"(?m)^\s*\(\d{1,3}\)\s+", tail[:16000]))
            tail_year_count = len(re.findall(r"\b(19|20)\d{2}\b", tail[:5000]))
            if tail_ref_count >= 2 and tail_year_count >= 2:
                chosen_start = match.start()
                break
        if chosen_start is None:
            chosen_start = paren_ref_matches[0].start()
        return cleaned[:chosen_start].strip(), cleaned[chosen_start:].strip()

    inline_matches = list(re.finditer(r"(?i)\breferences\b", cleaned))
    if inline_matches:
        preferred = None
        min_idx = int(len(cleaned) * 0.55)
        for match in inline_matches:
            if match.start() >= min_idx:
                preferred = match
        chosen = preferred or inline_matches[-1]
        return cleaned[: chosen.start()].strip(), cleaned[chosen.start() :].strip()
    return cleaned, ""


def _extract_reference_entries(content: str) -> list[dict[str, Any]]:
    _, reference_text = _references_split(content)
    if not reference_text:
        return []

    def _build_entries(matches: list[re.Match[str]], *, raw_group: int) -> list[dict[str, Any]]:
        built: list[dict[str, Any]] = []
        for idx, match in enumerate(matches, start=1):
            number_text = match.group(1) or match.group(2) or str(idx)
            raw = re.sub(r"\s+", " ", match.group(raw_group) or "").strip()
            if len(raw) < 12:
                continue
            number = int(number_text)
            doi_match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b", raw)
            year_match = re.search(r"\b(19|20)\d{2}\b", raw)
            author_match = re.match(r"^([A-Z][A-Za-z'`-]+)", raw)
            built.append(
                {
                    "id": f"ref-{number}",
                    "index": number,
                    "raw": raw,
                    "doi": doi_match.group(0) if doi_match else "",
                    "year": year_match.group(0) if year_match else "",
                    "author_hint": author_match.group(1) if author_match else "",
                    "title_hint": raw[:160],
                }
            )
        return built

    numeric_matches = list(
        re.finditer(
            r"(?:^|\n)\s*(?:\[(\d{1,3})\]|(\d{1,3})\.)\s*(.+?)(?=(?:\n\s*(?:\[\d{1,3}\]|\d{1,3}\.)\s)|\Z)",
            reference_text,
            flags=re.DOTALL,
        )
    )

    paren_matches = list(
        re.finditer(
            r"(?:^|\n|\s)\((\d{1,3})\)\s*(.+?)(?=(?:\s+\(\d{1,3}\)\s)|(?:\n\s*\(\d{1,3}\)\s)|\Z)",
            reference_text,
            flags=re.DOTALL,
        )
    )
    numeric_entries = _build_entries(numeric_matches, raw_group=3) if numeric_matches else []
    paren_entries = _build_entries(paren_matches, raw_group=2) if paren_matches else []
    if paren_entries and len(paren_entries) >= max(2, len(numeric_entries)):
        return paren_entries
    if numeric_entries:
        return numeric_entries

    entries: list[dict[str, Any]] = []
    lines = [ln.strip() for ln in reference_text.splitlines() if ln.strip()]
    for idx, line in enumerate(lines[:250], start=1):
        if len(line) < 16:
            continue
        doi_match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b", line)
        year_match = re.search(r"\b(19|20)\d{2}\b", line)
        author_match = re.match(r"^([A-Z][A-Za-z'`-]+)", line)
        entries.append(
            {
                "id": f"ref-{idx}",
                "index": idx,
                "raw": line,
                "doi": doi_match.group(0) if doi_match else "",
                "year": year_match.group(0) if year_match else "",
                "author_hint": author_match.group(1) if author_match else "",
                "title_hint": line[:160],
            }
        )
    return entries


def _extract_abstract_text(text: str) -> str:
    cleaned = _clean_for_analysis(text)
    match = re.search(
        r"(?is)\babstract\b[:\s-]*([\s\S]{80,2600}?)(?:\n\s*(?:introduction|background|methods?|materials|results?|discussion|conclusions?)\b|$)",
        cleaned,
    )
    if match:
        candidate = re.sub(r"\s+", " ", match.group(1)).strip()
        if len(candidate) >= 40:
            return candidate[:1600]
    sentences = _split_sentences(cleaned)
    return " ".join(sentences[:4])[:1600]


def _looks_like_title_boilerplate(line: str) -> bool:
    low = line.strip().lower()
    if not low:
        return True
    boilerplate_fragments = [
        "creative commons",
        "licensed under",
        "downloaded via",
        "copyright",
        "all rights reserved",
        "article https://doi.org/",
        "nature synthesis | volume",
        "org. process res. dev.",
        "supporting information",
        "view article online",
        "pubs.acs.org",
        "www.",
    ]
    return any(fragment in low for fragment in boilerplate_fragments)


def _title_tokens(text: str, *, min_len: int = 4) -> list[str]:
    return [
        tok
        for tok in re.findall(r"\b[a-zA-Z]{%d,}\b" % min_len, text.lower())
        if tok not in {"article", "journal", "through", "license", "licensed"}
    ]


def _extract_title_line(text: str, fallback: str) -> str:
    lines = [ln.strip() for ln in _clean_for_analysis(text).splitlines() if ln.strip()]
    candidates: list[tuple[float, str]] = []
    for idx, line in enumerate(lines[:40], start=1):
        if len(line) < 20 or len(line) > 220:
            continue
        if _looks_like_title_boilerplate(line):
            continue
        letters = len(re.findall(r"[A-Za-z]", line))
        if letters < 12:
            continue
        title_tokens = _title_tokens(line, min_len=4)
        if len(title_tokens) < 3:
            continue
        score = 0.0
        score += max(0.0, 5.0 - (idx * 0.15))
        score += min(3.0, len(title_tokens) * 0.2)
        if re.search(r"\b(19|20)\d{2}\b", line):
            score -= 0.5
        if line == line.upper():
            score -= 0.4
        if re.search(r"\bdoi\b", line, flags=re.IGNORECASE):
            score -= 0.6
        candidates.append((score, line))
    if candidates:
        candidates.sort(key=lambda row: (-row[0], len(row[1])))
        return _clean_comment_text(candidates[0][1], max_chars=220)
    return _clean_comment_text(fallback, max_chars=220)


def _normalize_doi_variants(doi: str) -> list[str]:
    normalized = str(doi or "").strip().lower()
    if not normalized:
        return []
    normalized = normalized.removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    return list(
        dict.fromkeys(
            [
                normalized,
                normalized.replace(" ", ""),
                normalized.rstrip(".;,"),
            ]
        )
    )


def _author_hint_tokens(text: str, limit: int = 6) -> list[str]:
    seen: list[str] = []
    for token in re.findall(r"\b[A-Z][A-Za-z'`-]{2,}\b", text):
        cleaned = token.strip().lower()
        if cleaned in seen or cleaned in {"article", "journal", "nature", "creative", "commons"}:
            continue
        seen.append(cleaned)
        if len(seen) >= limit:
            break
    return seen


def _build_matching_hints(
    *,
    title: str,
    doi: str,
    year: str,
    authors: list[str],
    raw_text: str,
    doc_path: Path,
) -> dict[str, Any]:
    author_tokens = [tok for tok in [_clean_comment_text(str(item), max_chars=80).lower() for item in authors] if tok]
    if not author_tokens:
        author_tokens = _author_hint_tokens(raw_text)
    title_token_list = list(dict.fromkeys(_title_tokens(title, min_len=4)[:16]))
    source_name_tokens = list(dict.fromkeys(_title_tokens(doc_path.stem.replace("_", " ").replace("-", " "), min_len=4)[:12]))
    return {
        "normalized_title": " ".join(title_token_list[:12]).strip(),
        "title_tokens": title_token_list,
        "author_tokens": author_tokens[:8],
        "year": str(year or "").strip(),
        "doi_variants": _normalize_doi_variants(doi),
        "source_name_tokens": source_name_tokens,
    }


def _extract_key_sentences(text: str, predicate: re.Pattern[str], limit: int = 4) -> list[str]:
    out: list[str] = []
    for sentence in _split_sentences(text):
        if predicate.search(sentence):
            out.append(_clean_comment_text(sentence, max_chars=280))
        if len(out) >= limit:
            break
    return [row for row in out if row]


def _support_search_roots(manuscript_path: Path) -> list[Path]:
    roots: list[Path] = [manuscript_path.parent]
    if manuscript_path.parent.name.lower() in {"manuscript", "manuscripts"}:
        roots.append(manuscript_path.parent.parent)
    roots.append(manuscript_path.parent.parent)
    seen: set[Path] = set()
    ordered: list[Path] = []
    for root in roots:
        if not root or not root.exists():
            continue
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(resolved)
    return ordered


def _is_manuscript_variant(manuscript_path: Path, candidate: Path) -> bool:
    if candidate.resolve() == manuscript_path.resolve():
        return True
    manuscript_parts = {part.lower() for part in manuscript_path.parts}
    candidate_parts = {part.lower() for part in candidate.parts}
    if "manuscript" in manuscript_parts and "managed" in candidate_parts:
        return True
    manuscript_tokens = set(_title_tokens(manuscript_path.stem.replace("_", " ").replace("-", " "), min_len=4))
    candidate_tokens = set(_title_tokens(candidate.stem.replace("_", " ").replace("-", " "), min_len=4))
    overlap = manuscript_tokens & candidate_tokens
    return bool(manuscript_tokens and candidate_tokens and len(overlap) >= max(3, min(len(manuscript_tokens), len(candidate_tokens)) // 2))


def _discover_support_documents(manuscript_path: Path) -> list[Path]:
    candidates: list[Path] = []
    roots = _support_search_roots(manuscript_path)
    hint_terms = ("citation", "citations", "reference", "references", "support", "papers", "literature")
    for root in roots:
        for doc in root.rglob("*"):
            if not doc.is_file():
                continue
            if _is_blocked_path(doc):
                continue
            if doc.suffix.lower() not in MANUSCRIPT_SUFFIXES:
                continue
            if _is_manuscript_variant(manuscript_path, doc):
                continue
            parent_text = str(doc.parent).lower()
            score = 0
            if any(term in parent_text for term in hint_terms):
                score += 2
            if "manuscript" in parent_text:
                score -= 1
            if doc.stat().st_size > 120_000_000:
                continue
            candidates.append((score, doc))

    ranked = [doc for _score, doc in sorted(candidates, key=lambda row: (-row[0], str(row[1])))]
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in ranked:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
        if len(unique) >= MAX_SUPPORT_DOCS:
            break
    return unique


def _citation_mentions_by_sentence(content: str) -> list[dict[str, Any]]:
    body, _ = _references_split(content)
    mentions: list[dict[str, Any]] = []
    seen_markers: set[tuple[int, str, str]] = set()

    def _parse_numeric_values(text: str) -> list[int]:
        chunks = [chunk for chunk in re.split(r"[,\s;:/-]+", text) if chunk.strip().isdigit()]
        out: list[int] = []
        for chunk in chunks:
            value = int(chunk)
            if 0 < value <= 300 and value not in out:
                out.append(value)
        return out

    def _push(sentence_index: int, sentence: str, marker_raw: str, marker_type: str, marker_values: list[Any]) -> None:
        normalized_marker = _clean_comment_text(marker_raw, max_chars=48).lower()
        key = (sentence_index, marker_type, normalized_marker)
        if key in seen_markers:
            return
        seen_markers.add(key)
        mentions.append(
            {
                "sentence_index": sentence_index,
                "sentence": sentence,
                "marker_raw": marker_raw,
                "marker_type": marker_type,
                "marker_values": marker_values,
            }
        )

    for idx, sentence in enumerate(_split_sentences(body), start=1):
        if not _is_readable_text(sentence):
            continue
        bracketed = re.findall(r"\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\]", sentence)
        for marker in bracketed:
            ids = _parse_numeric_values(marker)
            if ids:
                _push(idx, sentence, f"[{marker}]", "numeric", ids)
        parenthetical_single = re.findall(r"\((\d{1,3})\)", sentence)
        for marker in parenthetical_single:
            ids = _parse_numeric_values(marker)
            if ids:
                _push(idx, sentence, f"({marker})", "numeric", ids)
        parenthetical_numeric = re.findall(r"\((\d{1,3}(?:\s*[,;:/-]\s*\d{1,3})+)\)", sentence)
        for marker in parenthetical_numeric:
            ids = _parse_numeric_values(marker)
            if ids:
                _push(idx, sentence, f"({marker})", "numeric", ids)
        superscript_style = re.findall(
            r"(?:[.;:]\s*|\s)(\d{1,3}(?:\s+\d{1,3}){1,5})(?=\s+[A-Z][a-z])",
            sentence,
        )
        for marker in superscript_style:
            ids = _parse_numeric_values(marker)
            if ids:
                _push(idx, sentence, marker, "numeric", ids)
        auth_year = re.findall(
            r"\(([A-Z][A-Za-z'`-]+(?:\s+et\s+al\.)?(?:,\s*[A-Z][A-Za-z'`-]+)*),?\s+((?:19|20)\d{2}[a-z]?)\)",
            sentence,
        )
        for author, year in auth_year:
            _push(idx, sentence, f"({author}, {year})", "author_year", [author, year])
    return mentions[:MAX_CITATION_VERIFICATION_SENTENCES]


def _match_reference_entries(mention: dict[str, Any], references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if mention.get("marker_type") == "numeric":
        ids = [int(x) for x in mention.get("marker_values", []) if isinstance(x, int)]
        return [ref for ref in references if int(ref.get("index", -1)) in ids]

    if mention.get("marker_type") == "author_year":
        values = mention.get("marker_values", [])
        if len(values) < 2:
            return []
        author = str(values[0]).split()[0].lower()
        year = str(values[1])[:4]
        matches = []
        for ref in references:
            raw = str(ref.get("raw", "")).lower()
            if author and author in raw and year and year in raw:
                matches.append(ref)
        return matches
    return []


def _pick_verification_model(model_plan: dict[str, Any]) -> str:
    stage_models = model_plan.get("stage_models", {})
    if not isinstance(stage_models, dict):
        stage_models = {}
    if model_plan.get("requested_mode") == "gemma_single":
        return str(model_plan.get("primary_model", "gemma4:26b"))
    available = [str(x) for x in model_plan.get("available_models", []) if str(x).strip()]
    gemma = _first_model_by_prefix(available, ["gemma4:26b", "gemma4:31b"])
    if gemma:
        return gemma
    return str(stage_models.get("final_arbitration", model_plan.get("primary_model", "unknown")))

def _ollama_request(
    endpoint: str,
    payload: dict[str, Any] | None = None,
    timeout_seconds: float = 45.0,
) -> dict[str, Any]:
    url = f"{DEFAULT_OLLAMA_URL}{endpoint}"
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url=url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body) if body else {}
        _log_network_event("ollama_request", "localhost", status="ok")
        return {"ok": True, "payload": parsed}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            detail = str(exc)
        _log_network_event("ollama_request", "localhost", status=f"http_error:{exc.code}")
        return {"ok": False, "error": f"HTTP {exc.code}: {detail}"}
    except Exception as exc:
        _log_network_event("ollama_request", "localhost", status="fail")
        return {"ok": False, "error": str(exc)}


def _ollama_list_models() -> list[str]:
    result = _ollama_request("/api/tags", payload=None, timeout_seconds=4.0)
    if not result.get("ok"):
        return []
    payload = result.get("payload", {})
    models = payload.get("models", []) if isinstance(payload, dict) else []
    out = []
    for row in models:
        if isinstance(row, dict):
            name = str(row.get("name", "")).strip()
            if name:
                out.append(name)
    return out


def _ollama_chat_completion(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 900,
    temperature: float = 0.2,
    timeout_seconds: float = 120.0,
    json_mode: bool = False,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature,
            "num_ctx": 8192,
            "top_p": 0.9,
        },
    }
    if json_mode:
        payload["format"] = "json"
    result = _ollama_request("/api/chat", payload=payload, timeout_seconds=timeout_seconds)
    if not result.get("ok"):
        err = str(result.get("error", "")).lower()
        if "think" in err and "unknown" in err:
            payload.pop("think", None)
            result = _ollama_request("/api/chat", payload=payload, timeout_seconds=timeout_seconds)
    if not result.get("ok"):
        return {
            "ok": False,
            "error": result.get("error", "ollama request failed"),
            "content": "",
        }
    response_payload = result.get("payload", {})
    message = response_payload.get("message", {}) if isinstance(response_payload, dict) else {}
    content = str(message.get("content", "")).strip() if isinstance(message, dict) else ""
    thinking = str(message.get("thinking", "")).strip() if isinstance(message, dict) else ""
    if not content and isinstance(response_payload, dict):
        content = str(response_payload.get("response", "")).strip()
    # Some Ollama/Gemma builds occasionally return empty chat payloads for
    # long prompts; retry once through /api/generate with an explicit flat prompt.
    if not content:
        generate_prompt = f"{system_prompt}\n\n{user_prompt}"
        generate = _ollama_request(
            "/api/generate",
            payload={
                "model": model,
                "stream": False,
                "think": False,
                "prompt": _truncate_chars(generate_prompt, 24000),
                **({"format": "json"} if json_mode else {}),
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                    "num_ctx": 8192,
                    "top_p": 0.9,
                },
            },
            timeout_seconds=timeout_seconds,
        )
        if not generate.get("ok"):
            err = str(generate.get("error", "")).lower()
            if "think" in err and "unknown" in err:
                generate = _ollama_request(
                    "/api/generate",
                    payload={
                        "model": model,
                        "stream": False,
                        "prompt": _truncate_chars(generate_prompt, 24000),
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": temperature,
                            "num_ctx": 8192,
                            "top_p": 0.9,
                        },
                    },
                    timeout_seconds=timeout_seconds,
                )
        if generate.get("ok"):
            generate_payload = generate.get("payload", {})
            if isinstance(generate_payload, dict):
                content = str(generate_payload.get("response", "")).strip()
                if content:
                    return {
                        "ok": True,
                        "content": content,
                        "raw": {"chat_raw": response_payload, "generate_raw": generate_payload},
                    }
    if not content:
        return {
            "ok": False,
            "error": "EMPTY_RESPONSE_THINKING_ONLY" if thinking else "EMPTY_RESPONSE",
            "content": "",
            "raw": response_payload,
        }
    return {
        "ok": True,
        "content": content,
        "raw": response_payload,
    }


def _run_model_probe(
    model: str,
    prompt: str,
    expect_json: bool = False,
    attempt_profile: str = "standard",
) -> dict[str, Any]:
    if not _check_ollama():
        return {"ok": False, "error": "OLLAMA_UNREACHABLE"}
    attempt_plans: dict[str, list[dict[str, Any]]] = {
        "standard": [
            {"max_tokens": 320, "temperature": 0.0, "timeout_seconds": 40.0, "max_prompt_chars": 9000},
            {"max_tokens": 700, "temperature": 0.0, "timeout_seconds": 70.0, "max_prompt_chars": 5200},
        ],
        "stage": [
            {"max_tokens": 320, "temperature": 0.0, "timeout_seconds": 18.0, "max_prompt_chars": 4200},
            {"max_tokens": 520, "temperature": 0.0, "timeout_seconds": 28.0, "max_prompt_chars": 3000},
        ],
        "verification": [
            {"max_tokens": 260, "temperature": 0.0, "timeout_seconds": 16.0, "max_prompt_chars": 3600},
            {"max_tokens": 420, "temperature": 0.0, "timeout_seconds": 24.0, "max_prompt_chars": 2600},
        ],
    }
    attempts = attempt_plans.get(attempt_profile, attempt_plans["standard"])
    last_error = "unknown"
    for idx, attempt in enumerate(attempts, start=1):
        attempt_prompt = _compact_prompt(
            prompt,
            attempt["max_prompt_chars"],
            expect_json=expect_json,
        )
        response = _ollama_chat_completion(
            model=model,
            system_prompt="You are a concise scientific reviewer. Follow the format exactly.",
            user_prompt=attempt_prompt,
            max_tokens=attempt["max_tokens"],
            temperature=attempt["temperature"],
            timeout_seconds=attempt["timeout_seconds"],
            json_mode=expect_json,
        )
        if not response.get("ok"):
            last_error = str(response.get("error", "unknown"))
            continue
        content = str(response.get("content", "")).strip()
        if expect_json:
            parsed = _extract_best_effort_object(content)
            if parsed is not None:
                return {"ok": True, "attempt": idx, "content": content, "parsed": parsed}
            repair = _ollama_chat_completion(
                model=model,
                system_prompt="Convert assistant output into exactly one JSON object. No extra text.",
                user_prompt=(
                    "Normalize this output into one JSON object only.\n\n"
                    + _compact_prompt(content, 5000, expect_json=False)
                ),
                max_tokens=420,
                temperature=0.0,
                timeout_seconds=35.0,
                json_mode=True,
            )
            if repair.get("ok"):
                repaired_content = str(repair.get("content", "")).strip()
                repaired_parsed = _extract_best_effort_object(repaired_content)
                if repaired_parsed is not None:
                    return {
                        "ok": True,
                        "attempt": idx,
                        "content": content,
                        "parsed": repaired_parsed,
                        "repaired": True,
                    }
            last_error = "JSON_PARSE_FAILURE"
            continue
        return {"ok": True, "attempt": idx, "content": content}
    return {"ok": False, "error": last_error}


def _diagnose_model_runtime(model: str) -> dict[str, Any]:
    short_prompt = "Reply with exactly: OK_GEMMA_SHORT"
    medium_prompt = (
        "You are reviewing a manuscript excerpt. Give 3 concise findings (one sentence each). "
        "Excerpt: The trial compared two interventions across 42 participants, but the control "
        "condition is not described and no confidence intervals are reported."
    )
    json_prompt = (
        "Return strict JSON with keys findings (array of strings, max 3) and risk_level "
        "(one of low|medium|high). Text: Methods mention p-values but do not report sample-size rationale."
    )
    ingest_prompt = (
        "Return strict JSON with keys title, abstract_summary, key_claims (max 3), methods_summary, "
        "quantitative_findings (max 2), limitations (max 2). "
        "Paper text: Abstract: We tested a catalytic flow process with 42 runs and observed 18% yield gain "
        "over baseline. Methods: randomized block design, control arm present, p<0.05."
    )
    citation_prompt = (
        "Return strict JSON with keys status (supported|too_broad|stronger_than_source|not_supported), "
        "confidence (low|medium|high), rationale (one sentence), fix (one sentence). "
        "Claim: The intervention consistently improved yield in all tested conditions. "
        "Evidence: Abstract reports improvement in 42 runs under one control condition."
    )
    long_review_prompt = (
        "Return strict JSON with key findings (array of max 3 objects with keys issue, fix, severity). "
        "Focus on method rigor and citation support.\n\n"
        + (
            "Manuscript excerpt: We developed an automated synthesis workflow and report improved throughput, "
            "yield, and reproducibility across multiple substrate classes. "
            "Methods mention a control arm and randomized blocks, but sampling and exclusions are not always explicit. "
            "Several claims cite [12], [13], and [27], while some quantitative statements appear uncited. "
            "Results describe 18 percent gain, 0.74 AUC, and reduced variance versus baseline.\n"
        )
        * 18
    )

    short = _run_model_probe(model, short_prompt, expect_json=False)
    medium = _run_model_probe(model, medium_prompt, expect_json=False)
    structured = _run_model_probe(model, json_prompt, expect_json=True)
    ingest = _run_model_probe(model, ingest_prompt, expect_json=True)
    citation = _run_model_probe(model, citation_prompt, expect_json=True)
    long_review = _run_model_probe(model, long_review_prompt, expect_json=True)

    def _status(row: dict[str, Any]) -> str:
        return "ok" if row.get("ok") else f"fail:{row.get('error', 'unknown')}"

    return {
        "model": model,
        "short_prompt": {"status": _status(short), "attempt": short.get("attempt"), "sample": str(short.get("content", ""))[:120]},
        "medium_prompt": {"status": _status(medium), "attempt": medium.get("attempt"), "sample": str(medium.get("content", ""))[:220]},
        "json_prompt": {"status": _status(structured), "attempt": structured.get("attempt"), "parsed": structured.get("parsed", {}) if structured.get("ok") else {}},
        "ingest_prompt": {"status": _status(ingest), "attempt": ingest.get("attempt"), "parsed": ingest.get("parsed", {}) if ingest.get("ok") else {}},
        "citation_prompt": {"status": _status(citation), "attempt": citation.get("attempt"), "parsed": citation.get("parsed", {}) if citation.get("ok") else {}},
        "long_review_prompt": {"status": _status(long_review), "attempt": long_review.get("attempt"), "parsed": long_review.get("parsed", {}) if long_review.get("ok") else {}},
        "usable": bool(short.get("ok") and medium.get("ok") and structured.get("ok")),
        "usable_for_ingest": bool(ingest.get("ok")),
        "usable_for_citation_verification": bool(citation.get("ok")),
        "usable_for_long_review": bool(long_review.get("ok")),
    }


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


def _parse_stage_findings(stage: str, parsed: dict[str, Any]) -> list[dict[str, Any]]:
    findings = parsed.get("findings", [])
    out: list[dict[str, Any]] = []
    if isinstance(findings, list):
        for row in findings[:6]:
            if isinstance(row, dict):
                issue = str(row.get("issue", "")).strip()
                if not issue:
                    continue
                fix = str(row.get("fix", "")).strip()
                severity = str(row.get("severity", "medium")).strip().lower()
                out.append(
                    {
                        "stage": stage,
                        "issue": issue,
                        "fix": fix,
                        "severity": severity if severity in {"high", "medium", "low"} else "medium",
                        "source": "model",
                    }
                )
            elif isinstance(row, str):
                issue = row.strip()
                if not issue:
                    continue
                out.append(
                    {
                        "stage": stage,
                        "issue": issue,
                        "fix": "",
                        "severity": "medium",
                        "source": "model",
                    }
                )
    return out


def _fallback_stage_findings(stage: str, reports: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def _push(issue: str, fix: str = "", severity: str = "medium") -> None:
        out.append(
            {
                "stage": stage,
                "issue": issue.strip(),
                "fix": fix.strip(),
                "severity": severity,
                "source": "heuristic_fallback",
            }
        )

    if stage in {"structural_review", "style_alignment"}:
        coherence = reports.get("coherence", {})
        for finding in coherence.get("findings", [])[:2]:
            _push(str(finding), "Tighten transitions and split dense sentences where needed.")
    elif stage == "high_level_review":
        journal = reports.get("journal_format", {})
        citations = reports.get("citations", {})
        for finding in journal.get("findings", [])[:1]:
            _push(str(finding), "Add the missing section elements in the manuscript front matter.")
        for finding in citations.get("findings", [])[:1]:
            _push(str(finding), "Add explicit citation markers near evidence-backed claims.")
    elif stage == "hostile_review":
        methods = reports.get("methods", {})
        for finding in methods.get("findings", [])[:2]:
            _push(str(finding), "Clarify controls, sample rationale, and statistical assumptions.", severity="high")
    elif stage == "methods_verification":
        methods = reports.get("methods", {})
        for finding in methods.get("findings", [])[:2]:
            _push(str(finding), "State exact thresholds, controls, and reproducibility details.")
    elif stage == "line_by_line_edits":
        line_edits = reports.get("line_edits", [])
        for row in line_edits[:2]:
            if not isinstance(row, dict):
                continue
            issue = str(row.get("issue", "")).strip() or "Long sentence reduces clarity."
            fix = str(row.get("suggested", "")).strip()
            if not _is_readable_text(fix):
                fix = "Split this sentence and keep only the key result and needed context."
            _push(issue, fix)
    elif stage in {"reconciliation", "final_arbitration"}:
        _push(
            "Findings require a tighter final synthesis with explicit confidence boundaries.",
            "Separate confirmed evidence from assumptions in the conclusion.",
            severity="high",
        )

    if not out:
        _push(
            "No high-confidence issue extracted for this stage.",
            "Run manual verification on this section to confirm quality.",
            severity="low",
        )
    return out


def _clean_comment_text(text: str, max_chars: int = 180) -> str:
    cleaned = re.sub(r"[^\x20-\x7E]", " ", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"^\[[^\]]+\]\s*", "", cleaned)
    cleaned = re.sub(r"(?i)^review round:\s*", "", cleaned)
    if len(cleaned) > max_chars:
        cleaned = cleaned[: max_chars - 1].rstrip() + "…"
    return cleaned


def _is_readable_text(text: str) -> bool:
    candidate = _clean_comment_text(text, max_chars=400)
    if not candidate:
        return False
    if len(candidate) <= 28:
        return True
    letters = len(re.findall(r"[A-Za-z]", candidate))
    alnum = len(re.findall(r"[A-Za-z0-9]", candidate))
    slash_count = candidate.count("\\")
    symbols = len(re.findall(r"[^A-Za-z0-9\s,.;:()\[\]{}%\-+]", candidate))
    alpha_tokens = re.findall(r"[A-Za-z]{3,}", candidate)
    if letters < 8:
        return False
    if alnum > 0 and (letters / max(alnum, 1)) < 0.35:
        return False
    if len(candidate) > 40 and (letters / max(len(candidate), 1)) < 0.45:
        return False
    if slash_count >= 6 and letters / max(len(candidate), 1) < 0.45:
        return False
    if len(candidate) > 40 and (symbols / max(len(candidate), 1)) > 0.28:
        return False
    if len(candidate.split()) >= 8 and len(alpha_tokens) < 4:
        return False
    return True


def _compose_visible_comments(details: list[dict[str, Any]]) -> list[str]:
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    ranked = sorted(
        details,
        key=lambda row: (
            severity_rank.get(str(row.get("severity", "medium")), 1),
            STAGE_ORDER.index(row.get("stage")) if row.get("stage") in STAGE_ORDER else len(STAGE_ORDER),
        ),
    )
    comments: list[str] = []
    seen: set[str] = set()
    stage_counts: dict[str, int] = {}
    for row in ranked:
        stage = str(row.get("stage", "unknown"))
        if stage == "citation_verification" and stage_counts.get(stage, 0) >= 4:
            continue
        issue = _clean_comment_text(str(row.get("issue", "")))
        if not _is_readable_text(issue):
            continue
        if not issue:
            continue
        key = issue.lower()
        if key in seen:
            continue
        seen.add(key)
        fix = _clean_comment_text(str(row.get("fix", "")), max_chars=140)
        if fix and not _is_readable_text(fix):
            fix = ""
        body = issue
        include_fix = bool(
            fix
            and len(fix) <= 95
            and str(row.get("severity", "medium")).lower() == "high"
        )
        if include_fix:
            body = f"{issue} Fix: {fix}"
        comments.append(body)
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
        if len(comments) >= MAX_STAGE_COMMENT_COUNT:
            break
    return comments


def _build_suggested_changes(details: list[dict[str, Any]], line_edits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    counter = 0
    seen_pairs: set[tuple[str, str, str]] = set()
    for row in details:
        fix = _clean_comment_text(str(row.get("fix", "")), max_chars=180)
        if not fix:
            continue
        issue = _clean_comment_text(str(row.get("issue", "")), max_chars=180)
        stage = str(row.get("stage", "unknown"))
        if not _is_readable_text(issue) or not _is_readable_text(fix):
            continue
        dedupe_key = (stage, issue.lower(), fix.lower())
        if dedupe_key in seen_pairs:
            continue
        seen_pairs.add(dedupe_key)
        counter += 1
        out.append(
            {
                "id": f"suggested-change-{counter}",
                "target": "body",
                "original": issue,
                "suggested": fix,
                "stage": stage,
                "severity": row.get("severity"),
            }
        )
        if len(out) >= 10:
            return out

    for row in line_edits[:6]:
        if not isinstance(row, dict):
            continue
        original = _clean_comment_text(str(row.get("original", "")), max_chars=220)
        suggested = _clean_comment_text(str(row.get("suggested", "")), max_chars=220)
        if not _is_readable_text(original) or not _is_readable_text(suggested):
            continue
        if not original or not suggested:
            continue
        dedupe_key = ("line_by_line_edits", original.lower(), suggested.lower())
        if dedupe_key in seen_pairs:
            continue
        seen_pairs.add(dedupe_key)
        counter += 1
        out.append(
            {
                "id": f"line-edit-{counter}",
                "target": "body",
                "original": original,
                "suggested": suggested,
                "stage": "line_by_line_edits",
                "severity": "medium",
            }
        )
        if len(out) >= 10:
            break
    return out


def _heuristic_support_ingest_record(doc_path: Path, text: str, reference_hints: list[dict[str, Any]]) -> dict[str, Any]:
    abstract = _extract_abstract_text(text)
    key_claims = _extract_key_sentences(
        text,
        re.compile(r"\b(show|demonstrat|suggest|indicat|improv|increase|decrease|associate)\b", flags=re.IGNORECASE),
        limit=4,
    )
    methods_summary = " ".join(
        _extract_key_sentences(
            text,
            re.compile(r"\b(method|protocol|assay|random|control|dataset|cohort|experiment)\b", flags=re.IGNORECASE),
            limit=2,
        )
    )[:420]
    quantitative = _extract_key_sentences(
        text,
        re.compile(r"\b\d+(?:\.\d+)?\b"),
        limit=3,
    )
    limitations = _extract_key_sentences(
        text,
        re.compile(r"\b(limit|caution|bias|weakness|future work|generaliz)\b", flags=re.IGNORECASE),
        limit=3,
    )
    top_terms = [term for term, _count in _word_freq(text, top_n=12)]
    doi_match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b", text)
    year_match = re.search(r"\b(19|20)\d{2}\b", text)

    title_line = _extract_title_line(
        text,
        doc_path.stem.replace("_", " ").replace("-", " "),
    )

    chunks: list[dict[str, Any]] = []
    raw_chunks = re.split(r"\n{2,}", _clean_for_analysis(text))
    for idx, chunk in enumerate(raw_chunks[:16], start=1):
        body = _clean_comment_text(chunk, max_chars=760)
        if len(body) < 50:
            continue
        keywords = [term for term in top_terms if term in body.lower()][:5]
        chunks.append({"chunk_id": f"{_safe_slug(doc_path.stem)}-{idx}", "text": body, "keywords": keywords})
        if len(chunks) >= 10:
            break

    anchor_terms: list[str] = []
    if doi_match:
        anchor_terms.append(doi_match.group(0))
    if year_match:
        anchor_terms.append(year_match.group(0))
    author_tokens = re.findall(r"\b[A-Z][a-z]{3,}\b", title_line)
    anchor_terms.extend(author_tokens[:3])
    for ref in reference_hints[:6]:
        doi = str(ref.get("doi", "")).strip()
        if doi:
            anchor_terms.append(doi)
    anchor_terms = list(dict.fromkeys([token for token in anchor_terms if token]))

    matching_hints = _build_matching_hints(
        title=title_line,
        doi=doi_match.group(0) if doi_match else "",
        year=year_match.group(0) if year_match else "",
        authors=author_tokens[:6],
        raw_text=text,
        doc_path=doc_path,
    )

    return {
        "identity": {
            "title": _clean_comment_text(title_line, max_chars=220),
            "doi": doi_match.group(0) if doi_match else "",
            "year": year_match.group(0) if year_match else "",
            "authors": author_tokens[:6],
        },
        "matching_hints": matching_hints,
        "abstract": abstract,
        "key_claims": key_claims[:4],
        "methods_summary": _clean_comment_text(methods_summary, max_chars=320),
        "quantitative_findings": quantitative[:4],
        "limitations": limitations[:4],
        "terminology_entities": top_terms,
        "citation_anchors": anchor_terms,
        "evidence_chunks": chunks,
    }


def _model_support_ingest_record(
    *,
    model: str,
    doc_path: Path,
    parsed_text: str,
    heuristic_record: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    prompt = (
        "You are ingesting a scientific support paper for downstream citation verification.\n"
        "Return strict JSON with keys: title, doi, year, authors (array), abstract, key_claims (array <=4), "
        "methods_summary, quantitative_findings (array <=4), limitations (array <=4), terminology_entities (array <=12), "
        "citation_anchors (array <=12), evidence_chunks (array <=8 objects with keys text and keywords).\n"
        "Do not include markdown.\n\n"
        f"File name: {doc_path.name}\n"
        f"Paper excerpt:\n{_truncate_chars(parsed_text, 9000)}"
    )
    probe = _run_model_probe(model, prompt, expect_json=True, attempt_profile="verification")
    if not probe.get("ok"):
        return heuristic_record, {"status": "fallback_heuristic", "error": str(probe.get("error", "unknown"))}

    parsed = probe.get("parsed", {})
    if not isinstance(parsed, dict):
        return heuristic_record, {"status": "fallback_heuristic", "error": "JSON_PARSE_FAILURE"}

    evidence_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(parsed.get("evidence_chunks", []) if isinstance(parsed.get("evidence_chunks"), list) else [], start=1):
        if not isinstance(row, dict):
            continue
        text = _clean_comment_text(str(row.get("text", "")), max_chars=760)
        if len(text) < 40:
            continue
        raw_keywords = row.get("keywords", [])
        keywords = [str(item).strip().lower() for item in raw_keywords if str(item).strip()] if isinstance(raw_keywords, list) else []
        evidence_rows.append(
            {
                "chunk_id": f"{_safe_slug(doc_path.stem)}-{idx}",
                "text": text,
                "keywords": keywords[:6],
            }
        )
        if len(evidence_rows) >= 8:
            break

    merged_identity = {
        "title": _clean_comment_text(str(parsed.get("title", "")), max_chars=220) or heuristic_record["identity"]["title"],
        "doi": _clean_comment_text(str(parsed.get("doi", "")), max_chars=120) or heuristic_record["identity"]["doi"],
        "year": _clean_comment_text(str(parsed.get("year", "")), max_chars=16) or heuristic_record["identity"]["year"],
        "authors": [
            _clean_comment_text(str(item), max_chars=80)
            for item in (parsed.get("authors", []) if isinstance(parsed.get("authors"), list) else [])
            if _clean_comment_text(str(item), max_chars=80)
        ][:10]
        or heuristic_record["identity"]["authors"],
    }

    merged = {
        "identity": merged_identity,
        "matching_hints": _build_matching_hints(
            title=merged_identity["title"],
            doi=merged_identity["doi"],
            year=merged_identity["year"],
            authors=merged_identity["authors"],
            raw_text=parsed_text,
            doc_path=doc_path,
        ),
        "abstract": _clean_comment_text(str(parsed.get("abstract", "")), max_chars=2000) or heuristic_record["abstract"],
        "key_claims": [
            _clean_comment_text(str(item), max_chars=280)
            for item in (parsed.get("key_claims", []) if isinstance(parsed.get("key_claims"), list) else [])
            if _clean_comment_text(str(item), max_chars=280)
        ][:4]
        or heuristic_record["key_claims"],
        "methods_summary": _clean_comment_text(str(parsed.get("methods_summary", "")), max_chars=420)
        or heuristic_record["methods_summary"],
        "quantitative_findings": [
            _clean_comment_text(str(item), max_chars=280)
            for item in (parsed.get("quantitative_findings", []) if isinstance(parsed.get("quantitative_findings"), list) else [])
            if _clean_comment_text(str(item), max_chars=280)
        ][:4]
        or heuristic_record["quantitative_findings"],
        "limitations": [
            _clean_comment_text(str(item), max_chars=280)
            for item in (parsed.get("limitations", []) if isinstance(parsed.get("limitations"), list) else [])
            if _clean_comment_text(str(item), max_chars=280)
        ][:4]
        or heuristic_record["limitations"],
        "terminology_entities": [
            _clean_comment_text(str(item), max_chars=80).lower()
            for item in (parsed.get("terminology_entities", []) if isinstance(parsed.get("terminology_entities"), list) else [])
            if _clean_comment_text(str(item), max_chars=80)
        ][:12]
        or heuristic_record["terminology_entities"],
        "citation_anchors": [
            _clean_comment_text(str(item), max_chars=120)
            for item in (parsed.get("citation_anchors", []) if isinstance(parsed.get("citation_anchors"), list) else [])
            if _clean_comment_text(str(item), max_chars=120)
        ][:12]
        or heuristic_record["citation_anchors"],
        "evidence_chunks": evidence_rows or heuristic_record["evidence_chunks"],
    }
    return merged, {"status": "ok", "attempt": probe.get("attempt"), "error": ""}


def _read_cached_ingest(cache_file: Path) -> dict[str, Any] | None:
    if not cache_file.exists():
        return None
    try:
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def _write_cached_ingest(cache_file: Path, payload: dict[str, Any]) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ingest_support_documents(
    *,
    manuscript_path: Path | None,
    reasoning_mode: str,
    model_plan: dict[str, Any],
    reference_entries: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    if manuscript_path is None or not manuscript_path.exists():
        report = {
            "available_support_docs": 0,
            "selected_support_docs": 0,
            "ingested_docs": 0,
            "cache_reused_docs": 0,
            "cache_refreshed_docs": 0,
            "failed_docs": 0,
            "selection_basis": "no_manuscript_path",
            "reasoning_mode": reasoning_mode,
        }
        return report, {"used_sources": [], "unused_sources": [], "status": "no_manuscript_path"}, [], {
            "stage": "supporting_paper_ingest",
            "model": "",
            "status": "skipped",
            "error": "missing manuscript path",
            "finding_count": 0,
        }

    support_docs = _discover_support_documents(manuscript_path)
    ingest_model = _pick_verification_model(model_plan)
    usable_model_probe = _diagnose_model_runtime(ingest_model) if ingest_model else {"usable_for_ingest": False}
    use_model = bool(usable_model_probe.get("usable_for_ingest"))
    docs: list[dict[str, Any]] = []
    reused = 0
    refreshed = 0
    failed = 0

    for doc_path in support_docs:
        try:
            fingerprint = _file_fingerprint(doc_path)
            cache_file = SUPPORT_CACHE_ROOT / f"{_sha1_text(fingerprint['path'])}.json"
            cached = _read_cached_ingest(cache_file)
            if (
                cached
                and cached.get("schema_version") == INGEST_SCHEMA_VERSION
                and cached.get("source_fingerprint") == fingerprint
                and cached.get("ingest", {}).get("model_requested") == ingest_model
            ):
                cached["ingest"]["cache_status"] = "reused"
                docs.append(cached)
                reused += 1
                continue

            parsed = _parse_manuscript(doc_path)
            parsed_text = _clean_for_analysis(parsed.cleaned_text)
            heuristic = _heuristic_support_ingest_record(doc_path, parsed_text, reference_entries)

            model_payload = heuristic
            ingest_meta = {"status": "fallback_heuristic", "attempt": None, "error": "model_not_used"}
            if use_model:
                model_payload, ingest_meta = _model_support_ingest_record(
                    model=ingest_model,
                    doc_path=doc_path,
                    parsed_text=parsed_text,
                    heuristic_record=heuristic,
                )

            payload = {
                "schema_version": INGEST_SCHEMA_VERSION,
                "source_fingerprint": fingerprint,
                "source_provenance": {
                    "path": str(doc_path),
                    "parse_engine": parsed.parse_engine,
                    "warnings": parsed.parse_warnings,
                },
                "identity": model_payload["identity"],
                "matching_hints": model_payload.get("matching_hints", heuristic.get("matching_hints", {})),
                "abstract": model_payload["abstract"],
                "key_claims": model_payload["key_claims"],
                "methods_summary": model_payload["methods_summary"],
                "quantitative_findings": model_payload["quantitative_findings"],
                "limitations": model_payload["limitations"],
                "terminology_entities": model_payload["terminology_entities"],
                "citation_anchors": model_payload["citation_anchors"],
                "evidence_chunks": model_payload["evidence_chunks"],
                "ingest": {
                    "timestamp": _now_iso(),
                    "model_requested": ingest_model,
                    "model_mode": "model_assisted" if use_model else "heuristic_only",
                    "cache_status": "refreshed" if cached else "new",
                    "status": ingest_meta.get("status", "fallback_heuristic"),
                    "error": ingest_meta.get("error", ""),
                },
            }
            _write_cached_ingest(cache_file, payload)
            docs.append(payload)
            refreshed += 1 if cached else 0
        except Exception as exc:
            failed += 1
            docs.append(
                {
                    "schema_version": INGEST_SCHEMA_VERSION,
                    "source_fingerprint": {"path": str(doc_path)},
                    "source_provenance": {"path": str(doc_path)},
                    "identity": {"title": doc_path.name, "doi": "", "year": "", "authors": []},
                    "matching_hints": {},
                    "abstract": "",
                    "key_claims": [],
                    "methods_summary": "",
                    "quantitative_findings": [],
                    "limitations": [],
                    "terminology_entities": [],
                    "citation_anchors": [],
                    "evidence_chunks": [],
                    "ingest": {"timestamp": _now_iso(), "status": "failed", "error": str(exc), "cache_status": "failed"},
                }
            )

    report = {
        "available_support_docs": len(support_docs),
        "selected_support_docs": len(support_docs),
        "ingested_docs": len([row for row in docs if row.get("ingest", {}).get("status") != "failed"]),
        "cache_reused_docs": reused,
        "cache_refreshed_docs": refreshed,
        "failed_docs": failed,
        "selection_basis": "local_discovery_near_manuscript",
        "reasoning_mode": reasoning_mode,
        "model_requested": ingest_model,
        "model_usable_for_ingest": bool(usable_model_probe.get("usable_for_ingest")),
        "ingest_mode": "model_assisted" if use_model else "heuristic_only",
    }
    usage = {
        "used_sources": [],
        "unused_sources": [row.get("source_provenance", {}).get("path", "") for row in docs],
        "status": "pending_citation_linkage",
    }
    stage = {
        "stage": "supporting_paper_ingest",
        "model": ingest_model,
        "status": (
            "ok"
            if report["ingested_docs"] > 0 and use_model
            else ("heuristic_only" if report["ingested_docs"] > 0 else "fallback_error")
        ),
        "error": (
            ""
            if report["ingested_docs"] > 0 and use_model
            else ("ingest_model_unusable" if report["ingested_docs"] > 0 else "no_support_documents_ingested")
        ),
        "finding_count": report["ingested_docs"],
    }
    return report, usage, docs, stage


def _openalex_abstract_from_inverted_index(inverted: dict[str, Any]) -> str:
    if not isinstance(inverted, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for token, offsets in inverted.items():
        if not isinstance(offsets, list):
            continue
        for offset in offsets:
            if isinstance(offset, int):
                positions.append((offset, token))
    if not positions:
        return ""
    ordered = [token for _idx, token in sorted(positions, key=lambda row: row[0])]
    return " ".join(ordered).strip()


def _fetch_openalex_metadata(reference: dict[str, Any]) -> dict[str, Any] | None:
    doi = str(reference.get("doi", "")).strip()
    title_hint = str(reference.get("title_hint", "")).strip()
    urls = []
    if doi:
        encoded = urllib.parse.quote(f"https://doi.org/{doi}", safe="")
        urls.append(f"https://api.openalex.org/works/{encoded}")
    if title_hint:
        urls.append(f"https://api.openalex.org/works?search={urllib.parse.quote(title_hint)}&per-page=1")

    for url in urls:
        try:
            host = urllib.parse.urlparse(url).hostname or "api.openalex.org"
            _log_network_event("openalex_lookup", host, protocol="https", status="start")
            with urllib.request.urlopen(url, timeout=6.5) as response:
                payload_raw = response.read().decode("utf-8")
            _log_network_event("openalex_lookup", host, protocol="https", status="ok")
            payload = json.loads(payload_raw)
            if isinstance(payload, dict) and payload.get("abstract_inverted_index"):
                return payload
            results = payload.get("results") if isinstance(payload, dict) else None
            if isinstance(results, list) and results:
                row = results[0]
                if isinstance(row, dict):
                    return row
        except Exception:
            _log_network_event("openalex_lookup", "api.openalex.org", protocol="https", status="fail")
            continue
    return None


def _lexical_overlap_ratio(a: str, b: str) -> float:
    tokens_a = {tok for tok in re.findall(r"\b[a-zA-Z]{4,}\b", a.lower())}
    tokens_b = {tok for tok in re.findall(r"\b[a-zA-Z]{4,}\b", b.lower())}
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / max(1, len(tokens_a))


def _reference_matching_hints(reference: dict[str, Any]) -> dict[str, Any]:
    raw = str(reference.get("raw", ""))
    doi = str(reference.get("doi", "")).strip()
    title_hint = str(reference.get("title_hint", "")).strip()
    author_hint = str(reference.get("author_hint", "")).strip()
    year = str(reference.get("year", "")).strip()
    return {
        "doi_variants": _normalize_doi_variants(doi),
        "title_tokens": list(dict.fromkeys(_title_tokens(title_hint or raw, min_len=4)[:18])),
        "author_tokens": [author_hint.lower()] if author_hint else _author_hint_tokens(raw, limit=6),
        "year": year,
    }


def _score_support_reference_match(reference: dict[str, Any], support_doc: dict[str, Any]) -> tuple[float, list[str]]:
    ref_hints = _reference_matching_hints(reference)
    identity = support_doc.get("identity", {}) if isinstance(support_doc.get("identity"), dict) else {}
    hints = support_doc.get("matching_hints", {}) if isinstance(support_doc.get("matching_hints"), dict) else {}
    anchors = [str(token).strip().lower() for token in support_doc.get("citation_anchors", []) if str(token).strip()]

    support_dois = set(_normalize_doi_variants(str(identity.get("doi", ""))))
    support_dois.update(str(item).strip().lower() for item in hints.get("doi_variants", []) if str(item).strip())
    ref_dois = set(str(item).strip().lower() for item in ref_hints.get("doi_variants", []) if str(item).strip())

    support_title_tokens = set(str(item).strip().lower() for item in hints.get("title_tokens", []) if str(item).strip())
    if not support_title_tokens:
        support_title_tokens = set(_title_tokens(str(identity.get("title", "")), min_len=4))
    support_title_tokens.update(str(item).strip().lower() for item in hints.get("source_name_tokens", []) if str(item).strip())

    support_author_tokens = set(str(item).strip().lower() for item in hints.get("author_tokens", []) if str(item).strip())
    ref_title_tokens = set(str(item).strip().lower() for item in ref_hints.get("title_tokens", []) if str(item).strip())
    ref_author_tokens = set(str(item).strip().lower() for item in ref_hints.get("author_tokens", []) if str(item).strip())
    ref_year = str(ref_hints.get("year", "")).strip()
    support_year = str(hints.get("year", "") or identity.get("year", "")).strip()

    score = 0.0
    basis: list[str] = []

    if ref_dois and support_dois and ref_dois & support_dois:
        score += 6.0
        basis.append("doi")

    title_overlap = len(ref_title_tokens & support_title_tokens)
    if title_overlap:
        score += min(4.0, title_overlap * 0.7)
        basis.append(f"title:{title_overlap}")

    author_overlap = len(ref_author_tokens & support_author_tokens)
    if author_overlap:
        score += min(2.0, author_overlap * 0.9)
        basis.append(f"author:{author_overlap}")
    elif ref_author_tokens and any(token in anchors for token in ref_author_tokens):
        score += 1.3
        basis.append("author_anchor")

    if ref_year and support_year and ref_year == support_year:
        score += 1.2
        basis.append("year")

    if ref_dois and any(any(doi in anchor for anchor in anchors) for doi in ref_dois):
        score += 1.5
        basis.append("doi_anchor")

    return score, basis


def _map_support_to_reference(reference: dict[str, Any], support_docs: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    best: tuple[float, dict[str, Any], list[str]] | None = None
    for doc in support_docs:
        score, basis = _score_support_reference_match(reference, doc)
        if best is None or score > best[0]:
            best = (score, doc, basis)
    if best and best[0] >= 2.2:
        return best[1], {"score": round(best[0], 2), "basis": best[2]}
    return None, {"score": round(best[0], 2) if best else 0.0, "basis": best[2] if best else []}


def _verify_citation_claim_with_model(
    *,
    model: str,
    sentence: str,
    citation_marker: str,
    reference_raw: str,
    evidence_text: str,
    evidence_basis: str,
) -> dict[str, Any] | None:
    prompt = (
        "Return strict JSON with keys status, confidence, rationale, fix.\n"
        "Allowed status values: supported, too_broad, stronger_than_source, not_supported, abstract_only, unverifiable.\n"
        "Allowed confidence values: low, medium, high.\n"
        f"Sentence: {sentence}\n"
        f"Citation marker: {citation_marker}\n"
        f"Reference entry: {reference_raw}\n"
        f"Evidence basis: {evidence_basis}\n"
        f"Evidence excerpt:\n{_truncate_chars(evidence_text, 2600)}"
    )
    result = _run_model_probe(model, prompt, expect_json=True, attempt_profile="verification")
    if not result.get("ok"):
        return None
    parsed = result.get("parsed", {})
    if not isinstance(parsed, dict):
        return None
    status = str(parsed.get("status", "")).strip().lower()
    confidence = str(parsed.get("confidence", "medium")).strip().lower()
    rationale = _clean_comment_text(str(parsed.get("rationale", "")), max_chars=220)
    fix = _clean_comment_text(str(parsed.get("fix", "")), max_chars=180)
    status_map = {
        "appropriate": "supported",
        "abstract_only_unclear": "abstract_only",
        "could_not_verify_support": "unverifiable",
        "cited_source_unavailable": "unverifiable",
    }
    status = status_map.get(status, status)
    if status not in {"supported", "too_broad", "stronger_than_source", "not_supported", "abstract_only", "unverifiable"}:
        return None
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"
    return {
        "status": status,
        "confidence": confidence,
        "rationale": rationale,
        "fix": fix,
    }


def _run_line_by_line_citation_verification(
    *,
    content: str,
    references: list[dict[str, Any]],
    support_docs: list[dict[str, Any]],
    model_plan: dict[str, Any],
    allow_abstract_fallback: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    mentions = _citation_mentions_by_sentence(content)
    body_text, _ = _references_split(content)
    body_sentences = _split_sentences(body_text)
    verification_model = _pick_verification_model(model_plan)
    model_probe = _diagnose_model_runtime(verification_model) if verification_model else {"usable_for_citation_verification": False}
    model_ok = bool(model_probe.get("usable_for_citation_verification"))

    used_sources: set[str] = set()
    ledger_entries: list[dict[str, Any]] = []
    citation_details: list[dict[str, Any]] = []
    detail_seen: set[tuple[str, str]] = set()
    detail_counts: dict[str, int] = {}
    detail_quota = {
        "too_broad": 4,
        "stronger_than_source": 4,
        "not_supported": 5,
        "abstract_only": 5,
        "unverifiable": 5,
        "missing_citation": 6,
    }

    def _append_citation_detail(
        *,
        status_key: str,
        severity: str,
        issue: str,
        fix: str,
    ) -> None:
        clean_issue = _clean_comment_text(issue, max_chars=180)
        clean_fix = _clean_comment_text(fix, max_chars=150)
        if not _is_readable_text(clean_issue):
            return
        if clean_fix and not _is_readable_text(clean_fix):
            clean_fix = ""
        if detail_counts.get(status_key, 0) >= detail_quota.get(status_key, 3):
            return
        dedupe_key = (status_key, clean_issue.lower())
        if dedupe_key in detail_seen:
            return
        detail_seen.add(dedupe_key)
        detail_counts[status_key] = detail_counts.get(status_key, 0) + 1
        citation_details.append(
            {
                "stage": "citation_verification",
                "severity": severity,
                "issue": clean_issue,
                "fix": clean_fix or "Revise the sentence or add a citation with direct support.",
                "source": "citation_verifier",
            }
        )

    mention_sentence_ids = {int(row.get("sentence_index", -1)) for row in mentions if str(row.get("sentence_index", "")).isdigit()}

    for mention in mentions:
        sentence = str(mention.get("sentence", "")).strip()
        marker = str(mention.get("marker_raw", "")).strip()
        matched_refs = _match_reference_entries(mention, references)
        if not matched_refs:
            ledger_entries.append(
                {
                    "sentence_index": mention.get("sentence_index"),
                    "sentence": _clean_comment_text(sentence, max_chars=180),
                    "marker": marker,
                    "status": "unverifiable",
                    "confidence": "low",
                    "evidence_basis": "none",
                    "reference_ids": [],
                    "model": verification_model,
                }
            )
            marker_text = marker or "[unknown]"
            sentence_snippet = _clean_comment_text(sentence, max_chars=92)
            _append_citation_detail(
                status_key="unverifiable",
                severity="high",
                issue=f"Citation marker {marker_text} could not be mapped for this sentence: {sentence_snippet}",
                fix="Check numbering/author-year format and ensure this citation appears in References.",
            )
            continue

        for ref in matched_refs:
            support, support_match = _map_support_to_reference(ref, support_docs)
            evidence_basis = "full_paper_cache"
            evidence_text = ""
            support_path = ""
            if support:
                support_path = str(support.get("source_provenance", {}).get("path", ""))
                used_sources.add(support_path)
                abstract = str(support.get("abstract", ""))
                key_claims = " ".join(str(x) for x in support.get("key_claims", [])[:3])
                methods = str(support.get("methods_summary", ""))
                evidence_chunks = " ".join(str(row.get("text", "")) for row in support.get("evidence_chunks", [])[:2] if isinstance(row, dict))
                evidence_text = " ".join([abstract, key_claims, methods, evidence_chunks]).strip()
            else:
                evidence_basis = "none"

            if not evidence_text and allow_abstract_fallback:
                metadata = _fetch_openalex_metadata(ref)
                if metadata:
                    abstract = _openalex_abstract_from_inverted_index(metadata.get("abstract_inverted_index", {}))
                    if abstract:
                        evidence_text = abstract
                        evidence_basis = "abstract_only"

            status = "unverifiable"
            confidence = "low"
            rationale = ""
            fix = ""

            if not evidence_text:
                status = "unverifiable"
                fix = "Provide accessible source text or tighten this claim to verifiable evidence."
            else:
                model_result = None
                if model_ok:
                    model_result = _verify_citation_claim_with_model(
                        model=verification_model,
                        sentence=sentence,
                        citation_marker=marker,
                        reference_raw=str(ref.get("raw", "")),
                        evidence_text=evidence_text,
                        evidence_basis=evidence_basis,
                    )
                if model_result:
                    status = str(model_result.get("status", "unverifiable"))
                    confidence = str(model_result.get("confidence", "medium"))
                    rationale = str(model_result.get("rationale", ""))
                    fix = str(model_result.get("fix", ""))
                else:
                    overlap = _lexical_overlap_ratio(sentence, evidence_text)
                    if evidence_basis == "abstract_only":
                        status = "abstract_only"
                        confidence = "low"
                        if overlap < 0.12:
                            fix = "Checked against abstract only; support is still unclear for this sentence."
                        else:
                            fix = "Checked against abstract only; add full-source support if available."
                    elif overlap >= 0.2:
                        status = "supported"
                        confidence = "medium"
                    elif overlap >= 0.12:
                        status = "too_broad"
                        confidence = "low"
                        fix = "Narrow the claim or cite a source that directly supports the full statement."
                    else:
                        status = "not_supported"
                        confidence = "low"
                        fix = "Add a more directly supporting citation or weaken this claim."

            if evidence_basis == "abstract_only" and status not in {"unverifiable"}:
                status = "abstract_only"
                if confidence == "high":
                    confidence = "medium"
                if not fix:
                    fix = "Checked against abstract only; verify with full text before asserting this claim strongly."

            ledger_entry = {
                "sentence_index": mention.get("sentence_index"),
                "sentence": _clean_comment_text(sentence, max_chars=180),
                "marker": marker,
                "status": status,
                "confidence": confidence,
                "evidence_basis": evidence_basis,
                "reference_ids": [ref.get("id")],
                "reference_raw": _clean_comment_text(str(ref.get("raw", "")), max_chars=260),
                "support_source_path": support_path,
                "support_match_score": support_match.get("score", 0.0),
                "support_match_basis": support_match.get("basis", []),
                "source_resolution": "local_cache" if support_path else evidence_basis,
                "model": verification_model,
                "rationale": _clean_comment_text(rationale, max_chars=220),
                "fix": _clean_comment_text(fix, max_chars=180),
            }
            ledger_entries.append(ledger_entry)

            if status in {"too_broad", "stronger_than_source", "not_supported", "abstract_only", "unverifiable"}:
                issue_map = {
                    "too_broad": "This citation may be too broad for the full strength of the sentence.",
                    "stronger_than_source": "The sentence appears stronger than what this source supports.",
                    "not_supported": "This citation may not support the exact claim in this sentence.",
                    "abstract_only": "Checked against abstract only; support for this sentence may be incomplete.",
                    "unverifiable": "This sentence could not be verified against an accessible source.",
                }
                sentence_snippet = _clean_comment_text(sentence, max_chars=90)
                _append_citation_detail(
                    status_key=status,
                    severity="high" if status in {"not_supported", "unverifiable"} else "medium",
                    issue=f"{issue_map.get(status, 'Citation support is unclear for this sentence.')} Sentence: {sentence_snippet}",
                    fix=_clean_comment_text(fix, max_chars=150)
                    or "Revise the sentence or add a citation with direct support.",
                )

    # Flag likely evidence-bearing sentences that lack citation markers.
    missing_citation_count = 0
    for idx, sentence in enumerate(body_sentences, start=1):
        if idx in mention_sentence_ids:
            continue
        if not _is_readable_text(sentence):
            continue
        if len(sentence.split()) < 9:
            continue
        if not re.search(r"\b(show|found|observed|demonstrat|indicat|suggest|increase|decrease|significant|p\s*[<=>]|\d+\.\d+|\d+%)\b", sentence, flags=re.IGNORECASE):
            continue
        ledger_entries.append(
            {
                "sentence_index": idx,
                "sentence": _clean_comment_text(sentence, max_chars=180),
                "marker": "",
                "status": "missing_citation",
                "confidence": "medium",
                "evidence_basis": "none",
                "reference_ids": [],
                "reference_raw": "",
                "support_source_path": "",
                "model": verification_model,
                "rationale": "",
                "fix": "Add a citation for this sentence or soften the claim.",
            }
        )
        sentence_snippet = _clean_comment_text(sentence, max_chars=92)
        _append_citation_detail(
            status_key="missing_citation",
            severity="medium",
            issue=f"This sentence may need a citation: {sentence_snippet}",
            fix="Add a citation that directly supports this sentence.",
        )
        missing_citation_count += 1
        if missing_citation_count >= 12:
            break

    total_ledger_entries = len(ledger_entries)
    if len(ledger_entries) > 120:
        ledger_entries = ledger_entries[:120]
    if len(citation_details) > 40:
        citation_details = citation_details[:40]

    status_counts: dict[str, int] = {}
    for row in ledger_entries:
        key = str(row.get("status", "unknown"))
        status_counts[key] = status_counts.get(key, 0) + 1

    claim_summary = {
        "claim_count": len(mentions),
        "claims_checked": len(ledger_entries),
        "likely_overstated": status_counts.get("too_broad", 0) + status_counts.get("stronger_than_source", 0),
        "unsupported_or_unclear": status_counts.get("not_supported", 0)
        + status_counts.get("abstract_only", 0)
        + status_counts.get("unverifiable", 0),
        "missing_citation": status_counts.get("missing_citation", 0),
        "status": "line_by_line",
        "status_counts": status_counts,
    }
    verification_ledger = {
        "status": "line_by_line",
        "entries": ledger_entries,
        "total_entries_before_truncation": total_ledger_entries,
        "entries_truncated": total_ledger_entries > len(ledger_entries),
        "reference_count": len(references),
        "mention_count": len(mentions),
        "model": verification_model,
        "model_usable": model_ok,
        "allow_abstract_fallback": allow_abstract_fallback,
    }
    support_usage = {
        "used_sources": sorted([path for path in used_sources if path]),
        "unused_sources": sorted(
            [
                str(row.get("source_provenance", {}).get("path", ""))
                for row in support_docs
                if str(row.get("source_provenance", {}).get("path", "")) not in used_sources
            ]
        ),
        "status": "line_by_line_linked",
    }
    stage = {
        "stage": "citation_verification",
        "model": verification_model,
        "status": (
            "ok"
            if ledger_entries and model_ok
            else ("heuristic_only" if ledger_entries else "fallback_error")
        ),
        "error": (
            ""
            if ledger_entries and model_ok
            else ("citation_model_unusable" if ledger_entries else "no_citation_mentions_detected")
        ),
        "finding_count": len(citation_details),
    }
    assertion_ledger = {
        "claim_count": total_ledger_entries,
        "claims": [
            {
                "sentence_index": row.get("sentence_index"),
                "sentence": row.get("sentence"),
                "marker": row.get("marker"),
            }
            for row in ledger_entries[:300]
        ],
    }
    return verification_ledger, citation_details, support_usage, claim_summary, stage, assertion_ledger


def _stage_prompt(stage: str, content: str, section_map: dict[str, str]) -> str:
    section_summary = ", ".join(sorted(section_map.keys())[:10]) if section_map else "Body"
    excerpt = _truncate_chars(content, 12000)
    focus_map = {
        "structural_review": "Check section structure, logical order, and missing critical section framing.",
        "high_level_review": "Assess claim-evidence alignment and overstatement risk across the manuscript.",
        "hostile_review": "Act as an adversarial reviewer and surface fragile assumptions or unsupported leaps.",
        "methods_verification": "Audit method rigor, controls, reproducibility details, and statistical clarity.",
        "line_by_line_edits": "Find sentence-level edits that materially improve precision and readability.",
        "style_alignment": "Tighten wording and remove ambiguity without changing scientific meaning.",
        "reconciliation": "Reconcile conflicting findings and identify highest-priority revisions.",
        "final_arbitration": "Produce final editorial priorities and acceptance risk signals.",
    }
    focus = focus_map.get(stage, "Review the manuscript and produce concise actionable findings.")
    return (
        "Return strict JSON only with this schema:\n"
        "{\n"
        '  "findings": [\n'
        "    {\"issue\": \"short direct issue\", \"fix\": \"short concrete fix\", \"severity\": \"high|medium|low\"}\n"
        "  ]\n"
        "}\n"
        "Rules:\n"
        "- max 4 findings\n"
        "- each issue must be one sentence\n"
        "- each fix must be one sentence\n"
        "- no markdown, no prose outside JSON\n\n"
        f"Stage: {stage}\n"
        f"Detected sections: {section_summary}\n"
        f"Focus: {focus}\n\n"
        f"Manuscript excerpt:\n{excerpt}"
    )


def _resolve_stage_models(
    *,
    reasoning_mode_requested: str,
    profile: str,
    explicit_model_target: str | None,
    available_models: list[str],
) -> dict[str, Any]:
    mode = reasoning_mode_requested.strip().lower()
    normalized_models = available_models
    has_gemma26 = _contains_prefix(normalized_models, "gemma4:26b")
    has_gemma31 = _contains_prefix(normalized_models, "gemma4:31b")
    notes: list[str] = []

    if mode not in {"moe", "gemma_single"}:
        mode = "gemma_single" if profile in {"one_big_model", "full_manuscript_final_pass", "gemma4_26b", "gemma4_31b"} else "moe"

    if mode == "gemma_single":
        preferred: str | None = None
        if explicit_model_target and _contains_prefix(normalized_models, explicit_model_target):
            preferred = explicit_model_target
        elif has_gemma26:
            preferred = _first_model_by_prefix(normalized_models, ["gemma4:26b"])
        elif has_gemma31:
            preferred = _first_model_by_prefix(normalized_models, ["gemma4:31b"])

        degraded = False
        fallback_reason = ""
        if not preferred:
            degraded = True
            preferred = explicit_model_target or _largest_model(normalized_models) or "gemma4:26b"
            fallback_reason = "Gemma 4 unavailable; requested single-model Gemma mode degraded to fallback model."
            notes.append(fallback_reason)

        stage_models = {stage: preferred for stage in STAGE_ORDER}
        return {
            "requested_mode": "gemma_single",
            "effective_mode": "gemma_single" if not degraded else "gemma_single_degraded",
            "degraded": degraded,
            "fallback_reason": fallback_reason,
            "stage_models": stage_models,
            "notes": notes,
            "available_models": normalized_models,
            "primary_model": preferred,
            "support_ingest_model": preferred,
            "citation_verification_model": preferred,
        }

    stage_models: dict[str, str] = {}
    for stage in STAGE_ORDER:
        picked = _first_model_by_prefix(normalized_models, STAGE_TO_MODEL_CANDIDATES.get(stage, []))
        if not picked:
            stage_defaults = STAGE_TO_MODEL_CANDIDATES.get(stage, [])
            picked = stage_defaults[0] if stage_defaults else None
        if not picked:
            picked = explicit_model_target or _largest_model(normalized_models) or "unknown"
        stage_models[stage] = picked

    support_ingest_model = _first_model_by_prefix(normalized_models, ["gemma4:26b", "gemma4:31b"])
    if not support_ingest_model:
        support_ingest_model = stage_models.get("final_arbitration", explicit_model_target or "unknown")

    citation_verification_model = support_ingest_model
    if not citation_verification_model:
        citation_verification_model = stage_models.get("methods_verification", explicit_model_target or "unknown")

    return {
        "requested_mode": "moe",
        "effective_mode": "moe",
        "degraded": False,
        "fallback_reason": "",
        "stage_models": stage_models,
        "notes": notes,
        "available_models": normalized_models,
        "primary_model": stage_models.get("final_arbitration", explicit_model_target or "unknown"),
        "support_ingest_model": support_ingest_model,
        "citation_verification_model": citation_verification_model,
    }


def _generate_stage_reviews(
    *,
    content: str,
    profile: str,
    reasoning_mode: str,
    model_target: str | None = None,
    section_map: dict[str, str] | None = None,
    manuscript_path: str | None = None,
    allow_abstract_fallback: bool = True,
) -> dict[str, Any]:
    manuscript_file = Path(manuscript_path).resolve() if manuscript_path else None
    source_text = content
    if manuscript_file and manuscript_file.exists():
        try:
            source_text = _parse_manuscript(manuscript_file).cleaned_text or content
        except Exception:
            source_text = content
    clean = _clean_for_analysis(source_text)
    section_map = section_map or _simple_section_map(clean)

    terminology = _analyze_terminology(clean)
    coherence = _analyze_coherence(clean)
    methods = _analyze_methods(clean)
    figures_tables = _analyze_figures_tables(clean)
    citations = _analyze_citations(clean)
    journal_format = _analyze_journal_format(clean)
    line_edits_payload = _generate_line_edits(clean)
    line_edits = line_edits_payload.get("line_edits", [])

    reports = {
        "terminology": terminology,
        "coherence": coherence,
        "methods": methods,
        "figures_tables": figures_tables,
        "citations": citations,
        "journal_format": journal_format,
        "line_edits": line_edits if isinstance(line_edits, list) else [],
    }

    model_plan = _resolve_stage_models(
        reasoning_mode_requested=reasoning_mode,
        profile=profile,
        explicit_model_target=model_target,
        available_models=_ollama_list_models(),
    )

    references = _extract_reference_entries(clean)
    support_ingest_report, support_usage_ledger, support_docs, support_stage = _ingest_support_documents(
        manuscript_path=manuscript_file,
        reasoning_mode=reasoning_mode,
        model_plan=model_plan,
        reference_entries=references,
    )
    (
        citation_verification_ledger,
        citation_details,
        citation_support_usage,
        claim_verification_summary,
        citation_stage,
        assertion_ledger,
    ) = _run_line_by_line_citation_verification(
        content=clean,
        references=references,
        support_docs=support_docs,
        model_plan=model_plan,
        allow_abstract_fallback=allow_abstract_fallback,
    )
    support_usage_ledger = {
        "used_sources": citation_support_usage.get("used_sources", []),
        "unused_sources": citation_support_usage.get("unused_sources", []),
        "status": citation_support_usage.get("status", support_usage_ledger.get("status", "unknown")),
    }
    reports["citations"] = {
        "findings": citations.get("findings", [])[:4],
        "citation_marker_count": citations.get("citation_marker_count", 0),
        "doi_count": citations.get("doi_count", 0),
        "line_by_line_status": citation_verification_ledger.get("status", "unknown"),
        "line_by_line_checked": citation_verification_ledger.get("mention_count", 0),
        "line_by_line_reference_count": citation_verification_ledger.get("reference_count", 0),
    }
    reports["support_ingest_report"] = support_ingest_report
    reports["support_usage_ledger"] = support_usage_ledger
    reports["assertion_ledger"] = assertion_ledger
    reports["claim_verification_summary"] = claim_verification_summary
    reports["citation_verification_ledger"] = citation_verification_ledger
    reports["reference_map"] = {"count": len(references), "entries": references[:80]}

    stage_records: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = list(citation_details)
    stage_records.append(support_stage)
    stage_records.append(citation_stage)

    for stage in STAGE_ORDER:
        stage_model = model_plan["stage_models"].get(stage, model_plan.get("primary_model", "unknown"))
        prompt = _stage_prompt(stage, clean, section_map)
        result = _run_model_probe(stage_model, prompt, expect_json=True, attempt_profile="stage")
        if result.get("ok"):
            parsed = result.get("parsed", {})
            extracted = _parse_stage_findings(stage, parsed if isinstance(parsed, dict) else {})
            if not extracted:
                extracted = _fallback_stage_findings(stage, reports)
                status = "fallback_no_findings"
                note = "Model returned parseable JSON but no usable findings."
            else:
                status = "ok"
                note = ""
        else:
            extracted = _fallback_stage_findings(stage, reports)
            status = "fallback_error"
            note = str(result.get("error", "unknown"))

        details.extend(extracted)
        stage_records.append(
            {
                "stage": stage,
                "model": stage_model,
                "status": status,
                "error": note,
                "finding_count": len(extracted),
            }
        )

    runtime_fallback_records = [
        row for row in stage_records if str(row.get("status", "")) in {"fallback_error", "heuristic_only"}
    ]
    runtime_fallback_errors = sorted(
        {
            str(row.get("error", "")).strip()
            for row in runtime_fallback_records
            if str(row.get("error", "")).strip()
        }
    )
    runtime_degraded = len(runtime_fallback_records) > 0
    fallback_reasons: list[str] = []
    model_plan_reason = str(model_plan.get("fallback_reason", "")).strip()
    if model_plan_reason:
        fallback_reasons.append(model_plan_reason)
    if runtime_degraded:
        if runtime_fallback_errors:
            fallback_reasons.append(
                "Stage/model degradation detected: " + ", ".join(runtime_fallback_errors)
            )
        else:
            fallback_reasons.append(
                "Stage/model degradation detected: one or more stages used heuristic fallback."
            )
    combined_fallback_reason = " ".join(fallback_reasons).strip()

    visible_comments = _compose_visible_comments(details)
    suggested_changes = _build_suggested_changes(details, reports["line_edits"])
    compact_line_edits = []
    for row in reports["line_edits"][:4]:
        if not isinstance(row, dict):
            continue
        compact_line_edits.append(
            {
                "line_id": row.get("line_id"),
                "issue": _clean_comment_text(str(row.get("issue", "")), max_chars=140),
                "original": _clean_comment_text(str(row.get("original", "")), max_chars=200),
                "suggested": _clean_comment_text(str(row.get("suggested", "")), max_chars=200),
            }
        )
    reports_for_transport = {
        "terminology": {
            "findings": terminology.get("findings", [])[:4],
            "top_terms": terminology.get("top_terms", [])[:8],
        },
        "coherence": {
            "findings": coherence.get("findings", [])[:4],
            "avg_sentence_length": coherence.get("avg_sentence_length"),
            "transition_markers": coherence.get("transition_markers", {}),
        },
        "methods": {
            "findings": methods.get("findings", [])[:4],
            "skepticism_score": methods.get("skepticism_score"),
            "signal_checks": methods.get("signal_checks", {}),
        },
        "figures_tables": {
            "findings": figures_tables.get("findings", [])[:4],
            "figure_references": figures_tables.get("figure_references", [])[:12],
            "table_references": figures_tables.get("table_references", [])[:12],
        },
        "citations": {
            "findings": reports["citations"].get("findings", []),
            "citation_marker_count": reports["citations"].get("citation_marker_count", 0),
            "doi_count": reports["citations"].get("doi_count", 0),
            "line_by_line_status": reports["citations"].get("line_by_line_status", "unknown"),
            "line_by_line_checked": reports["citations"].get("line_by_line_checked", 0),
        },
        "journal_format": {
            "findings": journal_format.get("findings", [])[:4],
            "checks": journal_format.get("checks", {}),
        },
        "line_edits": compact_line_edits,
        "support_ingest_report": support_ingest_report,
        "support_usage_ledger": support_usage_ledger,
        "assertion_ledger": assertion_ledger,
        "claim_verification_summary": claim_verification_summary,
        "citation_verification_ledger": citation_verification_ledger,
        "references": {
            "count": len(references),
            "entry_samples": references[:20],
        },
        "support_ingest_cache_preview": [
            {
                "path": row.get("source_provenance", {}).get("path", ""),
                "title": row.get("identity", {}).get("title", ""),
                "doi": row.get("identity", {}).get("doi", ""),
                "cache_status": row.get("ingest", {}).get("cache_status", ""),
                "ingest_status": row.get("ingest", {}).get("status", ""),
            }
            for row in support_docs[:20]
            if isinstance(row, dict)
        ],
    }

    return {
        "comments": visible_comments,
        "comment_details": details,
        "suggested_changes": suggested_changes,
        "routing_trace": {
            "profile": profile,
            "transport": "local_mcp_bridge",
            "model_target": model_plan.get("primary_model", model_target or "unknown"),
            "reasoning_mode_requested": model_plan.get("requested_mode"),
            "reasoning_mode_effective": model_plan.get("effective_mode"),
            "degraded": bool(model_plan.get("degraded", False) or runtime_degraded),
            "fallback_reason": combined_fallback_reason,
            "support_ingest_model": model_plan.get("support_ingest_model", ""),
            "citation_verification_model": model_plan.get("citation_verification_model", ""),
            "support_ingest_cache_root": str(SUPPORT_CACHE_ROOT),
            "stage_model_map": [
                {
                    "stage": row["stage"],
                    "model": row["model"],
                    "status": row["status"],
                    "error": row["error"],
                    "finding_count": row["finding_count"],
                }
                for row in stage_records
            ],
            "stages": [row["stage"] for row in stage_records],
        },
        "reports": reports_for_transport,
        "model_plan": model_plan,
        "stage_records": stage_records,
    }


def _arbitrate(findings: list[str], profile: str = "balanced_local") -> dict[str, Any]:
    severity = "minor_revision"
    high_risk_tokens = [
        "missing",
        "unsupported",
        "not support",
        "could not verify",
        "cited source unavailable",
        "contradicted",
        "no conventional",
        "no figure",
        "no table",
    ]
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
    comment_details = review_data.get("comment_details") or []
    suggested_changes = review_data.get("suggested_changes") or []
    source_mode = review_data.get("source_mode") or {"mode": "unknown", "base_type": "unknown"}

    if not isinstance(comments, list):
        comments = [str(comments)]
    if not isinstance(comment_details, list):
        comment_details = []
    if not isinstance(suggested_changes, list):
        suggested_changes = [suggested_changes]

    normalized_comments: list[str] = []
    normalized_comment_details: list[dict[str, Any]] = []
    for idx, row in enumerate(comments):
        if isinstance(row, dict):
            issue = _clean_comment_text(str(row.get("issue", "")))
            fix = _clean_comment_text(str(row.get("fix", "")), max_chars=140)
            include_fix = bool(
                fix
                and len(fix) <= 95
                and str(row.get("severity", "medium")).lower() == "high"
            )
            body = issue if not include_fix else f"{issue} Fix: {fix}"
            if not body:
                continue
            normalized_comments.append(body)
            normalized_comment_details.append(
                {
                    "id": row.get("id", f"comment-{idx + 1}"),
                    "stage": row.get("stage", "unknown"),
                    "severity": row.get("severity", "medium"),
                    "issue": issue,
                    "fix": fix,
                    "source": row.get("source", "unknown"),
                    "body": body,
                }
            )
            continue
        body = _clean_comment_text(str(row))
        if not body:
            continue
        normalized_comments.append(body)

    if comment_details:
        for idx, row in enumerate(comment_details):
            if not isinstance(row, dict):
                continue
            issue = _clean_comment_text(str(row.get("issue", "")))
            fix = _clean_comment_text(str(row.get("fix", "")), max_chars=140)
            if not issue:
                continue
            include_fix = bool(
                fix
                and len(fix) <= 95
                and str(row.get("severity", "medium")).lower() == "high"
            )
            body = issue if not include_fix else f"{issue} Fix: {fix}"
            normalized_comment_details.append(
                {
                    "id": row.get("id", f"comment-detail-{idx + 1}"),
                    "stage": row.get("stage", "unknown"),
                    "severity": row.get("severity", "medium"),
                    "issue": issue,
                    "fix": fix,
                    "source": row.get("source", "unknown"),
                    "body": body,
                }
            )

    comments = normalized_comments[:MAX_STAGE_COMMENT_COUNT] if normalized_comments else []
    if not comments:
        comments = ["Manual review required: no high-confidence comments were generated."]
    if not normalized_comment_details:
        normalized_comment_details = [
            {
                "id": f"comment-{idx + 1}",
                "stage": "unknown",
                "severity": "medium",
                "issue": comment,
                "fix": "",
                "source": "unknown",
                "body": comment,
            }
            for idx, comment in enumerate(comments)
        ]

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
    support_ingest_cache_index = review_data.get("support_ingest_cache_index") or []
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
    reasoning_mode_requested = review_data.get(
        "reasoning_mode_requested",
        routing_trace.get("reasoning_mode_requested", review_data.get("mode", "unspecified")),
    )
    reasoning_mode_effective = review_data.get(
        "reasoning_mode_effective",
        routing_trace.get("reasoning_mode_effective", reasoning_mode_requested),
    )
    degraded = bool(review_data.get("degraded", routing_trace.get("degraded", False)))
    fallback_reason = str(review_data.get("fallback_reason", routing_trace.get("fallback_reason", "")))

    run_summary = {
        "timestamp": _now_iso(),
        "status": "completed",
        "profile": review_data.get("profile", "balanced_local"),
        "mode": review_data.get("mode", "unspecified"),
        "reasoning_mode_requested": reasoning_mode_requested,
        "reasoning_mode_effective": reasoning_mode_effective,
        "degraded": degraded,
        "fallback_reason": fallback_reason,
        "model_target": review_data.get("model_target", routing_trace.get("model_target", "unknown")),
        "stage_model_map": routing_trace.get("stage_model_map", []),
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
        "manuscript_comment_metadata.json": normalized_comment_details,
        "manuscript_suggested_changes_manifest.json": suggested_changes,
        "support_ingest_report.json": support_ingest_report,
        "support_usage_ledger.json": support_usage_ledger,
        "support_ingest_cache_index.json": support_ingest_cache_index,
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
        "manuscript_comment_metadata.json",
        "manuscript_suggested_changes_manifest.json",
        "support_ingest_report.json",
        "support_usage_ledger.json",
        "support_ingest_cache_index.json",
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
    allowed_remote_metadata_events = []
    disallowed_remote_events = []
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
                action = str(evt.get("action", "")).strip().lower()
                if action == "openalex_lookup":
                    allowed_remote_metadata_events.append(evt)
                else:
                    disallowed_remote_events.append(evt)

    valid = not missing and not json_errors and not front_matter_violations and not disallowed_remote_events
    payload = {
        "valid": valid,
        "missing": missing,
        "json_errors": json_errors,
        "front_matter_violations": front_matter_violations,
        "remote_network_events": remote_network_events,
        "allowed_remote_metadata_events": allowed_remote_metadata_events,
        "disallowed_remote_events": disallowed_remote_events,
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
        "comment_metadata": _load("manuscript_comment_metadata.json", []),
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
        {"name": "generate_deep_review", "description": "Run staged model-backed deep review, support-paper ingest, and line-by-line citation verification.", "inputSchema": {"type": "object", "properties": {"content": {"type": "string"}, "profile": {"type": "string"}, "reasoning_mode": {"type": "string"}, "model_target": {"type": "string"}, "section_map": {"type": "object"}, "manuscript_path": {"type": "string"}, "allow_abstract_fallback": {"type": "boolean"}}, "required": ["content"]}},
        {"name": "diagnose_model", "description": "Probe model responsiveness for short/medium/JSON/ingest/citation prompts.", "inputSchema": {"type": "object", "properties": {"model": {"type": "string"}}, "required": ["model"]}},
        {"name": "extract_color_palette", "description": "Render a PDF into representative palette artifacts and optionally filter viridis/plasma-like colors.", "inputSchema": {"type": "object", "properties": {"pdf_path": {"type": "string"}, "output_dir": {"type": "string"}, "config": {"type": "object"}}, "required": ["pdf_path"]}},
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
            # Keep MCP JSON-RPC payloads comfortably below stream-reader limits
            # while still preserving enough context for deep review stages.
            extracted_text = doc.cleaned_text[:9000]
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

        if name == "generate_deep_review":
            payload = _generate_stage_reviews(
                content=str(arguments.get("content", "")),
                profile=str(arguments.get("profile", "local_moe")),
                reasoning_mode=str(arguments.get("reasoning_mode", "moe")),
                model_target=str(arguments.get("model_target", "") or ""),
                section_map=arguments.get("section_map")
                if isinstance(arguments.get("section_map"), dict)
                else None,
                manuscript_path=str(arguments.get("manuscript_path", "") or "") or None,
                allow_abstract_fallback=bool(arguments.get("allow_abstract_fallback", True)),
            )
            _log_tool_event(
                name,
                "ok",
                {
                    "comment_count": len(payload.get("comments", [])),
                    "effective_mode": payload.get("model_plan", {}).get("effective_mode"),
                },
            )
            return payload

        if name == "diagnose_model":
            model = str(arguments.get("model", "")).strip()
            if not model:
                raise ValueError("model is required")
            payload = _diagnose_model_runtime(model)
            _log_tool_event(name, "ok", {"model": model, "usable": payload.get("usable")})
            return payload

        if name == "extract_color_palette":
            pdf_arg = str(arguments.get("pdf_path", "")).strip()
            if not pdf_arg:
                raise ValueError("pdf_path is required")
            pdf_path = Path(pdf_arg).resolve()
            if _is_blocked_path(pdf_path):
                raise ValueError(f"Path blocked by policy: {pdf_path}")
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF not found: {pdf_path}")
            output_root = (
                _ensure_local_output_root(Path(arguments["output_dir"]).resolve())
                if arguments.get("output_dir")
                else COLOR_PALETTE_OUTPUT_ROOT
            )
            output_root.mkdir(parents=True, exist_ok=True)
            config = arguments.get("config") if isinstance(arguments.get("config"), dict) else None
            try:
                payload = audit_pdf_color_palette(pdf_path, output_root=output_root, config_overrides=config)
            except ColorPaletteError as exc:
                raise ValueError(str(exc)) from exc
            _log_tool_event(
                name,
                "ok",
                {
                    "colors": payload.get("summary", {}).get("representative_colors", 0),
                    "filtered_colors": payload.get("summary", {}).get("filtered_colors", 0),
                },
            )
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
