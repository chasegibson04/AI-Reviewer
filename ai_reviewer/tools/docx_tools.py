from __future__ import annotations

import re
import zipfile
from pathlib import Path

from docx import Document

try:
    from docx2python import docx2python
except Exception:  # pragma: no cover
    docx2python = None

try:
    import mammoth
except Exception:  # pragma: no cover
    mammoth = None


def parse_docx_structured(path: Path) -> dict:
    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    headings = [p.text for p in doc.paragraphs if p.style and p.style.name.lower().startswith("heading")]
    warnings: list[str] = []

    alt_text = ""
    if docx2python is not None:
        try:
            alt = docx2python(str(path))
            alt_text = "\n".join(alt.body_runs)
        except Exception as exc:
            warnings.append(f"docx2python_failed:{exc}")

    html_text = ""
    if mammoth is not None:
        try:
            with path.open("rb") as f:
                html_text = mammoth.convert_to_html(f).value
        except Exception as exc:
            warnings.append(f"mammoth_failed:{exc}")

    comment_count = len(list(doc.comments)) if hasattr(doc, "comments") else 0
    return {
        "tool": "python-docx",
        "paragraph_count": len(paragraphs),
        "headings": headings[:300],
        "text": "\n".join(paragraphs),
        "comments_count": comment_count,
        "alt_text_excerpt": alt_text[:4000],
        "html_excerpt": html_text[:4000],
        "warnings": warnings,
    }


def create_commented_docx_copy(
    source_docx: Path,
    output_docx: Path,
    comments: list[dict],
    author: str = "AI-Reviewer",
    initials: str = "AIR",
) -> dict:
    doc = Document(str(source_docx))
    paragraph_map: dict[int, list[dict]] = {}
    for entry in comments:
        idx = int(entry.get("paragraph_index", -1))
        if idx < 0:
            continue
        paragraph_map.setdefault(idx, []).append(entry)

    added = 0
    anchored_paragraph_indices: list[int] = []
    for pidx, entries in paragraph_map.items():
        if pidx >= len(doc.paragraphs):
            continue
        paragraph = doc.paragraphs[pidx]
        if not paragraph.runs:
            paragraph.add_run(" ")
        first_run = paragraph.runs[0]
        last_run = paragraph.runs[-1]
        for item in entries[:3]:
            body = (
                f"Issue: {item.get('issue_type', 'general')}\n"
                f"Severity: {item.get('severity', 'medium')}\n"
                f"Critique: {item.get('critique', '')}\n"
                f"Suggested revision: {item.get('suggested_revision', '')}\n"
                f"Rationale: {item.get('rationale', '')}"
            ).strip()
            comment = doc.comments.add_comment(text=body, author=author, initials=initials)
            first_run.mark_comment_range(last_run, comment.comment_id)
            added += 1
            anchored_paragraph_indices.append(pidx)

    output_docx.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_docx))
    return {
        "output": str(output_docx),
        "comments_added": added,
        "anchored_paragraph_indices": anchored_paragraph_indices,
    }


def create_docx_from_plain_text(text: str, output_docx: Path, title: str = "Manuscript") -> Path:
    doc = Document()
    doc.add_heading(title, level=1)

    def _normalize_heading(raw: str) -> str:
        cleaned = re.sub(r"^[■*\[\]]+", "", raw).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip(":").strip()

    def _is_heading_block(block: str) -> bool:
        if len(block) > 80:
            return False
        low = block.lower().strip(":").strip()
        if low in {
            "abstract",
            "introduction",
            "experimental",
            "methods",
            "results",
            "discussion",
            "conclusion",
            "conclusions",
            "author contributions",
            "funding",
            "associated content",
            "author information",
            "abbreviations",
            "references",
            "keywords",
        }:
            return True
        if block.isupper() and len(block.split()) <= 6:
            return True
        if re.match(r"^\[?[A-Z][A-Z\s-]{3,}\]?$", block):
            return True
        return False

    for block in [b.strip() for b in text.split("\n\n") if b.strip()]:
        if _is_heading_block(block):
            doc.add_heading(_normalize_heading(block), level=2)
        else:
            doc.add_paragraph(block)
    output_docx.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_docx))
    return output_docx


def extract_docx_body_text(path: Path) -> str:
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def validate_commented_docx(base_docx: Path, reviewed_docx: Path) -> dict:
    base = Document(str(base_docx))
    reviewed = Document(str(reviewed_docx))
    base_text = "\n".join(p.text for p in base.paragraphs)
    reviewed_text = "\n".join(p.text for p in reviewed.paragraphs)
    comments = list(reviewed.comments) if hasattr(reviewed, "comments") else []
    comment_ranges = 0
    try:
        with zipfile.ZipFile(str(reviewed_docx), "r") as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
            comment_ranges = len(re.findall(r"<w:commentRangeStart\b", xml))
    except Exception:
        comment_ranges = 0
    return {
        "base_docx": str(base_docx),
        "reviewed_docx": str(reviewed_docx),
        "comment_count": len(comments),
        "comment_ranges_detected": comment_ranges,
        "comments_attached": comment_ranges > 0,
        "body_text_unchanged": base_text == reviewed_text,
    }


def create_suggested_changes_docx(
    source_docx: Path,
    output_docx: Path,
    changes: list[dict],
) -> dict:
    doc = Document(str(source_docx))
    applied = 0
    applied_indices: list[int] = []
    for change in changes:
        if change.get("status") != "applied":
            continue
        idx = int(change.get("paragraph_index", -1))
        revised = (change.get("revised_text") or "").strip()
        if idx < 0 or not revised:
            continue
        if idx >= len(doc.paragraphs):
            continue
        doc.paragraphs[idx].text = revised
        applied += 1
        applied_indices.append(idx)
    output_docx.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_docx))
    return {"output": str(output_docx), "changes_applied": applied, "applied_paragraph_indices": applied_indices}


def validate_suggested_changes_docx(base_docx: Path, suggested_docx: Path) -> dict:
    base = Document(str(base_docx))
    suggested = Document(str(suggested_docx))
    base_paragraphs = [p.text for p in base.paragraphs]
    suggested_paragraphs = [p.text for p in suggested.paragraphs]
    return {
        "base_docx": str(base_docx),
        "suggested_docx": str(suggested_docx),
        "paragraph_count_base": len(base_paragraphs),
        "paragraph_count_suggested": len(suggested_paragraphs),
        "structure_intact": len(base_paragraphs) == len(suggested_paragraphs),
        "docx_opens": True,
    }
