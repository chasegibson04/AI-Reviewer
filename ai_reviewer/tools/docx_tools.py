from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from docx import Document

try:
    from docx2python import docx2python
except Exception:  # pragma: no cover
    docx2python = None

try:
    import mammoth
except Exception:  # pragma: no cover
    mammoth = None


W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
SUGGESTED_CHANGE_MARKER = "[Suggested change]"
FOLLOWUP_SUGGESTED_CHANGE_MARKER = "[Suggested change - follow-up]"


def normalize_review_artifact_text(text: str) -> str:
    if not text:
        return ""
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(SUGGESTED_CHANGE_MARKER):
            continue
        if stripped.startswith(FOLLOWUP_SUGGESTED_CHANGE_MARKER):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def get_docx_paragraph_texts(path: Path, normalize_review_artifacts: bool = False) -> list[str]:
    doc = Document(str(path))
    texts = [p.text or "" for p in doc.paragraphs]
    if normalize_review_artifacts:
        return [normalize_review_artifact_text(text) for text in texts]
    return texts


def inspect_docx_annotation_state(path: Path) -> dict:
    doc = Document(str(path))
    paragraphs = [p.text or "" for p in doc.paragraphs]
    normalized = [normalize_review_artifact_text(text) for text in paragraphs]
    visible_suggested_blocks = sum(text.count(SUGGESTED_CHANGE_MARKER) for text in paragraphs) + sum(
        text.count(FOLLOWUP_SUGGESTED_CHANGE_MARKER) for text in paragraphs
    )
    comment_texts: list[str] = []
    comment_authors: list[str] = []
    comments = list(doc.comments) if hasattr(doc, "comments") else []
    for comment in comments:
        try:
            comment_texts.append((comment.text or "").strip())
            comment_authors.append((comment.author or "").strip())
        except Exception:
            continue
    ai_reviewer_comment_count = sum(1 for author in comment_authors if "ai-reviewer" in author.lower())
    ai_reviewer_comment_count += sum(1 for text in comment_texts if "issue:" in text.lower() and "suggested revision:" in text.lower())
    non_ai_comment_count = max(0, len(comment_texts) - ai_reviewer_comment_count) if comment_texts else max(0, len(comments) - ai_reviewer_comment_count)

    track_changes = {"insertions": 0, "deletions": 0, "moves": 0}
    comments_xml_present = False
    try:
        with zipfile.ZipFile(str(path), "r") as zf:
            document_xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
            track_changes["insertions"] = len(re.findall(r"<w:ins\b", document_xml))
            track_changes["deletions"] = len(re.findall(r"<w:del\b", document_xml))
            track_changes["moves"] = len(re.findall(r"<w:move(To|From)\b", document_xml))
            comments_xml_present = "word/comments.xml" in zf.namelist()
            if comments_xml_present:
                root = ET.fromstring(zf.read("word/comments.xml"))
                extracted_authors: list[str] = []
                extracted_texts: list[str] = []
                for comment in root.findall(".//w:comment", W_NS):
                    author = comment.attrib.get(f"{{{W_NS['w']}}}author", "")
                    if author:
                        extracted_authors.append(author)
                    parts = [node.text or "" for node in comment.findall(".//w:t", W_NS)]
                    joined = "".join(parts).strip()
                    if joined:
                        extracted_texts.append(joined)
                if extracted_authors:
                    comment_authors = extracted_authors
                if extracted_texts:
                    comment_texts = extracted_texts
                    ai_reviewer_comment_count = sum(
                        1 for text in extracted_texts if "issue:" in text.lower() and "suggested revision:" in text.lower()
                    ) + sum(1 for author in comment_authors if "ai-reviewer" in author.lower())
    except Exception:
        pass

    track_change_count = sum(track_changes.values())
    if not comments and not visible_suggested_blocks and track_change_count == 0:
        annotation_state = "clean_native_docx"
    elif ai_reviewer_comment_count > 0 or visible_suggested_blocks > 0:
        annotation_state = "prior_ai_reviewer_annotated_docx" if comments or visible_suggested_blocks else "prior_ai_reviewer_comments_only"
    elif comments and track_change_count:
        annotation_state = "mixed_annotated_docx"
    elif comments:
        annotation_state = "docx_with_existing_comments"
    elif visible_suggested_blocks:
        annotation_state = "docx_with_existing_suggested_blocks"
    elif track_change_count:
        annotation_state = "docx_with_tracked_changes"
    else:
        annotation_state = "clean_native_docx"

    return {
        "annotation_state": annotation_state,
        "existing_comments_count": len(comment_texts) if comment_texts else len(comments),
        "existing_comment_authors": sorted({a for a in comment_authors if a})[:50],
        "existing_comment_excerpts": [text[:200] for text in comment_texts[:10]],
        "existing_ai_reviewer_comment_count": ai_reviewer_comment_count,
        "existing_non_ai_comment_count": non_ai_comment_count,
        "existing_suggested_change_blocks": visible_suggested_blocks,
        "tracked_change_elements": track_changes,
        "tracked_change_total": track_change_count,
        "comments_xml_present": comments_xml_present,
        "review_artifact_text_blocks_removed_for_analysis": sum(1 for raw, clean in zip(paragraphs, normalized) if raw.strip() != clean.strip()),
    }


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
    annotation_state = inspect_docx_annotation_state(path)
    return {
        "tool": "python-docx",
        "paragraph_count": len(paragraphs),
        "headings": headings[:300],
        "text": "\n".join(paragraphs),
        "comments_count": comment_count,
        "annotation_state": annotation_state,
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
    comment_tag: str | None = None,
) -> dict:
    doc = Document(str(source_docx))
    before_state = inspect_docx_annotation_state(source_docx)
    paragraph_map: dict[int, list[dict]] = {}
    for entry in comments:
        idx = int(entry.get("paragraph_index", -1))
        if idx < 0:
            continue
        paragraph_map.setdefault(idx, []).append(entry)

    added = 0
    anchored_paragraph_indices: list[int] = []

    def _anchor_runs(paragraph, anchor_text: str):
        full_text = paragraph.text or ""
        if not anchor_text or not full_text:
            return None, None
        low_full = full_text.lower()
        low_anchor = anchor_text.lower().strip()
        pos = low_full.find(low_anchor)
        if pos < 0:
            return None, None
        before = full_text[:pos]
        middle = full_text[pos : pos + len(anchor_text)]
        after = full_text[pos + len(anchor_text) :]
        paragraph.text = ""
        before_run = paragraph.add_run(before) if before else None
        middle_run = paragraph.add_run(middle)
        after_run = paragraph.add_run(after) if after else None
        return middle_run, middle_run or before_run or after_run

    for pidx, entries in paragraph_map.items():
        if pidx >= len(doc.paragraphs):
            continue
        paragraph = doc.paragraphs[pidx]
        if not paragraph.runs:
            paragraph.add_run(" ")
        for item in entries[:3]:
            first_run = paragraph.runs[0]
            last_run = paragraph.runs[-1]
            anchor_text = str(item.get("anchor_text", "")).strip()
            anchored_first, anchored_last = _anchor_runs(paragraph, anchor_text)
            if anchored_first is not None and anchored_last is not None:
                first_run, last_run = anchored_first, anchored_last
            elif paragraph.runs:
                first_run, last_run = paragraph.runs[0], paragraph.runs[-1]
            body = (
                f"{f'Review round: {comment_tag}\\n' if comment_tag else ''}"
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
    after_state = inspect_docx_annotation_state(output_docx)
    return {
        "output": str(output_docx),
        "comments_added": added,
        "anchored_paragraph_indices": anchored_paragraph_indices,
        "existing_comments_before": before_state.get("existing_comments_count", 0),
        "existing_comments_after": after_state.get("existing_comments_count", 0),
        "annotation_state_before": before_state,
        "annotation_state_after": after_state,
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
    before_state = inspect_docx_annotation_state(base_docx)
    after_state = inspect_docx_annotation_state(reviewed_docx)
    comment_ranges = 0
    try:
        with zipfile.ZipFile(str(reviewed_docx), "r") as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
            comment_ranges = len(re.findall(r"<w:commentRangeStart\b", xml))
    except Exception:
        comment_ranges = 0
    input_preannotated = before_state.get("annotation_state") != "clean_native_docx"
    new_ai_comments_added = max(
        0,
        int(after_state.get("existing_ai_reviewer_comment_count", 0)) - int(before_state.get("existing_ai_reviewer_comment_count", 0)),
    )
    return {
        "base_docx": str(base_docx),
        "reviewed_docx": str(reviewed_docx),
        "comment_count": len(comments),
        "comment_ranges_detected": comment_ranges,
        "comments_attached": comment_ranges > 0,
        "body_text_unchanged": base_text == reviewed_text,
        "input_annotation_state": before_state,
        "output_annotation_state": after_state,
        "new_comments_added_count": max(
            0,
            int(after_state.get("existing_comments_count", 0)) - int(before_state.get("existing_comments_count", 0)),
        ),
        "new_ai_reviewer_comments_added_count": new_ai_comments_added,
        "existing_comments_preserved": int(after_state.get("existing_comments_count", 0))
        >= int(before_state.get("existing_comments_count", 0)),
        "input_preannotated": input_preannotated,
        "silent_noop_suspected": input_preannotated and new_ai_comments_added == 0,
        "meaningful_new_review_state": new_ai_comments_added > 0,
    }


def create_suggested_changes_docx(
    source_docx: Path,
    output_docx: Path,
    changes: list[dict],
) -> dict:
    doc = Document(str(source_docx))
    before_state = inspect_docx_annotation_state(source_docx)
    applied = 0
    applied_indices: list[int] = []
    follow_up_applied = 0
    for change in changes:
        if change.get("status") != "applied":
            continue
        idx = int(change.get("paragraph_index", -1))
        revised = (change.get("revised_text") or "").strip()
        if idx < 0 or not revised:
            continue
        if idx >= len(doc.paragraphs):
            continue
        existing_text = (doc.paragraphs[idx].text or "").strip()
        original_text = (change.get("original_text") or existing_text).strip()
        if revised and revised in existing_text:
            continue
        if SUGGESTED_CHANGE_MARKER in existing_text or FOLLOWUP_SUGGESTED_CHANGE_MARKER in existing_text:
            visible = f"{existing_text}\n{FOLLOWUP_SUGGESTED_CHANGE_MARKER} {revised}"
            follow_up_applied += 1
        else:
            visible = f"{existing_text or original_text}\n{SUGGESTED_CHANGE_MARKER} {revised}"
        doc.paragraphs[idx].text = visible
        applied += 1
        applied_indices.append(idx)
    output_docx.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_docx))
    after_state = inspect_docx_annotation_state(output_docx)
    return {
        "output": str(output_docx),
        "changes_applied": applied,
        "applied_paragraph_indices": applied_indices,
        "follow_up_changes_applied": follow_up_applied,
        "existing_suggested_change_blocks_before": before_state.get("existing_suggested_change_blocks", 0),
        "existing_suggested_change_blocks_after": after_state.get("existing_suggested_change_blocks", 0),
    }


