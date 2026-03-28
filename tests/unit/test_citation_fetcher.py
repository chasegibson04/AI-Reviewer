from pathlib import Path

from ai_reviewer.config import Defaults, ReviewerConfig, CitationFetchConfig
from ai_reviewer.ingest.types import ParsedDocument
from ai_reviewer.review.citation_fetcher import (
    CitationMethodResult,
    extract_doi,
    fetch_citations_for_documents,
    parse_references,
)


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


def test_fetch_uses_configured_methods(monkeypatch, tmp_path: Path):
    cfg = ReviewerConfig(
        defaults=Defaults(strict_offline=False),
        citation_fetch=CitationFetchConfig(
            enabled=True,
            methods=["dummy_method"],
            max_refs_per_doc=10,
            max_papers=10,
        ),
    )

    from ai_reviewer.review import citation_fetcher as cf

    def _dummy_method(ctx):
        dest = ctx.dest_dir / "dummy.pdf"
        dest.write_bytes(b"%PDF-1.4\n")
        return CitationMethodResult(
            status="downloaded:dummy",
            saved_path=str(dest),
            doi=ctx.doi or "10.1111/dummy",
            title=ctx.title or "Dummy",
            source="dummy",
            candidate_count=1,
        )

    monkeypatch.setitem(cf.REGISTERED_CITATION_METHODS, "dummy_method", _dummy_method)
    report = fetch_citations_for_documents(
        docs=[_doc(tmp_path, "REFERENCES\n(1) Test. doi:10.1234/abc\n")],
        project_root=tmp_path,
        cfg=cfg,
        logger=None,
        run_dir=tmp_path,
    )
    assert report.enabled
    assert report.total_downloaded == 1
    saved = tmp_path / "materials" / "other" / "dummy.pdf"
    assert saved.exists()


def test_fetch_uses_doi_cache_before_download(monkeypatch, tmp_path: Path):
    cfg = ReviewerConfig(
        defaults=Defaults(strict_offline=False),
        citation_fetch=CitationFetchConfig(
            enabled=True,
            methods=["doi_open_access_apis"],
            max_refs_per_doc=10,
            max_papers=10,
        ),
    )
    other = tmp_path / "materials" / "other"
    other.mkdir(parents=True, exist_ok=True)
    cached_pdf = other / "cached.pdf"
    cached_pdf.write_bytes(b"%PDF-1.4\n")
    (other / "citation_doi_cache.json").write_text(
        '{"10.1234/abc":"%s"}' % str(cached_pdf).replace("\\", "\\\\"),
        encoding="utf-8",
    )

    # Ensure network path is never used when cache is hit.
    from ai_reviewer.review import citation_fetcher as cf

    def _no_network(*args, **kwargs):
        raise AssertionError("network should not be called on cache hit")

    monkeypatch.setattr(cf, "_requests_get", _no_network)
    report = fetch_citations_for_documents(
        docs=[_doc(tmp_path, "REFERENCES\n(1) Test. doi:10.1234/abc\n")],
        project_root=tmp_path,
        cfg=cfg,
        logger=None,
        run_dir=tmp_path,
    )
    assert report.enabled
    assert report.total_downloaded == 0
    assert report.entries[0]["status"] == "already_present_by_cache"
