from __future__ import annotations

import re
from pathlib import Path

import pymupdf
from pypdf import PdfReader

try:
    import pymupdf4llm
except Exception:  # pragma: no cover
    pymupdf4llm = None


def parse_pdf_structured(path: Path) -> dict:
    warnings: list[str] = []
    text = ""
    engine = "none"
    if pymupdf4llm is not None:
        try:
            text = pymupdf4llm.to_markdown(str(path))
            engine = "pymupdf4llm"
        except Exception as exc:
            warnings.append(f"pymupdf4llm_failed:{exc}")

    if len(text.strip()) < 200:
        try:
            doc = pymupdf.open(str(path))
            text = "\n".join(page.get_text("text") for page in doc)
            engine = "pymupdf"
        except Exception as exc:
            warnings.append(f"pymupdf_failed:{exc}")

    page_count = None
    try:
        reader = PdfReader(str(path))
        page_count = len(reader.pages)
        if len(text.strip()) < 200:
            text = "\n".join((p.extract_text() or "") for p in reader.pages)
            engine = "pypdf"
    except Exception as exc:
        warnings.append(f"pypdf_failed:{exc}")

    headings = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.match(r"^(\d+(\.\d+)*)\s+[A-Z]", s) or s.startswith("#"):
            headings.append(s.lstrip("# ").strip())
    fig_mentions = len(re.findall(r"\b(fig(?:ure)?\.?)\b", text.lower()))
    table_mentions = len(re.findall(r"\btable\b", text.lower()))
    citations = re.findall(r"\[[0-9]{1,3}\]|\([A-Z][A-Za-z-]+(?: et al\.)?,\s?[12][0-9]{3}\)", text)
    return {
        "tool": engine,
        "page_count": page_count,
        "text": text,
        "headings": headings[:300],
        "figure_mentions": fig_mentions,
        "table_mentions": table_mentions,
        "citation_markers": citations[:500],
        "warnings": warnings,
    }
