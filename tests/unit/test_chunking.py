from ai_reviewer.ingest.chunking import chunk_document
from ai_reviewer.ingest.types import ParsedDocument
from pathlib import Path


def test_chunking_overlap_and_ids():
    doc = ParsedDocument(
        source_path=Path("a.md"),
        source_path_abs=Path("a.md"),
        source_path_rel="a.md",
        file_size_bytes=10,
        document_type="md",
        parse_engine="utf8-text",
        ingest_timestamp="2026-01-01T00:00:00+00:00",
        raw_text="x" * 8000,
        cleaned_text="x" * 8000,
    )
    chunks = chunk_document(doc, max_chars=1000, overlap=100)
    assert len(chunks) > 5
    assert chunks[0].chunk_id.endswith("000")
    assert chunks[1].start_char < chunks[1].end_char
