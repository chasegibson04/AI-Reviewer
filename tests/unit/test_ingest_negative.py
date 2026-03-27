from pathlib import Path

from ai_reviewer.ingest.loaders import parse_file, parse_path_with_failures


def test_parse_path_with_failures_continues(tmp_path: Path):
    good = tmp_path / "good.md"
    bad = tmp_path / "bad.xyz"
    good.write_text("# Title\n\ntext", encoding="utf-8")
    bad.write_text("nope", encoding="utf-8")

    docs, failures = parse_path_with_failures(tmp_path, continue_on_error=True)
    assert len(docs) == 1
    assert len(failures) == 0  # unsupported extension should not be collected by scanner


def test_unsupported_extension_raises(tmp_path: Path):
    bad = tmp_path / "bad.xyz"
    bad.write_text("x", encoding="utf-8")
    try:
        parse_file(bad)
    except ValueError as exc:
        assert "Unsupported file type" in str(exc)
