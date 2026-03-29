from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import requests

from ai_reviewer.config import ReviewerConfig
from ai_reviewer.ingest.types import ParsedDocument

try:
    from habanero import Crossref
except Exception:  # pragma: no cover
    Crossref = None


DOI_RE = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)")
REF_START = re.compile(r"^\s*\(?\d+[a-z]?[.)]\s+")


@dataclass
class CitationFetchReport:
    enabled: bool
    reason: str | None
    total_references: int
    total_candidates: int
    total_downloaded: int
    entries: list[dict]


@dataclass
class CitationMethodContext:
    reference: str
    doi: str | None
    title: str | None
    cfg: ReviewerConfig
    timeout: int
    dest_dir: Path
    doi_cache: dict[str, str]


@dataclass
class CitationMethodResult:
    status: str
    saved_path: str | None = None
    doi: str | None = None
    title: str | None = None
    source: str | None = None
    candidate_count: int = 0
    query_audit: list[dict] | None = None


CitationMethod = Callable[[CitationMethodContext], CitationMethodResult]


def extract_doi(text: str) -> str | None:
    match = DOI_RE.search(text or "")
    if not match:
        return None
    return match.group(1).rstrip(".").lower()


def extract_title(ref: str) -> str:
    quoted = re.findall(r'["\'](.*?)["\']', ref or "")
    if quoted:
        return quoted[0]
    clean = re.sub(r"^\s*\(?\d+[a-z]?[.)]\s*", "", ref or "")
    return clean.strip()


def parse_references(text: str, max_refs: int) -> list[str]:
    if not text:
        return []
    lines = [ln.strip() for ln in text.replace("−", "-").replace("—", "-").splitlines()]
    refs: list[str] = []
    current = ""
    in_refs = False
    for line in lines:
        if not line:
            continue
        header = line.lower().strip(" :")
        if header in {"references", "reference"} or re.match(r"^(■\s*)?references\b", line, re.I):
            in_refs = True
            continue
        if not in_refs:
            continue
        if REF_START.match(line):
            if current:
                refs.append(current.strip())
            current = line
        elif current:
            if current.endswith("-"):
                current = current[:-1] + line
            else:
                current += " " + line
        else:
            current = line
        if len(refs) >= max_refs:
            break
    if current and len(refs) < max_refs:
        refs.append(current.strip())
    if refs:
        return refs

    # Fallback: collect numbered reference-like lines without explicit header.
    current = ""
    for line in lines:
        if not line:
            continue
        if REF_START.match(line):
            if current:
                refs.append(current.strip())
            current = line
        elif current:
            if current.endswith("-"):
                current = current[:-1] + line
            else:
                current += " " + line
        if len(refs) >= max_refs:
            break
    if current and len(refs) < max_refs:
        refs.append(current.strip())
    return refs


def _safe_filename(text: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "", text).strip().replace(" ", "_")
    if not name:
        name = "citation"
    return (name[:80] + ".pdf") if not name.lower().endswith(".pdf") else name[:84]


def _normalized_title_tokens(text: str) -> set[str]:
    cleaned = _sanitize_query_text(text or "", max_chars=500).lower()
    tokens = re.findall(r"[a-z0-9]{4,}", cleaned)
    stop = {"with", "from", "using", "into", "this", "that", "these", "those", "journal", "article"}
    return {tok for tok in tokens if tok not in stop}


def _requests_get(url: str, timeout: int, accept_pdf: bool = False) -> requests.Response | None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "application/pdf,application/xhtml+xml,text/html;q=0.9,*/*;q=0.8" if accept_pdf else "application/json,*/*",
    }
    try:
        return requests.get(url, timeout=timeout, headers=headers)
    except Exception:
        return None


