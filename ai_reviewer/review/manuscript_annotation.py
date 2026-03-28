from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re
from uuid import uuid4

from docx import Document

from ai_reviewer.ingest.types import ParsedDocument
from ai_reviewer.models.base import Provider, ChatRequest
from ai_reviewer.review.repair import extract_json_candidate
from ai_reviewer.tools.docx_tools import (
    create_commented_docx_copy,
    create_docx_from_plain_text,
    create_suggested_changes_docx,
    validate_commented_docx,
    validate_suggested_changes_docx,
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
        if "add one concrete evidence statement" in critique.lower():
            continue
        entries.append(
            {
                "paragraph_index": idx,
                "issue_type": "structure/organization",
                "severity": sec.severity,
                "critique": critique,
                "suggested_revision": f"Proposed edit: revise the opening of '{sec.section}' to explicitly reflect: {critique}",
                "rationale": "Section-level issue tied to review schema output; aim to align opening claim with critique.",
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
            if re.match(r"^abstract\b", low) or low.startswith("abstract:"):
                continue
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
        if not e.get("comment_id"):
            e["comment_id"] = f"cmt_{uuid4().hex[:10]}"
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
    if re.match(r"^\d+\s*[a-z].*\b(university|department|inc\.|corp\.|usa|uk|germany|france|switzerland)\b", t):
        return True
    if "present address" in t:
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
        "check for updates",
        "nature synthesis",
        "doi.org",
        "acs",
        "keywords",
        "corresponding author",
        "notes",
        "american chemical society",
        "org. process res. dev",
        "organic process research",
        "pubs.acs.org",
        "article",
        "copyright",
        "©",
    ]
    return any(b in t for b in blocked)


def _is_placeholder_paragraph(text: str) -> bool:
    t = text.strip().lower()
    if "==> picture" in t or "intentionally omitted" in t:
        return True
    if "picture" in t and "omitted" in t:
        return True
    if "start of picture text" in t or "end of picture text" in t:
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
    if re.match(r"^##\s*\*\*?.+\*\*?$", t):
        return True
    if t.isupper() and 1 <= len(t.split()) <= 6:
        return True
    if re.match(r"^\*\*[A-Za-z].+\*\*$", t) and len(t.split()) <= 8:
        return True
    return False


def _is_header_footer_text(text: str) -> bool:
    t = text.strip().lower()
    if not t:
        return False
    digits = re.sub(r"[^0-9]", "", t)
    if digits and 3 <= len(digits) <= 5 and len(t) <= len(digits) + 4:
        return True
    if "nature synthesis" in t:
        return True
    if "volume" in t and ("issue" in t or "november" in t or re.search(r"\b20\d{2}\b", t)):
        return True
    if "check for updates" in t:
        return True
    if re.search(r"\bvolume\s*\d+\b", t) and re.search(r"\b\d{4}\b", t):
        return True
    if re.search(r"\bvolume\s*\d+\b", t) and "|" in t:
        return True
    header_terms = [
        "pubs.acs.org",
        "org. process res. dev",
        "organic process research",
        "https://doi.org/10.1021",
        "doi.org/10.1021",
        "doi.org/10.1038",
        "article",
    ]
    if any(term in t for term in header_terms) and len(t.split()) <= 6:
        return True
    return False


def _is_front_or_back_matter_heading(text: str) -> bool:
    t = re.sub(r"[^a-zA-Z ]", " ", text).lower()
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return False
    return bool(
        re.match(
            r"^(author contributions|funding|associated content|author information|abbreviations|references|notes|corresponding author|authors|acknowledg(e)?ments|data availability|additional information|supplementary information|competing interests)\b",
            t,
        )
    )


def _normalize_heading_text(text: str) -> str:
    cleaned = re.sub(r"[*#_]+", " ", text)
    cleaned = re.sub(r"[^a-zA-Z ]", " ", cleaned).lower()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    tokens = cleaned.split()
    if len(tokens) <= 3 and "experimental" in tokens:
        return "experimental"
    if len(tokens) <= 3 and "methods" in tokens:
        return "methods"
    return cleaned


def _heading_to_section(norm: str) -> str | None:
    if not norm:
        return None
    if norm.startswith("abstract"):
        return "abstract"
    if norm in {"introduction", "background"}:
        return "introduction"
    if norm in {"methods", "experimental", "materials methods", "materials and methods"}:
        return "methods"
    if norm.startswith("general procedure") or "procedure" in norm:
        return "methods"
    if norm in {"results", "results and discussion", "findings"}:
        return "results"
    if norm in {"discussion", "interpretation"}:
        return "discussion"
    if norm in {"conclusion", "conclusions"}:
        return "conclusions"
    if norm.startswith("references"):
        return "references"
    if _is_front_or_back_matter_heading(norm):
        return "front_matter"
    return None


def _build_section_index_map(paragraphs: list[str]) -> dict[int, str]:
    section_by_idx: dict[int, str] = {}
    current = "body"
    total = len(paragraphs)
    method_headings: list[int] = []
    references_heading: int | None = None
    for idx, text in enumerate(paragraphs):
        if not text:
            continue
        low = text.strip().lower()
        if _is_header_footer_text(low):
            section_by_idx[idx] = "header_footer"
            continue
        if _is_front_or_back_matter_text(low):
            section_by_idx[idx] = "front_matter"
            current = "front_matter"
            continue
        if _is_heading_paragraph(text):
            norm = _normalize_heading_text(text)
            heading_section = _heading_to_section(norm)
            if heading_section:
                current = heading_section
                if heading_section in {"methods", "experimental"}:
                    method_headings.append(idx)
                if heading_section == "references":
                    references_heading = idx
        elif re.match(r"^abstract\b", low):
            current = "abstract"
        section_by_idx[idx] = current

    body_indices = [idx for idx, sec in section_by_idx.items() if sec == "body"]
    if body_indices and len(body_indices) / max(1, len(section_by_idx)) > 0.6:
        first_methods = min(method_headings) if method_headings else None
        for idx in body_indices:
            text = paragraphs[idx].strip()
            low = text.lower()
            if re.match(r"^\\d+\\.\\s", low) and re.search(r"\\b(19|20)\\d{2}\\b", low):
                section_by_idx[idx] = "references"
                continue
            if first_methods is not None and idx < first_methods:
                section_by_idx[idx] = "introduction"
                continue
            if idx < max(6, int(total * 0.12)) and "abstract" not in low:
                section_by_idx[idx] = "introduction"
                continue
            if any(k in low for k in ["method", "experimental", "procedure", "reagent", "reaction conditions"]):
                section_by_idx[idx] = "methods"
                continue
            if any(k in low for k in ["result", "yield", "conversion", "screen", "figure", "table", "data"]):
                section_by_idx[idx] = "results"
                continue
            if any(k in low for k in ["discussion", "overall", "in summary", "we conclude", "implications"]):
                section_by_idx[idx] = "discussion"
                continue

    # Reclassify methods paragraphs that clearly read like results/discussion.
    for idx, sec in list(section_by_idx.items()):
        if sec not in {"methods", "experimental"}:
            continue
        text = paragraphs[idx].strip().lower()
        if any(k in text for k in ["result", "yield", "conversion", "screen", "figure", "table", "data"]):
            section_by_idx[idx] = "results"
            continue
        if any(k in text for k in ["discussion", "overall", "in summary", "we conclude", "implications"]):
            section_by_idx[idx] = "discussion"
            continue
    return section_by_idx


def _assign_paragraph_indices(entries: list[dict[str, Any]], base_docx: Path) -> list[dict[str, Any]]:
    doc = Document(str(base_docx))
    paragraphs = [p.text.strip() for p in doc.paragraphs]
    non_empty = [idx for idx, text in enumerate(paragraphs) if text]
    if not non_empty:
        return entries

    section_by_idx = _build_section_index_map(paragraphs)

    eligible = [
        idx
        for idx in non_empty
        if section_by_idx.get(idx) not in {"front_matter", "references", "header_footer"}
        and not _is_placeholder_paragraph(paragraphs[idx])
        and not _is_heading_paragraph(paragraphs[idx])
        and not _is_header_footer_text(paragraphs[idx])
        and not _is_front_or_back_matter_text(paragraphs[idx])
    ]
    if not eligible:
        eligible = non_empty

    used: dict[int, int] = {}
    for i, entry in enumerate(entries):
        if entry.get("locked_paragraph") and isinstance(entry.get("paragraph_index"), int):
            pidx = int(entry["paragraph_index"])
            if 0 <= pidx < len(paragraphs) and section_by_idx.get(pidx) not in {"front_matter", "references"}:
                section = section_by_idx.get(pidx, "body")
                issue_type = str(entry.get("issue_type", "")).lower()
                if section == "abstract" and not entry.get("allow_abstract", False) and issue_type in {"grammar/style", "clarity", "redundancy"}:
                    continue
                entry["paragraph_excerpt"] = paragraphs[pidx][:180]
                entry["section_hint"] = section
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


def _enrich_comment_suggestions(entries: list[dict[str, Any]], base_docx: Path) -> list[dict[str, Any]]:
    doc = Document(str(base_docx))
    paragraphs = [p.text.strip() for p in doc.paragraphs]
    templated_markers = [
        "add a sentence",
        "tone down",
        "attach a specific citation",
        "align figure/table",
        "remove repetition",
        "rewrite this sentence",
        "rewrite this location",
        "suggested rewrite",
        "apply action",
        "revise wording",
    ]
    for entry in entries:
        pidx = entry.get("paragraph_index")
        if not isinstance(pidx, int) or pidx < 0 or pidx >= len(paragraphs):
            continue
        text = paragraphs[pidx]
        if not text:
            continue
        low = text.lower()
        if _is_front_or_back_matter_text(low) or _is_heading_paragraph(text):
            continue
        suggestion = str(entry.get("suggested_revision", "")).strip()
        critique = str(entry.get("critique", "")).strip()
        extracted = None
        for marker in [
            "Rewrite long sentence for clarity:",
            "Long sentence to simplify:",
            "Possible passive construction to rewrite:",
            "Clarify this section’s opening claim:",
            "Clarify this section's opening claim:",
        ]:
            if marker in critique:
                extracted = critique.split(marker, 1)[-1].strip().strip("\"")
                break
        if not extracted and "\"" in critique:
            match = re.search(r"\"(.+?)\"", critique)
            if match:
                extracted = match.group(1).strip()
        if not suggestion:
            suggestion = ""
        if extracted:
            rewrite = _rewrite_candidate(extracted)
            entry["suggested_revision"] = f"Proposed edit: {rewrite}"
            entry["rationale"] = "Proposed edit derived from the cited sentence in the critique."
            continue
        if any(marker in suggestion.lower() for marker in templated_markers):
            sentence = re.split(r"(?<=[.!?])\s+", text)[0].strip()
            if sentence:
                rewrite = _rewrite_candidate(sentence)
                entry["suggested_revision"] = f"Proposed edit: {rewrite}"
                entry["rationale"] = "Proposed edit derived from the nearby sentence to improve clarity and flow."
    return entries


def _section_map_for_docx(base_docx: Path) -> list[dict[str, Any]]:
    doc = Document(str(base_docx))
    paragraphs = [p.text.strip() for p in doc.paragraphs]
    out: list[dict[str, Any]] = []
    section_by_idx = _build_section_index_map(paragraphs)
    for idx, text in enumerate(paragraphs):
        if not text:
            continue
        section = section_by_idx.get(idx, "body")
        out.append(
            {
                "paragraph_index": idx,
                "section": section,
                "text_excerpt": text[:200],
            }
        )
    return out


def _section_lookup_for_docx(base_docx: Path) -> dict[int, str]:
    return {item["paragraph_index"]: item["section"] for item in _section_map_for_docx(base_docx)}


def _severity_rank(value: str | None) -> int:
    low = (value or "").lower()
    if low in {"critical", "high"}:
        return 3
    if low in {"medium", "moderate"}:
        return 2
    return 1


def _token_overlap(a: str, b: str) -> float:
    ta = {t for t in re.split(r"\W+", a.lower()) if t}
    tb = {t for t in re.split(r"\W+", b.lower()) if t}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / float(len(ta | tb))


def _numeric_tokens(text: str) -> set[str]:
    cleaned = re.sub(r"\[[^\]]+\]", "", text)
    cleaned = cleaned.replace(",", "")
    tokens = re.findall(r"\d+(?:\.\d+)?", cleaned)
    return {t.strip() for t in tokens if t.strip()}


def _basic_rewrite_checks(original: str, revised: str) -> tuple[bool, str | None]:
    o = original.strip()
    r = revised.strip()
    if not r:
        return False, "empty_revision"
    if r == o:
        return False, "no_change"
    if re.match(r"^\s*#{1,6}\s", r):
        return False, "markdown_heading"
    if re.match(r"^\s*\*\*\[[^\]]+\]\*\*", r):
        return False, "markdown_section_label"
    if len(r) < 0.6 * len(o) or len(r) > 1.6 * len(o):
        return False, "length_drift"
    orig_nums = _numeric_tokens(o)
    rev_nums = _numeric_tokens(r)
    if orig_nums and not orig_nums.issubset(rev_nums):
        return False, "numeric_loss"
    if _token_overlap(o, r) < 0.35:
        return False, "low_overlap"
    return True, None


def _verify_rewrite(
    provider: Provider,
    model: str,
    original: str,
    revised: str,
    critique: str,
    timeout_seconds: int,
) -> tuple[bool, dict[str, Any]]:
    system_prompt = (
        "You are a careful scientific editor. Return ONLY JSON with keys: ok, fluency_score, faithfulness_score, "
        "alignment_score, issues. Scores are 0-1. ok=false if meaning changes, invented facts, or worse clarity."
    )
    user_prompt = (
        "Evaluate the rewrite for fluency, faithfulness to meaning, and alignment with the critique.\n\n"
        f"CRITIQUE:\n{critique}\n\n"
        f"ORIGINAL:\n{original}\n\n"
        f"REVISED:\n{revised}\n\n"
        "Return JSON only."
    )
    resp = provider.chat(
        ChatRequest(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=320,
            timeout_seconds=timeout_seconds,
            metadata={"purpose": "rewrite_verifier"},
        )
    )
    candidate = extract_json_candidate(resp.content) or resp.content
    parsed = json.loads(candidate)
    ok = bool(parsed.get("ok", False))
    return ok, parsed


def _generate_suggested_changes(
    base_docx: Path,
    comments: list[dict[str, Any]],
    source_mode: dict[str, Any],
    project_id: str | None,
    run_id: str | None,
    provider: Provider | None,
    model: str | None,
    rewrite_model: str | None,
    timeout_seconds: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    docx = Document(str(base_docx))
    paragraphs = [p.text or "" for p in docx.paragraphs]
    section_by_idx = _section_lookup_for_docx(base_docx)
    grouped: dict[int, list[dict[str, Any]]] = {}
    for c in comments:
        pidx = c.get("paragraph_index")
        if isinstance(pidx, int):
            grouped.setdefault(pidx, []).append(c)
    changes: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    blocked_sections = {"front_matter", "references", "header_footer"}
    abstract_allowed = {"evidence/overclaim concern", "clarity", "structure/organization"}
    global_issue_types = {"structure/organization", "framing", "global"}
    for pidx, group in sorted(grouped.items(), key=lambda x: x[0]):
        section = section_by_idx.get(pidx, "body")
        original = paragraphs[pidx].strip()
        change_id = f"chg_{uuid4().hex[:10]}"
        issue_types = sorted({str(c.get("issue_type", "")).strip() for c in group if str(c.get("issue_type", "")).strip()})
        severity = max((c.get("severity") for c in group), key=_severity_rank, default="medium")
        comment_ids = [c.get("comment_id") for c in group if c.get("comment_id")]
        base_entry = {
            "change_id": change_id,
            "project_id": project_id,
            "run_id": run_id,
            "source_mode": source_mode.get("mode"),
            "target_section": section,
            "target_paragraph_index": pidx,
            "original_text": original[:1200],
            "revised_text": None,
            "originating_comment_ids": comment_ids,
            "issue_types": issue_types,
            "severity": severity,
            "rationale": None,
            "confidence": None,
            "status": "skipped",
            "skip_reason": None,
        }
        if issue_types and all(it.lower() in global_issue_types for it in issue_types):
            base_entry["skip_reason"] = "global_issue_not_localized"
            changes.append(base_entry)
            continue
        low = original.lower().strip()
        if section in blocked_sections or _is_front_or_back_matter_text(low):
            base_entry["skip_reason"] = "blocked_section"
            changes.append(base_entry)
            continue
        if _is_heading_paragraph(original):
            base_entry["skip_reason"] = "heading_paragraph"
            changes.append(base_entry)
            continue
        if re.match(r"^[^a-z0-9]*fig\\.|^[^a-z0-9]*figure\\b|^[^a-z0-9]*table\\b", low):
            base_entry["skip_reason"] = "caption_blocked"
            changes.append(base_entry)
            continue
        if _is_placeholder_paragraph(low):
            base_entry["skip_reason"] = "placeholder_text"
            changes.append(base_entry)
            continue
        if not original or len(original.split()) < 6:
            base_entry["skip_reason"] = "too_short"
            changes.append(base_entry)
            continue
        if section == "abstract":
            if not any(str(c.get("issue_type", "")).lower() in abstract_allowed for c in group) and not any(
                c.get("allow_abstract", False) for c in group
            ):
                base_entry["skip_reason"] = "abstract_high_threshold"
                changes.append(base_entry)
                continue
        if provider is None or (rewrite_model or model) is None:
            base_entry["skip_reason"] = "no_provider"
            changes.append(base_entry)
            continue
        prev_text = paragraphs[pidx - 1].strip() if pidx - 1 >= 0 else ""
        next_text = paragraphs[pidx + 1].strip() if pidx + 1 < len(paragraphs) else ""
        context = "\n\n".join(
            [
                f"PREV: {prev_text}" if prev_text else "",
                f"TARGET: {original}",
                f"NEXT: {next_text}" if next_text else "",
            ]
        ).strip()
        critique_lines = []
        for c in group:
            critique_lines.append(
                f"- {c.get('issue_type','')} ({c.get('severity','')}): {c.get('critique','')}. "
                f"Suggestion: {c.get('suggested_revision','')}"
            )
        section_rules = {
            "abstract": "Keep the abstract concise; only adjust claim calibration, ambiguity, or scope alignment. Avoid adding procedural detail unless required.",
            "introduction": "Improve framing, novelty clarity, and problem statement precision without adding new claims.",
            "methods": "Improve reproducibility phrasing, parameter clarity, and disclosure without altering actual procedures.",
            "experimental": "Improve reproducibility phrasing, parameter clarity, and disclosure without altering actual procedures.",
            "results": "Clarify claim support, yield/metric precision, and interpretation boundaries; avoid overstating.",
            "discussion": "Tone down overreach and improve interpretation discipline; keep meaning intact.",
            "conclusion": "Align with demonstrated scope and avoid broad overclaims.",
            "conclusions": "Align with demonstrated scope and avoid broad overclaims.",
        }
        rule = section_rules.get(section, "Improve clarity and flow while preserving scientific meaning.")
        system_prompt = (
            "You are an expert scientific editor. Return ONLY JSON with keys: revised_text, rationale, confidence. "
            "Do not add new facts or citations. Preserve meaning unless a comment requests calibration. "
            "Make minimal, high-impact edits rather than rewriting the whole paragraph."
        )
        user_prompt = (
            f"SECTION: {section}\n"
            f"RULE: {rule}\n\n"
            f"COMMENTS:\n" + "\n".join(critique_lines) + "\n\n"
            f"CONTEXT:\n{context}\n\n"
            "Rewrite ONLY the TARGET paragraph. If no safe improvement exists, return the original text. "
            "Return JSON only."
        )
        use_model = rewrite_model or model
        try:
            resp = provider.chat(
                ChatRequest(
                    model=use_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.2,
                    max_tokens=700,
                    timeout_seconds=timeout_seconds,
                    metadata={
                        "purpose": "suggested_changes",
                        "project_id": project_id,
                        "run_id": run_id,
                        "section": section,
                    },
                )
            )
            candidate = extract_json_candidate(resp.content) or resp.content
            parsed = json.loads(candidate)
        except Exception:
            base_entry["skip_reason"] = "generation_failed"
            changes.append(base_entry)
            continue
        revised = str(parsed.get("revised_text", "") or "").strip()
        rationale = str(parsed.get("rationale", "") or "").strip()
        confidence = parsed.get("confidence", None)
        ok_basic, reason = _basic_rewrite_checks(original, revised)
        if not ok_basic:
            base_entry["skip_reason"] = reason
            changes.append(base_entry)
            continue
        try:
            ok_verify, verdict = _verify_rewrite(
                provider=provider,
                model=use_model,
                original=original,
                revised=revised,
                critique="; ".join(critique_lines)[:800],
                timeout_seconds=timeout_seconds,
            )
        except Exception:
            ok_verify, verdict = False, {"ok": False, "issues": ["verifier_failed"]}
        base_entry["verification"] = verdict
        if not ok_verify:
            issues = verdict.get("issues", []) if isinstance(verdict, dict) else []
            if issues:
                repair_system = (
                    "You are a careful scientific editor revising a draft. Fix the issues listed. "
                    "Return ONLY JSON with keys: revised_text, rationale, confidence."
                )
                repair_user = (
                    f"SECTION: {section}\n"
                    f"RULE: {rule}\n\n"
                    f"ISSUES TO FIX:\n{issues}\n\n"
                    f"CRITIQUE:\n" + "\n".join(critique_lines) + "\n\n"
                    f"ORIGINAL:\n{original}\n\n"
                    f"CURRENT REVISION:\n{revised}\n\n"
                    "Provide a corrected revision that resolves the issues. Return JSON only."
                )
                try:
                    repair_resp = provider.chat(
                        ChatRequest(
                            model=use_model,
                            system_prompt=repair_system,
                            user_prompt=repair_user,
                            temperature=0.2,
                            max_tokens=700,
                            timeout_seconds=timeout_seconds,
                            metadata={"purpose": "suggested_changes_revise", "section": section},
                        )
                    )
                    repair_candidate = extract_json_candidate(repair_resp.content) or repair_resp.content
                    repair_parsed = json.loads(repair_candidate)
                    revised = str(repair_parsed.get("revised_text", "") or "").strip()
                    rationale = str(repair_parsed.get("rationale", "") or "").strip()
                    confidence = repair_parsed.get("confidence", None)
                    ok_basic, reason = _basic_rewrite_checks(original, revised)
                    if ok_basic:
                        ok_verify, verdict = _verify_rewrite(
                            provider=provider,
                            model=use_model,
                            original=original,
                            revised=revised,
                            critique="; ".join(critique_lines)[:800],
                            timeout_seconds=timeout_seconds,
                        )
                        base_entry["verification"] = verdict
                except Exception:
                    ok_verify = False
            if not ok_verify:
                base_entry["skip_reason"] = "rewrite_rejected_low_quality"
                changes.append(base_entry)
                continue
        try:
            if float(verdict.get("faithfulness_score", 1.0)) < 0.6:
                base_entry["skip_reason"] = "rewrite_rejected_meaning_change"
                changes.append(base_entry)
                continue
        except Exception:
            pass
        base_entry["revised_text"] = revised[:1200]
        base_entry["rationale"] = rationale[:600] if rationale else None
        try:
            base_entry["confidence"] = float(confidence) if confidence is not None else None
        except Exception:
            base_entry["confidence"] = None
        base_entry["status"] = "applied"
        base_entry["skip_reason"] = None
        changes.append(base_entry)
        applied.append({"paragraph_index": pidx, "revised_text": revised})
    return changes, applied


def build_annotated_manuscript_output(
    source_path: Path,
    doc: ParsedDocument,
    review: Any,
    output_dir: Path,
    project_id: str | None = None,
    run_id: str | None = None,
    provider: Provider | None = None,
    model: str | None = None,
    rewrite_model: str | None = None,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    source_mode = detect_source_mode(source_path)
    if source_mode["mode"] == "original_docx":
        base_docx = source_path
        reviewed_name = "reviewed_manuscript_with_comments.docx"
        suggested_name = "reviewed_manuscript_with_suggested_changes.docx"
    else:
        base_docx = output_dir / "surrogate_manuscript_from_pdf_base.docx"
        create_docx_from_plain_text(doc.cleaned_text, base_docx, title=source_path.stem)
        reviewed_name = "surrogate_manuscript_from_pdf_with_comments.docx"
        suggested_name = "surrogate_manuscript_from_pdf_with_suggested_changes.docx"
    comments = review_to_comment_entries(review, doc=doc, base_docx=base_docx)
    comments = _assign_paragraph_indices(comments, base_docx)
    comments = _limit_comments_per_paragraph(comments, max_per_paragraph=2)
    comments = _enrich_comment_suggestions(comments, base_docx)
    reviewed_docx = output_dir / reviewed_name
    result = create_commented_docx_copy(base_docx, reviewed_docx, comments)
    validation = validate_commented_docx(base_docx, reviewed_docx)
    section_map = _section_map_for_docx(base_docx)
    changes_manifest, applied_changes = _generate_suggested_changes(
        base_docx=base_docx,
        comments=comments,
        source_mode=source_mode,
        project_id=project_id,
        run_id=run_id,
        provider=provider,
        model=model,
        rewrite_model=rewrite_model,
        timeout_seconds=timeout_seconds,
    )
    suggested_docx = output_dir / suggested_name
    suggested_result = create_suggested_changes_docx(
        source_docx=base_docx,
        output_docx=suggested_docx,
        changes=[
            {
                "paragraph_index": entry.get("target_paragraph_index"),
                "revised_text": entry.get("revised_text"),
                "status": entry.get("status"),
            }
            for entry in changes_manifest
        ],
    )
    suggested_validation = validate_suggested_changes_docx(base_docx, suggested_docx)
    base_doc = Document(str(base_docx))
    suggested_doc = Document(str(suggested_docx))
    section_by_idx = _section_lookup_for_docx(base_docx)
    front_matter_changed = 0
    references_changed = 0
    for idx, base_p in enumerate(base_doc.paragraphs):
        sec = section_by_idx.get(idx, "body")
        if idx >= len(suggested_doc.paragraphs):
            continue
        if base_p.text != suggested_doc.paragraphs[idx].text:
            if sec == "front_matter":
                front_matter_changed += 1
            if sec == "references":
                references_changed += 1
    manifest_path = output_dir / "manuscript_suggested_changes_manifest.json"
    manifest_path.write_text(json.dumps(changes_manifest, indent=2))
    validation_path = output_dir / "suggested_changes_validation.json"
    validation_payload = {
        "suggested_docx": str(suggested_docx),
        "manifest_path": str(manifest_path),
        "changes_proposed": len(changes_manifest),
        "changes_applied": suggested_result.get("changes_applied", 0),
        "applied_paragraph_indices": suggested_result.get("applied_paragraph_indices", []),
        "front_matter_changed_count": front_matter_changed,
        "references_changed_count": references_changed,
        "front_matter_untouched": front_matter_changed == 0,
        "references_untouched": references_changed == 0,
        **suggested_validation,
    }
    validation_path.write_text(json.dumps(validation_payload, indent=2))
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
        "suggested_changes_docx": str(suggested_docx),
        "suggested_changes_manifest": str(manifest_path),
        "suggested_changes_validation": validation_payload,
        "section_map": section_map,
    }
