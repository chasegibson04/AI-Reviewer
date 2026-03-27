from pathlib import Path

from ai_reviewer.ingest.loaders import parse_file


def test_markdown_parser(tmp_path: Path):
    p = tmp_path / "doc.md"
    p.write_text("# Title\n\n## Method\nText.", encoding="utf-8")
    doc = parse_file(p)
    assert doc.document_type == "md"
    assert "Method" in " ".join(doc.headings)