def _find_pdf_urls_for_doi(doi: str, cfg: ReviewerConfig, timeout: int) -> list[tuple[str, str]]:
    urls: list[tuple[str, str]] = []
    if not doi:
        return urls
    if cfg.citation_fetch.email:
        upw = f"https://api.unpaywall.org/v2/{doi}?email={cfg.citation_fetch.email}"
        r = _requests_get(upw, timeout)
        if r and r.status_code == 200:
            data = r.json()
            if data.get("is_oa"):
                best = (data.get("best_oa_location") or {}).get("url_for_pdf")
                if best:
                    urls.append(("unpaywall", best))
                for loc in data.get("oa_locations", []):
                    alt = loc.get("url_for_pdf")
                    if alt and alt != best:
                        urls.append(("unpaywall_alt", alt))
    oa = f"https://api.openalex.org/works/https://doi.org/{doi}"
    r = _requests_get(oa, timeout)
    if r and r.status_code == 200:
        best = (r.json().get("best_oa_location") or {}).get("pdf_url")
        if best:
            urls.append(("openalex", best))
    ss = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=openAccessPdf"
    r = _requests_get(ss, timeout)
    if r and r.status_code == 200:
        oa_pdf = (r.json().get("openAccessPdf") or {}).get("url")
        if oa_pdf:
            urls.append(("semantic_scholar", oa_pdf))
    epmc = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:{doi}&format=json&resultType=core"
    r = _requests_get(epmc, timeout)
    if r and r.status_code == 200:
        results = (r.json().get("resultList") or {}).get("result", [])
        if results and results[0].get("pmcid") and results[0].get("isOpenAccess") == "Y":
            urls.append(("europe_pmc", f"https://europepmc.org/articles/{results[0]['pmcid']}?pdf=render"))
    ncbi = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={doi}&format=json"
    r = _requests_get(ncbi, timeout)
    if r and r.status_code == 200:
        records = r.json().get("records", [])
        if records and records[0].get("pmcid"):
            urls.append(("ncbi_pmc", f"https://www.ncbi.nlm.nih.gov/pmc/articles/{records[0]['pmcid']}/pdf/"))
    return urls


def _sanitize_query_text(text: str, max_chars: int = 220) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    cleaned = re.sub(r"[^A-Za-z0-9 .,:;()_+\-/]", "", cleaned)
    return cleaned[:max_chars]


def _download_pdf(url: str, dest: Path, timeout: int) -> str:
    r = _requests_get(url, timeout, accept_pdf=True)
    if not r:
        return "request_failed"
    if r.status_code != 200:
        return f"http_{r.status_code}"
    content = r.content or b""
    if b"%PDF" not in content[:100]:
        return "not_pdf"
    dest.write_bytes(content)
    return "ok"


def _crossref_lookup(reference: str) -> tuple[str | None, str | None]:
    if Crossref is None:
        return None, None
    try:
        cr = Crossref()
        res = cr.works(query=_sanitize_query_text(reference), limit=1)
        items = (res or {}).get("message", {}).get("items", [])
        if not items:
            return None, None
        item = items[0]
        doi = item.get("DOI")
        title = (item.get("title") or [""])[0]
        return doi, title
    except Exception:
        return None, None


def _method_doi_open_access_apis(ctx: CitationMethodContext) -> CitationMethodResult:
    doi = ctx.doi
    if not doi:
        return CitationMethodResult(status="no_doi")
    query_audit = [{"type": "doi_lookup", "len": len(doi)}]
    cached_path = ctx.doi_cache.get(doi.lower())
    if cached_path and Path(cached_path).exists():
        return CitationMethodResult(
            status="already_present_by_cache",
            saved_path=cached_path,
            doi=doi,
            title=ctx.title,
            source="doi_cache",
            candidate_count=0,
            query_audit=query_audit,
        )
    urls = _find_pdf_urls_for_doi(doi, ctx.cfg, ctx.timeout)
    if not urls:
        return CitationMethodResult(status="no_oa_links", doi=doi, title=ctx.title, candidate_count=0, query_audit=query_audit)
    name = _safe_filename((ctx.title or doi).replace("/", "_"))
    dest = ctx.dest_dir / name
    if dest.exists():
        return CitationMethodResult(
            status="already_present",
            saved_path=str(dest),
            doi=doi,
            title=ctx.title,
            source="existing",
            candidate_count=len(urls),
            query_audit=query_audit,
        )
    status = "no_oa_links"
    for source, url in urls:
        dl = _download_pdf(url, dest, ctx.timeout)
        if dl == "ok":
            return CitationMethodResult(
                status=f"downloaded:{source}",
                saved_path=str(dest),
                doi=doi,
                title=ctx.title,
                source=source,
                candidate_count=len(urls),
                query_audit=query_audit,
            )
        status = f"failed:{dl}"
        time.sleep(random.uniform(0.2, 0.6))
    return CitationMethodResult(status=status, doi=doi, title=ctx.title, candidate_count=len(urls), query_audit=query_audit)


def _method_crossref_lookup_then_oa(ctx: CitationMethodContext) -> CitationMethodResult:
    if ctx.doi:
        return CitationMethodResult(status="skip_has_doi", doi=ctx.doi, title=ctx.title)
    safe_ref = _sanitize_query_text(ctx.reference)
    doi, title = _crossref_lookup(safe_ref)
    if not doi:
        return CitationMethodResult(status="no_doi", title=ctx.title, query_audit=[{"type": "crossref_title_lookup", "len": len(safe_ref)}])
    nested = CitationMethodContext(
        reference=ctx.reference,
        doi=doi,
        title=title or ctx.title,
        cfg=ctx.cfg,
        timeout=ctx.timeout,
        dest_dir=ctx.dest_dir,
        doi_cache=ctx.doi_cache,
    )
    out = _method_doi_open_access_apis(nested)
    out.doi = out.doi or doi
    out.title = out.title or title
    out.query_audit = [{"type": "crossref_title_lookup", "len": len(safe_ref)}, *((out.query_audit or []))]
    return out


