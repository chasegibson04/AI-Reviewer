from __future__ import annotations

import re

from ai_reviewer.ingest.types import ParsedDocument
from ai_reviewer.training.schema import TrainingCategory, TrainingTakeaways


def _sentences(text: str) -> list[str]:
    raw = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
    return [s.strip() for s in raw if len(s.strip()) > 40]


def _pick_sentences(text: str, keywords: list[str], max_items: int = 4) -> list[str]:
    out: list[str] = []
    sents = _sentences(text)
    for s in sents:
        lower = s.lower()
        if any(k in lower for k in keywords):
            out.append(s[:220])
        if len(out) >= max_items:
            break
    if not out:
        out = [s[:220] for s in sents[:max_items]]
    return out


def _dedupe_keep_order(items: list[str], max_items: int = 8) -> list[str]:
    seen = set()
    out = []
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
        if len(out) >= max_items:
            break
    return out


def extract_takeaways(file_id: str, source_path: str, category: TrainingCategory, doc: ParsedDocument) -> TrainingTakeaways:
    text = doc.cleaned_text[:50000]
    headings = doc.headings[:20]
    style_keys = ["clear", "concise", "novel", "contribution", "results", "method", "evidence"]
    formatting_keys = ["section", "figure", "table", "format", "layout", "heading", "appendix", "color"]
    language_keys = ["grammar", "wording", "phrase", "tense", "voice", "clarity", "readability"]
    tone_keys = ["limitation", "however", "we recommend", "should", "must", "concern", "weakness"]

    if category == "formatting_color_guides":
        formatting_keys += ["font", "palette", "spacing", "margin", "style", "brand"]
    if category == "external_guides":
        tone_keys += ["policy", "requirement", "editor", "reviewer", "criteria", "journal"]
    if category == "published_papers":
        style_keys += ["abstract", "introduction", "discussion", "related work", "conclusion"]
    if category == "other_groups_papers":
        style_keys += ["baseline", "ablation", "comparison", "state of the art"]
    if category == "in_progress_examples":
        language_keys += ["draft", "revision", "todo", "rewrite"]

    style_guidance = _dedupe_keep_order(_pick_sentences(text, style_keys))
    formatting_guidance = _dedupe_keep_order(_pick_sentences(text, formatting_keys))
    language_guidance = _dedupe_keep_order(_pick_sentences(text, language_keys))
    reviewer_tone = _dedupe_keep_order(_pick_sentences(text, tone_keys))
    conventions = _dedupe_keep_order([f"Use heading pattern similar to: {h}" for h in headings[:6]])
    summary = f"{category.replace('_', ' ').title()} guidance extracted from {source_path.split('/')[-1] if '/' in source_path else source_path}."

    confidence = 0.75
    quality_notes = []
    warnings = list(doc.parse_warnings)
    if len(doc.cleaned_text) < 1200:
        quality_notes.append("Short document; takeaways may be less representative.")
        confidence = 0.55
    if warnings:
        confidence = max(0.35, confidence - 0.2)

    return TrainingTakeaways(
        file_id=file_id,
        source_path=source_path,
        category=category,
        summary=summary,
        style_guidance=style_guidance,
        formatting_layout_guidance=formatting_guidance,
        language_grammar_guidance=language_guidance,
        reviewer_tone_guidance=reviewer_tone,
        notable_conventions=conventions,
        confidence=confidence,
        quality_notes=quality_notes,
        warnings=warnings,
    )

