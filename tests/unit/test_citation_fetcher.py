from pathlib import Path

from ai_reviewer.config import Defaults, ReviewerConfig, CitationFetchConfig
from ai_reviewer.ingest.types import ParsedDocument
from ai_reviewer.review.citation_fetcher import extract_doi, fetch_citations_for_documents, parse_references


def _doc(tmp_path: Path, text: str) -> ParsedDocument:
    return ParsedDocument(
        source_path=tmp_path / "doc.pdf",
        source_path_abs=tmp_path / "doc.pdf",
        source_path_rel="doc.pdf",
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


def test_parse_references_basic():
    text = """
Some intro text.
REFERENCES
(1) Smith, J. A. Example paper. J. Test 2020, 1, 1-2. doi:10.1234/abc.
(2) Doe, J. Another paper. J. Test 2021, 2, 10-20.
"""
    refs = parse_references(text, max_refs=10)
    assert len(refs) == 2
    assert "Smith" in refs[0]
    assert "Doe" in refs[1]


def test_extract_doi():
    ref = "Sample title. J. Test 2020. doi:10.1234/ABC.567"
    assert extract_doi(ref) == "10.1234/abc.567"


def test_fetch_skips_strict_offline(tmp_path: Path):
    cfg = ReviewerConfig(
        defaults=Defaults(strict_offline=True),
        citation_fetch=CitationFetchConfig(enabled=True),
    )
    report = fetch_citations_for_documents(
        docs=[_doc(tmp_path, "REFERENCES\n(1) Test. doi:10.1234/abc\n")],
        project_root=tmp_path,
        cfg=cfg,
        logger=None,
        run_dir=None,
    )
    assert not report.enabled
    assert report.reason == "strict_offline"