def _method_local_project_pdf_match(ctx: CitationMethodContext) -> CitationMethodResult:
    title_tokens = _normalized_title_tokens(ctx.title or ctx.reference)
    doi = (ctx.doi or "").lower().strip()
    matches: list[tuple[float, Path]] = []
    for path in sorted(ctx.dest_dir.glob("*.pdf")):
        haystack = f"{path.stem} {path.name}".lower()
        score = 0.0
        if doi and doi.replace("/", "_") in haystack:
            score += 2.0
        pdf_tokens = _normalized_title_tokens(path.stem)
        if title_tokens and pdf_tokens:
            overlap = len(title_tokens & pdf_tokens) / float(len(title_tokens | pdf_tokens))
            score += overlap
        if score >= 0.45:
            matches.append((score, path))
    if not matches:
        return CitationMethodResult(
            status="no_local_match",
            doi=ctx.doi,
            title=ctx.title,
            query_audit=[{"type": "local_pdf_title_match", "len": len(" ".join(sorted(title_tokens)))}],
        )
    matches.sort(key=lambda item: item[0], reverse=True)
    best = matches[0][1]
    return CitationMethodResult(
        status="already_present_by_local_match",
        saved_path=str(best),
        doi=ctx.doi,
        title=ctx.title,
        source="local_other_dir_match",
        candidate_count=len(matches),
        query_audit=[{"type": "local_pdf_title_match", "len": len(" ".join(sorted(title_tokens)))}],
    )


def _method_crossref_short_title_then_oa(ctx: CitationMethodContext) -> CitationMethodResult:
    if ctx.doi:
        return CitationMethodResult(status="skip_has_doi", doi=ctx.doi, title=ctx.title)
    base_title = ctx.title or extract_title(ctx.reference)
    words = _sanitize_query_text(base_title, max_chars=220).split()
    if not words:
        return CitationMethodResult(status="no_title_tokens", title=ctx.title)
    shortened = " ".join(words[: min(len(words), 12)])
    doi, title = _crossref_lookup(shortened)
    if not doi:
        return CitationMethodResult(
            status="no_doi",
            title=ctx.title,
            query_audit=[{"type": "crossref_short_title_lookup", "len": len(shortened)}],
        )
    nested = CitationMethodContext(
        reference=ctx.reference,
        doi=doi,
        title=title or ctx.title,
        cfg=ctx.cfg,
        timeout=ctx.timeout,
        dest_dir=ctx.dest_dir,
        doi_cache=ctx.doi_cache,
    )
    out = _method_doi_open_access_apis(nested)
    out.doi = out.doi or doi
    out.title = out.title or title
    out.query_audit = [{"type": "crossref_short_title_lookup", "len": len(shortened)}, *((out.query_audit or []))]
    return out


REGISTERED_CITATION_METHODS: dict[str, CitationMethod] = {
    # Fast path when DOI exists in the reference string.
    "doi_open_access_apis": _method_doi_open_access_apis,
    # Fallback path inspired by PaperScraperV2: title->Crossref->OA APIs.
    "crossref_lookup_then_oa": _method_crossref_lookup_then_oa,
    # Local fallback: reuse PDFs already present in materials/other when title/DOI strongly matches.
    "local_project_pdf_match": _method_local_project_pdf_match,
    # Network fallback: shorten noisy reference/title strings before Crossref lookup.
    "crossref_short_title_then_oa": _method_crossref_short_title_then_oa,
}


def _resolve_method_order(cfg: ReviewerConfig) -> list[str]:
    ordered = [m.strip() for m in (cfg.citation_fetch.methods or []) if m.strip()]
    if not ordered:
        ordered = ["doi_open_access_apis", "crossref_lookup_then_oa"]
    for fallback in ["local_project_pdf_match", "crossref_short_title_then_oa"]:
        if fallback not in ordered:
            ordered.append(fallback)
    return ordered


def _doi_cache_path(other_dir: Path) -> Path:
    return other_dir / "citation_doi_cache.json"


def _load_doi_cache(other_dir: Path) -> dict[str, str]:
    path = _doi_cache_path(other_dir)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        doi = str(k).strip().lower()
        p = Path(str(v))
        if doi and p.exists():
            out[doi] = str(p)
    return out


