from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

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
        else:
            if current:
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
        else:
            if current:
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


def _requests_get(url: str, timeout: int) -> requests.Response | None:
    try:
        return requests.get(url, timeout=timeout, headers={"User-Agent": "AI-Reviewer/1.0"})
    except Exception:
        return None


def _find_pdf_urls(doi: str, cfg: ReviewerConfig, timeout: int) -> list[tuple[str, str]]:
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


def _download_pdf(url: str, dest: Path, timeout: int) -> str:
    r = _requests_get(url, timeout)
    if not r:
        return "request_failed"
    if r.status_code != 200:
        return f"http_{r.status_code}"
    content = r.content or b""
    if b"%PDF" not in content[:100]:
        return "not_pdf"
    dest.write_bytes(content)
    return "ok"


def _crossref_lookup(reference: str, timeout: int) -> tuple[str | None, str | None]:
    if Crossref is None:
        return None, None
    try:
        cr = Crossref()
        res = cr.works(query=reference, limit=1)
        items = (res or {}).get("message", {}).get("items", [])
        if not items:
            return None, None
        item = items[0]
        doi = item.get("DOI")
        title = (item.get("title") or [""])[0]
        return doi, title
    except Exception:
        return None, None


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

    other_dir = project_root / "materials" / "other" / "citations"
    other_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    total_downloaded = 0
    total_candidates = 0

    for doc in docs:
        refs = parse_references(doc.raw_text or doc.cleaned_text, cfg.citation_fetch.max_refs_per_doc)
        for ref in refs[: cfg.citation_fetch.max_papers]:
            doi = extract_doi(ref)
            title = None
            if not doi:
                doi, title = _crossref_lookup(ref, cfg.citation_fetch.request_timeout_seconds)
            if not doi:
                entries.append({"reference": ref, "status": "no_doi"})
                continue

            urls = _find_pdf_urls(doi, cfg, cfg.citation_fetch.request_timeout_seconds)
            total_candidates += len(urls)
            status = "no_oa_links"
            saved = None
            for src, url in urls:
                name = _safe_filename(title or doi.replace("/", "_"))
                dest = other_dir / name
                if dest.exists():
                    status = "already_present"
                    saved = str(dest)
                    break
                dl = _download_pdf(url, dest, cfg.citation_fetch.request_timeout_seconds)
                if dl == "ok":
                    status = f"downloaded:{src}"
                    saved = str(dest)
                    total_downloaded += 1
                    break
                status = f"failed:{dl}"
                time.sleep(random.uniform(0.2, 0.6))
            entries.append({"reference": ref, "doi": doi, "status": status, "saved_path": saved})

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
        "total_references": report.total_references,
        "total_candidates": report.total_candidates,
        "total_downloaded": report.total_downloaded,
        "entries": report.entries,
    }
    if run_dir:
        (run_dir / "artifacts" / "citation_fetch_report.json").write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
    if logger:
        logger.info(
            "citation_fetch enabled=%s downloaded=%s candidates=%s entries=%s",
            report.enabled,
            report.total_downloaded,
            report.total_candidates,
            report.total_references,
        )
    return report
