from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf

from ai_reviewer.config import FigureReviewConfig
from ai_reviewer.ingest.types import ParsedDocument


@dataclass
class FigureArtifact:
    figure_id: str
    page: int
    image_path: str
    caption: str
    caption_confidence: float
    page_text_excerpt: str
    caption_source: str


def _extract_captions(page_text: str) -> list[tuple[int | None, str]]:
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    captions: list[tuple[int | None, str]] = []
    for idx, line in enumerate(lines):
        match = re.search(r"(fig(ure)?|scheme|table)\\.?\\s*(\\d+)", line, re.IGNORECASE)
        if not match:
            continue
        fig_num = int(match.group(3)) if match.group(3) else None
        caption_lines = [line[match.start():]]
        for tail in lines[idx + 1 : idx + 3]:
            if re.match(r"^(fig(ure)?|scheme|table)\\.?\\s*\\d+", tail.lower()):
                break
            caption_lines.append(tail)
        captions.append((fig_num, " ".join(caption_lines)))
    return captions


def _caption_from_blocks(blocks: list[tuple], img_rect: pymupdf.Rect) -> str:
    candidates = []
    for block in blocks:
        if len(block) < 5:
            continue
        x0, y0, x1, y1, text = block[:5]
        if not text:
            continue
        text = str(text).strip()
        if not text:
            continue
        # Prefer text blocks just below the image.
        if y0 >= img_rect.y1 - 5 and y0 <= img_rect.y1 + 140:
            candidates.append((y0, text))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0])
    merged = " ".join(text for _, text in candidates).strip()
    match = re.search(r"(figure|fig\\.|scheme|table)\\s*\\d+.*", merged, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    caption = match.group(0)
    next_match = re.search(r"(figure|fig\\.|scheme|table)\\s*\\d+", caption[1:], re.IGNORECASE)
    if next_match:
        caption = caption[: next_match.start() + 1]
    caption = re.sub(r"\\s+", " ", caption).strip()
    if len(caption) > 500:
        caption = caption[:500] + "…"
    return caption


def extract_figures(pdf_path: Path, output_dir: Path, max_figures: int) -> list[FigureArtifact]:
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(str(pdf_path))
    artifacts: list[FigureArtifact] = []
    fig_index = 1
    for page_idx, page in enumerate(doc, start=1):
        images = page.get_images(full=True)
        if not images:
            continue
        page_text = page.get_text("text")
        blocks = page.get_text("blocks")
        captions = _extract_captions(page_text)
        for img in images:
            if fig_index > max_figures:
                break
            caption_num = None
            caption_text = ""
            caption_confidence = 0.1
            caption_source = "none"
            if captions:
                if len(captions) >= (fig_index - 1):
                    caption_num, caption_text = captions[min(len(captions) - 1, fig_index - 1)]
                else:
                    caption_num, caption_text = captions[0]
                if caption_text:
                    caption_confidence = 0.7
                    caption_source = "page_text"
            xref = img[0]
            img_rects = page.get_image_rects(xref)
            if img_rects:
                area = float(img_rects[0].width * img_rects[0].height)
                if area < 5000:
                    # Skip tiny decorative/logo assets.
                    continue
            if img_rects:
                block_caption = _caption_from_blocks(blocks, img_rects[0])
                if block_caption and not caption_text:
                    caption_text = block_caption
                    caption_confidence = 0.5
                    caption_source = "block_text"
            pix = pymupdf.Pixmap(doc, xref)
            if pix.n > 4:
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            img_path = output_dir / f"figure_{fig_index:03d}.png"
            pix.save(str(img_path))
            artifacts.append(
                FigureArtifact(
                    figure_id=f"figure_{fig_index:03d}",
                    page=page_idx,
                    image_path=str(img_path),
                    caption=caption_text,
                    caption_confidence=caption_confidence if caption_text else 0.1,
                    page_text_excerpt=page_text[:1200],
                    caption_source=caption_source if caption_text else "none",
                )
            )
            fig_index += 1
        if fig_index > max_figures:
            break
    return artifacts


def critique_figures(
    figures: list[FigureArtifact],
    doc: ParsedDocument,
    cfg: FigureReviewConfig,
) -> dict[str, Any]:
    critiques = []
    for fig in figures:
        caption = fig.caption.strip()
        issues = []
        visual_notes = []
        if not caption:
            issues.append("Caption not detected via PDF text extraction; figure interpretation may be limited.")
        if caption and len(caption.split()) < 12:
            issues.append("Caption is very short; may not provide enough context for interpretation.")
        if caption and re.search(r"\\b[a-c]\\b", caption.lower()) and "panel" not in caption.lower():
            issues.append("Caption references panel letters without describing panel meaning.")
        if caption and "axis" not in caption.lower() and "x" not in caption.lower() and "y" not in caption.lower():
            issues.append("Caption does not mention axes or measurement units; interpretability risk.")
        if cfg.style_checks_enabled:
            visual_notes.append("Visual assessment not performed (no local VLM support configured).")
        nearby_text = ""
        if cfg.include_nearby_text:
            if caption:
                key = caption.split()[0].lower()
                idx = doc.cleaned_text.lower().find(key)
                if idx >= 0:
                    nearby_text = doc.cleaned_text[max(0, idx - 300): idx + 600]
            if not nearby_text and fig.page_text_excerpt:
                nearby_text = fig.page_text_excerpt
        nearby_low = nearby_text.lower()
        if any(k in nearby_low for k in ["demonstrates", "proves", "confirms", "shows that"]) and fig.caption_confidence < 0.5:
            issues.append("Nearby claim language appears strong relative to low-confidence caption extraction; verify claim-to-figure support.")
        critiques.append(
            {
                "figure_id": fig.figure_id,
                "page": fig.page,
                "caption": caption,
                "caption_confidence": fig.caption_confidence,
                "caption_source": fig.caption_source,
                "content_issues": issues,
                "visual_notes": visual_notes,
                "nearby_text_excerpt": nearby_text[:800] if nearby_text else "",
            }
        )
    return {
        "figure_count": len(figures),
        "critique": critiques,
        "visual_mode": "text_only",
        "notes": [
            "Figure critique uses caption + nearby text only; no multimodal model configured.",
        ],
    }


def run_figure_review(
    doc: ParsedDocument,
    output_dir: Path,
    cfg: FigureReviewConfig,
) -> dict[str, Any]:
    if doc.document_type != "pdf":
        return {"figure_count": 0, "critique": [], "notes": ["Figure review skipped: non-PDF source."]}
    figure_dir = output_dir / "figures"
    figures = extract_figures(Path(doc.source_path_abs), figure_dir, cfg.max_figures)
    if cfg.include_captions and figures:
        global_captions = _extract_captions(doc.cleaned_text)
        if global_captions:
            for idx, fig in enumerate(figures):
                if fig.caption:
                    continue
                if idx < len(global_captions):
                    _, caption_text = global_captions[idx]
                    fig.caption = caption_text
                    fig.caption_confidence = 0.4
                    fig.caption_source = "document_text"
    critique = critique_figures(figures, doc, cfg)
    manifest = {
        "figures": [f.__dict__ for f in figures],
        "critique": critique,
    }
    (output_dir / "figure_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