def _save_doi_cache(other_dir: Path, cache: dict[str, str]) -> None:
    path = _doi_cache_path(other_dir)
    payload = {k: v for k, v in sorted(cache.items())}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def fetch_citations_for_documents(
    docs: Iterable[ParsedDocument],
    project_root: Path,
    cfg: ReviewerConfig,
    logger,
    run_dir: Path | None = None,
) -> CitationFetchReport:
    if not cfg.citation_fetch.enabled:
        return CitationFetchReport(False, "disabled", 0, 0, 0, [])
    if cfg.defaults.strict_offline:
        return CitationFetchReport(False, "strict_offline", 0, 0, 0, [])

    other_dir = project_root / "materials" / "other"
    other_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    total_downloaded = 0
    total_candidates = 0
    total_cache_hits = 0
    method_order = _resolve_method_order(cfg)
    active_methods = [m for m in method_order if m in REGISTERED_CITATION_METHODS]
    doi_cache = _load_doi_cache(other_dir)

    if logger:
        logger.info(
            "citation_fetch_stage_start methods=%s output_dir=%s",
            ",".join(active_methods) or "none",
            other_dir,
        )

    for doc in docs:
        refs = parse_references(doc.raw_text or doc.cleaned_text, cfg.citation_fetch.max_refs_per_doc)
        for ref in refs[: cfg.citation_fetch.max_papers]:
            initial_doi = extract_doi(ref)
            title = extract_title(ref)
            entry = {
                "reference": ref,
                "doi": initial_doi,
                "title": title,
                "status": "not_attempted",
                "saved_path": None,
                "method_attempts": [],
            }
            if entry["doi"]:
                cached_path = doi_cache.get(str(entry["doi"]).lower())
                if cached_path and Path(cached_path).exists():
                    entry["status"] = "already_present_by_cache"
                    entry["saved_path"] = cached_path
                    entry["method_attempts"].append(
                        {"method": "doi_cache", "status": "already_present_by_cache", "source": "doi_cache"}
                    )
                    total_cache_hits += 1
                    entries.append(entry)
                    continue
            for method_name in active_methods:
                method = REGISTERED_CITATION_METHODS.get(method_name)
                if method is None:
                    continue
                ctx = CitationMethodContext(
                    reference=ref,
                    doi=entry.get("doi"),
                    title=entry.get("title"),
                    cfg=cfg,
                    timeout=cfg.citation_fetch.request_timeout_seconds,
                    dest_dir=other_dir,
                    doi_cache=doi_cache,
                )
                result = method(ctx)
                total_candidates += int(result.candidate_count)
                if result.doi and not entry.get("doi"):
                    entry["doi"] = result.doi
                if result.title and not entry.get("title"):
                    entry["title"] = result.title
                attempt = {"method": method_name, "status": result.status, "source": result.source}
                if result.query_audit:
                    attempt["query_audit"] = result.query_audit
                entry["method_attempts"].append(attempt)
                if result.status.startswith("downloaded:") or result.status in {"already_present", "already_present_by_local_match"}:
                    entry["status"] = result.status
                    entry["saved_path"] = result.saved_path
                    if entry.get("doi") and entry.get("saved_path"):
                        doi_cache[str(entry["doi"]).lower()] = str(entry["saved_path"])
                    if result.status.startswith("downloaded:"):
                        total_downloaded += 1
                    break
                if result.status == "already_present_by_cache":
                    entry["status"] = result.status
                    entry["saved_path"] = result.saved_path
                    total_cache_hits += 1
                    break
                entry["status"] = result.status
            entries.append(entry)
    _save_doi_cache(other_dir, doi_cache)

    report = CitationFetchReport(
        enabled=True,
        reason=None,
        total_references=len(entries),
        total_candidates=total_candidates,
        total_downloaded=total_downloaded,
        entries=entries,
    )
    payload = {
        "enabled": report.enabled,
        "reason": report.reason,
        "methods": active_methods,
        "output_dir": str(other_dir),
        "total_references": report.total_references,
        "total_candidates": report.total_candidates,
        "total_downloaded": report.total_downloaded,
        "total_cache_hits": total_cache_hits,
        "doi_cache_entries": len(doi_cache),
        "query_policy": {
            "no_manuscript_raw_text": True,
            "allowed_query_types": ["doi_lookup", "crossref_title_lookup", "crossref_short_title_lookup", "local_pdf_title_match"],
            "query_sanitization": "whitespace normalized, symbol filtering, max length 220",
        },
        "entries": report.entries,
    }
    if run_dir:
        (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (run_dir / "artifacts" / "citation_fetch_report.json").write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
    if logger:
        logger.info(
            "citation_fetch_stage_done methods=%s downloaded=%s candidates=%s entries=%s",
            ",".join(active_methods) or "none",
            report.total_downloaded,
            report.total_candidates,
            report.total_references,
        )
    return report