def validate_suggested_changes_docx(base_docx: Path, suggested_docx: Path) -> dict:
    base = Document(str(base_docx))
    suggested = Document(str(suggested_docx))
    base_paragraphs = [p.text for p in base.paragraphs]
    suggested_paragraphs = [p.text for p in suggested.paragraphs]
    before_state = inspect_docx_annotation_state(base_docx)
    after_state = inspect_docx_annotation_state(suggested_docx)
    input_preannotated = before_state.get("annotation_state") != "clean_native_docx"
    new_blocks_added = max(
        0,
        int(after_state.get("existing_suggested_change_blocks", 0)) - int(before_state.get("existing_suggested_change_blocks", 0)),
    )
    return {
        "base_docx": str(base_docx),
        "suggested_docx": str(suggested_docx),
        "paragraph_count_base": len(base_paragraphs),
        "paragraph_count_suggested": len(suggested_paragraphs),
        "structure_intact": len(base_paragraphs) == len(suggested_paragraphs),
        "docx_opens": True,
        "input_annotation_state": before_state,
        "output_annotation_state": after_state,
        "new_suggested_change_blocks_added": new_blocks_added,
        "input_preannotated": input_preannotated,
        "silent_noop_suspected": input_preannotated and new_blocks_added == 0,
        "meaningful_new_review_state": new_blocks_added > 0,
    }
