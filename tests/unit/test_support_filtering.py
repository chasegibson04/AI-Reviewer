from __future__ import annotations

from pathlib import Path

from ai_reviewer.ingest.types import ParsedDocument
from ai_reviewer.review.engine import _filter_support_docs_for_grounding


def _doc(path: Path, text: str) -> ParsedDocument:
    return ParsedDocument(
        source_path=path,
        source_path_abs=path,
        source_path_rel=path.name,
        file_size_bytes=0,
        document_type="pdf",
        parse_engine="test",
        ingest_timestamp="now",
        raw_text=text,
        cleaned_text=text,
        headings=[],
        page_count=1,
        parse_warnings=[],
        chunks=[],
    )


def test_filter_support_docs_blocks_irrelevant_markers_and_low_overlap(tmp_path: Path):
    manuscript = _doc(tmp_path / "manuscript.pdf", "Phactor workflow uses ChatGPT to design reaction arrays and optimize coupling yields.")
    good = _doc(tmp_path / "relevant.pdf", "Reaction arrays and coupling conditions in phactor workflows are compared with ChatGPT design quality.")
    low_overlap = _doc(tmp_path / "irrelevant.pdf", "Protein fold recognition benchmark and image segmentation report.")
    blocked_name = _doc(tmp_path / "BioGPT_notes.pdf", "Some overlapping words phactor reaction arrays.")

    selected, skipped, _selected_audit = _filter_support_docs_for_grounding(manuscript, [good, low_overlap, blocked_name])
    selected_names = [d.source_path.name for d in selected]
    skipped_names = [s["source"] for s in skipped]

    assert "relevant.pdf" in selected_names
    assert "irrelevant.pdf" in skipped_names
    assert "BioGPT_notes.pdf" in skipped_names
