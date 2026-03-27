from __future__ import annotations

import re

from ai_reviewer.config import ReviewerConfig

try:
    from habanero import Crossref
except Exception:  # pragma: no cover
    Crossref = None

try:
    from pyalex import Works
except Exception:  # pragma: no cover
    Works = None


DOI_RE = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)")


def normalize_doi(text: str) -> str | None:
    m = DOI_RE.search(text.strip())
    if not m:
        return None
    return m.group(1).lower()


def lookup_doi_metadata(doi: str, cfg: ReviewerConfig) -> dict:
    if cfg.defaults.strict_offline:
        return {"enabled": False, "reason": "strict_offline"}
    out = {"enabled": True, "doi": doi}
    if Crossref is not None:
        try:
            cr = Crossref()
            work = cr.works(ids=doi)
            out["crossref"] = {
                "title": ((work.get("message", {}).get("title") or [""])[0]),
                "publisher": work.get("message", {}).get("publisher", ""),
                "published": work.get("message", {}).get("created", {}),
            }
        except Exception as exc:
            out["crossref_error"] = str(exc)
    if Works is not None:
        try:
            result = Works().filter(doi=doi).get(per_page=1)
            if result:
                w = result[0]
                out["openalex"] = {
                    "id": w.get("id"),
                    "title": w.get("title"),
                    "cited_by_count": w.get("cited_by_count"),
                }
        except Exception as exc:
            out["openalex_error"] = str(exc)
    return out
