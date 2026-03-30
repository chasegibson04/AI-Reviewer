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


def test_fetch_runs_even_when_strict_offline_enabled(monkeypatch, tmp_path: Path):
    cfg = ReviewerConfig(
        defaults=Defaults(strict_offline=True),
        citation_fetch=CitationFetchConfig(
            enabled=True,
            methods=["dummy_method"],
            max_refs_per_doc=10,
            max_papers=10,
        ),
    )

    from ai_reviewer.review import citation_fetcher as cf

    def _dummy_method(ctx):
        return CitationMethodResult(
            status="no_oa_links",
            doi=ctx.doi or "10.1234/abc",
            title=ctx.title or "Dummy",
            source="dummy",
            candidate_count=0,
            query_audit=[{"type": "doi_lookup", "len": len(ctx.doi or "10.1234/abc")}],
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
    assert report.reason is None
    assert report.total_references == 1
    payload = __import__("json").loads((tmp_path / "artifacts" / "citation_fetch_report.json").read_text(encoding="utf-8"))
    assert payload["entries"][0]["method_attempts"][0]["query_audit"][0]["type"] == "doi_lookup"
    assert "text" not in payload["entries"][0]["method_attempts"][0]["query_audit"][0]


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


def test_fetch_report_includes_query_policy_and_query_audit(monkeypatch, tmp_path: Path):
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
        return CitationMethodResult(
            status="no_oa_links",
            doi=ctx.doi or "10.1234/abc",
            title=ctx.title or "Dummy",
            source="dummy",
            candidate_count=0,
            query_audit=[{"type": "doi_lookup", "len": len(ctx.doi or "10.1234/abc")}],
        )

    monkeypatch.setitem(cf.REGISTERED_CITATION_METHODS, "dummy_method", _dummy_method)
    fetch_citations_for_documents(
        docs=[_doc(tmp_path, "REFERENCES\n(1) Test. doi:10.1234/abc\n")],
        project_root=tmp_path,
        cfg=cfg,
        logger=None,
        run_dir=tmp_path,
    )
    payload_path = tmp_path / "artifacts" / "citation_fetch_report.json"
    payload = __import__("json").loads(payload_path.read_text(encoding="utf-8"))
    assert payload["query_policy"]["no_manuscript_raw_text"] is True
    assert payload["query_policy"]["no_long_manuscript_excerpts"] is True
    assert payload["query_policy"]["no_support_paper_full_text"] is True
    assert payload["entries"][0]["method_attempts"][0]["query_audit"][0]["type"] == "doi_lookup"
    assert "text" not in payload["entries"][0]["method_attempts"][0]["query_audit"][0]


def test_fetch_report_distinguishes_citation_existence_from_support(monkeypatch, tmp_path: Path):
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
        return CitationMethodResult(
            status="already_present_by_local_match",
            saved_path=str(tmp_path / "materials" / "other" / "matched.pdf"),
            doi="10.1234/abc",
            title="Predicting Reaction Outcomes",
            source="dummy",
            candidate_count=1,
            query_audit=[{"type": "local_pdf_title_match", "len": 27}],
        )

    monkeypatch.setitem(cf.REGISTERED_CITATION_METHODS, "dummy_method", _dummy_method)
    report = fetch_citations_for_documents(
        docs=[_doc(tmp_path, 'REFERENCES\n(1) "Predicting Reaction Outcomes" J. Test 2020.\n')],
        project_root=tmp_path,
        cfg=cfg,
        logger=None,
        run_dir=tmp_path,
    )
    verification = report.entries[0]["verification"]
    assert verification["citation_exists"] is True
    assert verification["metadata_match_likely"] is True
    assert verification["support_relationship"] == "not_verified"
    assert verification["verification_scope"] == "external_metadata_check_only"
    assert verification["needs_human_verification"] is True


def test_fetch_local_project_pdf_match_fallback(tmp_path: Path):
    cfg = ReviewerConfig(
        defaults=Defaults(strict_offline=False),
        citation_fetch=CitationFetchConfig(
            enabled=True,
            methods=["local_project_pdf_match"],
            max_refs_per_doc=10,
            max_papers=10,
        ),
    )
    other = tmp_path / "materials" / "other"
    other.mkdir(parents=True, exist_ok=True)
    existing = other / "Predicting_Reaction_Outcomes_Local_Copy.pdf"
    existing.write_bytes(b"%PDF-1.4\n")

    report = fetch_citations_for_documents(
        docs=[_doc(tmp_path, 'REFERENCES\n(1) "Predicting Reaction Outcomes" J. Test 2020.\n')],
        project_root=tmp_path,
        cfg=cfg,
        logger=None,
        run_dir=tmp_path,
    )
    assert report.enabled
    assert report.entries[0]["status"] == "already_present_by_local_match"


def test_fetch_default_method_order_includes_fallbacks(tmp_path: Path):
    cfg = ReviewerConfig(
        defaults=Defaults(strict_offline=False),
        citation_fetch=CitationFetchConfig(enabled=True, methods=[]),
    )
    fetch_citations_for_documents(
        docs=[_doc(tmp_path, "REFERENCES\n(1) Test. doi:10.1234/abc\n")],
        project_root=tmp_path,
        cfg=cfg,
        logger=None,
        run_dir=tmp_path,
    )
    payload = __import__("json").loads((tmp_path / "artifacts" / "citation_fetch_report.json").read_text(encoding="utf-8"))
    assert "local_project_pdf_match" in payload["methods"]
    assert "crossref_short_title_then_oa" in payload["methods"]
