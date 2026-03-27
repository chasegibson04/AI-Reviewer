from __future__ import annotations

from pathlib import Path
from typing import Any
import re

from docx import Document

from ai_reviewer.ingest.types import ParsedDocument
from ai_reviewer.tools.docx_tools import (
    create_commented_docx_copy,
    create_docx_from_plain_text,
    validate_commented_docx,
)


def detect_source_mode(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return {"mode": "original_docx", "base_type": "docx"}
    if suffix == ".pdf":
        return {"mode": "pdf_only_surrogate", "base_type": "pdf"}
    return {"mode": "surrogate_other_source", "base_type": suffix.lstrip(".")}


def review_to_comment_entries(
    review: Any,
    doc: ParsedDocument | None = None,
    base_docx: Path | None = None,
    max_comments: int = 24,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for idx, sec in enumerate(review.section_specific_comments, start=1):
        critique = str(sec.comment).strip()
        if not critique:
            continue
        entries.append(
            {
                "paragraph_index": idx,
                "issue_type": "structure/organization",
                "severity": sec.severity,
                "critique": critique,
                "suggested_revision": f"Section rewrite suggestion: In '{sec.section}', lead with the main claim, then add one concrete supporting detail and one limitation sentence.",
                "rationale": "Section-level issue tied to review schema output.",
            }
        )
    for idx, item in enumerate(review.extracted_action_items, start=len(entries) + 1):
        action = str(item.action).strip()
        if not action:
            continue
        if action.lower().startswith("address:"):
            action = action.split(":", 1)[-1].strip()
        entries.append(
            {
                "paragraph_index": idx,
                "issue_type": "clarity",
                "severity": item.priority,
                "critique": action,
                "suggested_revision": (
                    "Suggested rewrite: add one sentence that specifies the exact condition, metric, and observed outcome, "
                    "and add one sentence that states the limitation or boundary of the claim."
                ),
                "rationale": "Derived from extracted action item requiring manuscript-local clarification.",
            }
        )
        if len(entries) >= max_comments:
            break
    category_pairs = [
        ("methods concern", getattr(review, "methodological_concerns", [])),
        ("evidence/overclaim concern", getattr(review, "novelty_concerns", [])),
        ("citation/reference concern", getattr(review, "citation_reference_concerns", [])),
        ("grammar/style", getattr(review, "writing_organization_concerns", [])),
        ("formatting/journal style", getattr(review, "figure_table_concerns", [])),
        ("redundancy", getattr(review, "major_weaknesses", [])),
    ]
    for label, items in category_pairs:
        for item in items[:2]:
            text = str(item).strip()
            if not text:
                continue
            if label == "methods concern":
                suggestion = (
                    "Add a sentence that names the control/baseline explicitly and links it to the exact experiment or metric."
                )
            elif label == "evidence/overclaim concern":
                suggestion = (
                    "Tone down certainty language and add a boundary-condition sentence that states what was not tested."
                )
            elif label == "citation/reference concern":
                suggestion = (
                    "Attach a specific citation and state whether the support is direct evidence or contextual prior work."
                )
            elif label == "grammar/style":
                suggestion = "Shorten the sentence, prefer active voice, and keep one claim per sentence."
            elif label == "formatting/journal style":
                suggestion = "Align figure/table callout wording and caption style with journal and lab formatting guidance."
            else:
                suggestion = "Remove repetition and merge overlapping statements into one precise sentence."
            entries.append(
                {
                    "paragraph_index": len(entries) + 1,
                    "issue_type": label,
                    "severity": "medium",
                    "critique": text,
                    "suggested_revision": suggestion,
                    "rationale": f"Derived from {label} findings.",
                }
            )
            if len(entries) >= max_comments:
                break
        if len(entries) >= max_comments:
            break
    if not entries:
        for idx, text in enumerate(review.detailed_reviewer_comments[:max_comments], start=1):
            entries.append(
                {
                    "paragraph_index": idx,
                    "issue_type": "grammar/style",
                    "severity": "medium",
                    "critique": str(text).strip(),
                    "suggested_revision": "Rewrite this sentence with tighter wording and explicit subject-action-result structure.",
                    "rationale": "Fallback from detailed reviewer comments with sentence-level edit intent.",
                }
            )
    if not entries:
        summary = str(getattr(review, "summary", "") or "").strip()
        weaknesses = [str(x) for x in getattr(review, "major_weaknesses", []) if str(x).strip()]
        seed = weaknesses[:3] or ([summary] if summary else [])
        if not seed:
            seed = [
                "Clarify core contribution and novelty claim.",
                "Tighten methods/result linkage language.",
                "Improve writing precision and remove ambiguous phrasing.",
            ]
        for idx, text in enumerate(seed, start=1):
            entries.append(
                {
                    "paragraph_index": idx,
                    "issue_type": "clarity",
                    "severity": "medium",
                    "critique": text,
                    "suggested_revision": "Replace vague phrasing with one specific claim and one concrete supporting detail.",
                    "rationale": "Fallback comment when structured review fields were sparse.",
                }
            )

    # Inject concrete sentence-level edits from the manuscript body when possible.
    if base_docx is not None:
        docx = Document(str(base_docx))
        paragraphs = [p.text.strip() for p in docx.paragraphs]
        locked_used: set[int] = set()
        for pidx, text in enumerate(paragraphs):
            if len(entries) >= max_comments:
                break
            if not text or len(text.split()) < 18:
                continue
            low = text.lower()
            if re.fullmatch(r"\d{3,5}", text.strip()):
                continue
            if _is_placeholder_paragraph(low):
                continue
            if _is_header_footer_text(low):
                continue
            if re.match(r"^#+\s", text.strip()) or re.match(r"^■", text.strip()):
                continue
            if _is_front_or_back_matter_text(low):
                continue
            if "abstract" in low and len(text.split()) < 30:
                continue
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
            for s in sentences:
                if len(entries) >= max_comments:
                    break
                if len(s.split()) < 22:
                    continue
                if pidx in locked_used:
                    break
                if " was " in f" {s.lower()} " or " were " in f" {s.lower()} ":
                    rewrite = _rewrite_candidate(s)
                    entries.append(
                        {
                            "paragraph_index": pidx,
                            "issue_type": "grammar/style",
                            "severity": "medium",
                            "critique": f"Passive or long sentence reduces clarity: {s[:220]}",
                            "suggested_revision": f"Suggested rewrite: {rewrite}",
                            "rationale": "Sentence-level clarity pass on manuscript text.",
                            "locked_paragraph": True,
                        }
                    )
                    locked_used.add(pidx)
                    break

    # Add manuscript-specific claim calibration prompts if phrases appear.
    if doc is not None:
        text = doc.cleaned_text.lower()
        claim_hits = []
        for phrase in ["first attempt", "every instance tried", "modest to excellent yields"]:
            if phrase in text:
                claim_hits.append(phrase)
        for phrase in claim_hits[:3]:
            anchor_index = None
            if base_docx is not None:
                docx = Document(str(base_docx))
                for i, p in enumerate(docx.paragraphs):
                    if phrase in (p.text or "").lower():
                        anchor_index = i
                        break
            entry = {
                "paragraph_index": anchor_index if anchor_index is not None else len(entries) + 1,
                "issue_type": "evidence/overclaim concern",
                "severity": "high",
                "critique": f"Claim language around '{phrase}' may overstate generality without clarifying assay vs isolated yields or scope.",
                "suggested_revision": (
                    "Clarify whether this refers to at least one successful condition per case study, "
                    "distinguish assay yield vs isolated yield, and specify the scope of 'first attempt'."
                ),
                "rationale": "Manuscript-specific claim calibration cue detected in text.",
                "allow_abstract": True,
                "anchor_phrase": phrase,
            }
            if anchor_index is not None:
                entry["locked_paragraph"] = True
            entries.append(entry)
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for e in entries:
        critique = re.sub(r"\s+", " ", str(e.get("critique", "")).strip())
        suggestion = re.sub(r"\s+", " ", str(e.get("suggested_revision", "")).strip())
        if not critique:
            continue
        if any(x in suggestion.lower() for x in ["apply action:", "address:", "revise wording to address this issue"]):
            suggestion = "Rewrite this location with concrete condition, evidence statement, and limitation language."
            e["suggested_revision"] = suggestion
        sig = (e.get("issue_type", ""), critique[:180].lower())
        if sig in seen:
            continue
        seen.add(sig)
        clean.append(e)
        if len(clean) >= max_comments:
            break
    return clean


def _rewrite_candidate(sentence: str) -> str:
    s = sentence.strip()
    if len(s) > 260:
        s = s[:260].rstrip() + "..."
    clauses = [c.strip() for c in s.split(",") if c.strip()]
    if s.lower().startswith("to ") and len(clauses) >= 2:
        words = s.split()
        short = " ".join(words[:26]).rstrip(".")
        return short + "."
    if len(clauses) >= 2:
        c1 = clauses[0].rstrip(".")
        c2 = clauses[1][0:120].rstrip(".")
        if c2 and c2[0].islower():
            c2 = c2[0].upper() + c2[1:]
        return f"{c1}. {c2}."
    words = s.split()
    if len(words) > 24:
        short = " ".join(words[:24]).rstrip(".")
        return short + "."
    return s if s.endswith(".") else s + "."


def _limit_comments_per_paragraph(entries: list[dict[str, Any]], max_per_paragraph: int = 2) -> list[dict[str, Any]]:
    if not entries:
        return entries
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    type_rank = {
        "evidence/overclaim concern": 0,
        "methods concern": 1,
        "clarity": 2,
        "grammar/style": 3,
        "redundancy": 4,
        "structure/organization": 5,
        "citation/reference concern": 6,
        "formatting/journal style": 7,
        "figure/table concern": 8,
    }
    grouped: dict[int, list[dict[str, Any]]] = {}
    for e in entries:
        pidx = e.get("paragraph_index")
        if not isinstance(pidx, int):
            continue
        grouped.setdefault(pidx, []).append(e)
    trimmed: list[dict[str, Any]] = []
    used_ids = set()
    for pidx, group in grouped.items():
        if len(group) <= max_per_paragraph:
            trimmed.extend(group)
            continue
        # Prefer highest severity and diverse issue types.
        group_sorted = sorted(
            group,
            key=lambda x: (
                type_rank.get(str(x.get("issue_type", "")).lower(), 9),
                severity_rank.get(str(x.get("severity", "medium")).lower(), 1),
            ),
        )
        kept: list[dict[str, Any]] = []
        seen_types: set[str] = set()
        for item in group_sorted:
            itype = str(item.get("issue_type", "")).lower()
            if itype in seen_types and itype == "evidence/overclaim concern":
                continue
            kept.append(item)
            seen_types.add(itype)
            if len(kept) >= max_per_paragraph:
                break
        trimmed.extend(kept)
    # Preserve original order for stability.
    for e in entries:
        if id(e) in used_ids:
            continue
    kept_set = {id(e) for e in trimmed}
    return [e for e in entries if id(e) in kept_set]


def _is_front_or_back_matter_text(text: str) -> bool:
    t = text.lower().strip()
    if not t:
        return True
    blocked = [
        "cite this",
        "associated content",
        "supporting information",
        "author information",
        "author contributions",
        "funding",
        "acknowledgment",
        "abbreviations",
        "references",
        "received",
        "accepted",
        "published",
        "doi.org",
        "acs",
        "keywords",
        "corresponding author",
        "notes",
    ]
    return any(b in t for b in blocked)


def _is_placeholder_paragraph(text: str) -> bool:
    t = text.strip().lower()
    if "==> picture" in t or "intentionally omitted" in t:
        return True
    if "picture" in t and "omitted" in t:
        return True
    if t.startswith("figure ") and "intentionally omitted" in t:
        return True
    return False


def _is_heading_paragraph(text: str) -> bool:
    t = text.strip()
    if re.match(r"^#\s", t):
        return True
    if re.match(r"^##\s", t):
        return True
    if re.match(r"^###\s", t):
        return True
    if re.match(r"^■", t):
        return True
    if re.match(r"^\*\*\[.+\]\*\*$", t):
        return True
    return False


def _is_header_footer_text(text: str) -> bool:
    t = text.strip().lower()
    if not t:
        return False
    if re.fullmatch(r"\d{3,5}", t):
        return True
    header_terms = [
        "pubs.acs.org",
        "org. process res. dev",
        "organic process research",
        "https://doi.org/10.1021",
        "doi.org/10.1021",
        "article",
    ]
    if any(term in t for term in header_terms) and len(t.split()) <= 6:
        return True
    return False


def _is_front_or_back_matter_heading(text: str) -> bool:
    t = text.strip().lower()
    if not t:
        return False
    return bool(
        re.match(
            r"^(author contributions|funding|associated content|author information|abbreviations|references|notes|corresponding author|authors)\b",
            t,
        )
    )


def _assign_paragraph_indices(entries: list[dict[str, Any]], base_docx: Path) -> list[dict[str, Any]]:
    doc = Document(str(base_docx))
    paragraphs = [p.text.strip() for p in doc.paragraphs]
    non_empty = [idx for idx, text in enumerate(paragraphs) if text]
    if not non_empty:
        return entries

    def _normalize_heading(text: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z ]", " ", text).lower()
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        tokens = cleaned.split()
        if len(tokens) <= 3 and "experimental" in tokens:
            return "experimental"
        if len(tokens) <= 3 and "methods" in tokens:
            return "methods"
        return cleaned

    section_by_idx: dict[int, str] = {}
    current = "body"
    for idx in non_empty:
        t = paragraphs[idx].strip()
        low = t.lower()
        norm = _normalize_heading(t)
        if _is_header_footer_text(low):
            section_by_idx[idx] = "header_footer"
            continue
        if re.match(r"^abstract\b", low) or norm == "abstract":
            current = "abstract"
        elif norm in {"introduction", "experimental", "methods", "results", "discussion", "conclusions", "conclusion"}:
            current = norm
        elif norm.startswith("references"):
            current = "references"
        elif _is_front_or_back_matter_heading(low):
            current = "front_matter" if "references" not in low else "references"
        section_by_idx[idx] = current

    eligible = [
        idx
        for idx in non_empty
        if section_by_idx.get(idx) not in {"front_matter", "references", "header_footer"}
        and not _is_placeholder_paragraph(paragraphs[idx])
        and not _is_heading_paragraph(paragraphs[idx])
        and not _is_header_footer_text(paragraphs[idx])
    ]
    if not eligible:
        eligible = non_empty

    used: dict[int, int] = {}
    for i, entry in enumerate(entries):
        if entry.get("locked_paragraph") and isinstance(entry.get("paragraph_index"), int):
            pidx = int(entry["paragraph_index"])
            if 0 <= pidx < len(paragraphs) and section_by_idx.get(pidx) not in {"front_matter", "references"}:
                entry["paragraph_excerpt"] = paragraphs[pidx][:180]
                entry["section_hint"] = section_by_idx.get(pidx, "body")
                used[pidx] = used.get(pidx, 0) + 1
                continue
        critique = str(entry.get("critique", "")).lower()
        suggestion = str(entry.get("suggested_revision", "")).lower()
        anchor_phrase = str(entry.get("anchor_phrase", "")).lower().strip()
        anchor_terms = [w for w in (critique + " " + suggestion).split() if len(w) > 5][:12]
        issue_type = str(entry.get("issue_type", "")).lower()

        chosen: int | None = None
        preferred_sections = []
        if issue_type == "methods concern":
            preferred_sections = ["methods", "experimental"]
        elif issue_type == "evidence/overclaim concern":
            preferred_sections = ["results", "discussion", "conclusions", "abstract"]
        elif issue_type in {"grammar/style", "clarity", "redundancy"}:
            preferred_sections = ["introduction", "methods", "experimental", "results", "discussion"]
        elif issue_type in {"formatting/journal style", "figure/table concern"}:
            preferred_sections = ["results", "discussion"]
        elif issue_type == "structure/organization":
            preferred_sections = ["introduction", "results", "discussion", "conclusions"]

        pool = eligible
        if preferred_sections:
            pool = [p for p in eligible if section_by_idx.get(p, "body") in preferred_sections] or eligible
        if issue_type in {"formatting/journal style", "figure/table concern"}:
            pool = [
                p
                for p in pool
                if "figure" in paragraphs[p].lower()
                and not _is_placeholder_paragraph(paragraphs[p])
            ] or pool
        else:
            pool = [p for p in pool if not _is_placeholder_paragraph(paragraphs[p])]

        if anchor_phrase:
            tokens = [t for t in re.split(r"\s+", anchor_phrase) if len(t) > 2]
            for pidx in pool:
                text = paragraphs[pidx].lower()
                if anchor_phrase in text or (tokens and all(tok in text for tok in tokens)):
                    chosen = pidx
                    break

        for pidx in pool:
            text = paragraphs[pidx].lower()
            section = section_by_idx.get(pidx, "body")
            if section == "abstract" and issue_type in {"methods concern", "reproducibility", "statistics concern"}:
                continue
            if section == "abstract" and not entry.get("allow_abstract", False) and issue_type in {"grammar/style", "clarity", "redundancy"}:
                continue
            if section in {"front_matter", "references", "header_footer"}:
                continue
            if "keywords" in text or text.startswith("keywords:"):
                continue
            if re.fullmatch(r"\d{3,5}", text.strip()):
                continue
            if _is_placeholder_paragraph(text):
                if issue_type not in {"formatting/journal style", "figure/table concern"}:
                    continue
            if "figure" in text and issue_type not in {"formatting/journal style", "figure/table concern"}:
                continue
            if any(term in text for term in anchor_terms):
                if used.get(pidx, 0) < 1:
                    chosen = pidx
                    break

        if chosen is None:
            dist_total = len(eligible)
            target_rank = max(0, min(dist_total - 1, round((i + 1) * dist_total / (len(entries) + 1))))
            chosen = eligible[target_rank]
            attempts = 0
            while used.get(chosen, 0) >= 1 and attempts < dist_total:
                target_rank = min(dist_total - 1, target_rank + 1)
                chosen = eligible[target_rank]
                attempts += 1

        entry["paragraph_index"] = chosen
        entry["paragraph_excerpt"] = paragraphs[chosen][:180]
        entry["section_hint"] = section_by_idx.get(chosen, "body")
        used[chosen] = used.get(chosen, 0) + 1
    return entries


def _section_map_for_docx(base_docx: Path) -> list[dict[str, Any]]:
    doc = Document(str(base_docx))
    paragraphs = [p.text.strip() for p in doc.paragraphs]
    out: list[dict[str, Any]] = []
    current = "body"
    def _normalize_heading(text: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z ]", " ", text).lower()
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        tokens = cleaned.split()
        if len(tokens) <= 3 and "experimental" in tokens:
            return "experimental"
        if len(tokens) <= 3 and "methods" in tokens:
            return "methods"
        return cleaned
    for idx, text in enumerate(paragraphs):
        if not text:
            continue
        low = text.lower()
        norm = _normalize_heading(text)
        if _is_header_footer_text(low):
            out.append(
                {
                    "paragraph_index": idx,
                    "section": "header_footer",
                    "text_excerpt": text[:200],
                }
            )
            continue
        if re.match(r"^abstract\b", low) or norm == "abstract":
            current = "abstract"
        elif norm in {"introduction", "experimental", "methods", "results", "discussion", "conclusions", "conclusion"}:
            current = norm
        elif norm.startswith("references"):
            current = "references"
        elif _is_front_or_back_matter_heading(low):
            current = "front_matter" if "references" not in low else "references"
        out.append(
            {
                "paragraph_index": idx,
                "section": current,
                "text_excerpt": text[:200],
            }
        )
    return out


def build_annotated_manuscript_output(
    source_path: Path,
    doc: ParsedDocument,
    review: Any,
    output_dir: Path,
    project_id: str | None = None,
) -> dict[str, Any]:
    source_mode = detect_source_mode(source_path)
    if source_mode["mode"] == "original_docx":
        base_docx = source_path
        reviewed_name = "reviewed_manuscript_with_comments.docx"
    else:
        base_docx = output_dir / "surrogate_manuscript_from_pdf_base.docx"
        create_docx_from_plain_text(doc.cleaned_text, base_docx, title=source_path.stem)
        reviewed_name = "surrogate_manuscript_from_pdf_with_comments.docx"
    comments = review_to_comment_entries(review, doc=doc, base_docx=base_docx)
    comments = _assign_paragraph_indices(comments, base_docx)
    comments = _limit_comments_per_paragraph(comments, max_per_paragraph=2)
    reviewed_docx = output_dir / reviewed_name
    result = create_commented_docx_copy(base_docx, reviewed_docx, comments)
    validation = validate_commented_docx(base_docx, reviewed_docx)
    section_map = _section_map_for_docx(base_docx)
    source_mode_artifact = {
        "project_id": project_id,
        "manuscript_source_path": str(source_path),
        "source_mode": source_mode["mode"],
        "surrogate_base_path": str(base_docx) if source_mode["mode"] != "original_docx" else None,
        "notes": [],
    }
    return {
        "source_mode": source_mode,
        "source_mode_artifact": source_mode_artifact,
        "base_docx": str(base_docx),
        "reviewed_docx": str(reviewed_docx),
        "comments_requested": len(comments),
        "comments_added": result.get("comments_added", 0),
        "anchored_paragraph_indices": result.get("anchored_paragraph_indices", []),
        "comment_targets": comments,
        "validation": validation,
        "section_map": section_map,
    }
