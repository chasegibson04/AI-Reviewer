from __future__ import annotations

from pathlib import Path

import pymupdf

from ai_reviewer.figures.figure_review import extract_figures, run_figure_review
from ai_reviewer.ingest.types import ParsedDocument
from ai_reviewer.config import FigureReviewConfig


def _make_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "sample.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Figure 1: Test plot showing yield vs time.")
    rect = pymupdf.Rect(72, 120, 200, 240)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.Rect(0, 0, 64, 64))
    page.insert_image(rect, pixmap=pix)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_extract_figures(tmp_path: Path) -> None:
    pdf_path = _make_pdf(tmp_path)
    out_dir = tmp_path / "figs"
    figs = extract_figures(pdf_path, out_dir, max_figures=2)
    assert figs
    assert Path(figs[0].image_path).exists()


def test_run_figure_review(tmp_path: Path) -> None:
    pdf_path = _make_pdf(tmp_path)
    doc = ParsedDocument(
        source_path=pdf_path,
        source_path_abs=pdf_path,
        source_path_rel=str(pdf_path),
        document_type="pdf",
        raw_text="Figure 1: Test plot showing yield vs time.",
        cleaned_text="Figure 1: Test plot showing yield vs time.",
        page_count=1,
        parse_engine="pymupdf",
        parse_warnings=[],
        headings=[],
        ingest_timestamp="now",
        chunks=[],
        file_size_bytes=pdf_path.stat().st_size,
    )
    cfg = FigureReviewConfig(enabled=True, max_figures=2)
    result = run_figure_review(doc, tmp_path, cfg)
    assert result["critique"]["figure_count"] >= 1
