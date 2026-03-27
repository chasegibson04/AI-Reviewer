from pathlib import Path

from docx import Document

from ai_reviewer.config import load_config
from ai_reviewer.ingest.loaders import parse_file
from ai_reviewer.review.manuscript_annotation import build_annotated_manuscript_output, detect_source_mode
from ai_reviewer.tools.availability import scan_tool_availability
from ai_reviewer.tools.docx_tools import create_commented_docx_copy, parse_docx_structured
from ai_reviewer.tools.docx_tools import create_suggested_changes_docx, validate_suggested_changes_docx


def test_tool_availability_has_required_entries():
    avail = scan_tool_availability()
    assert "python_docx" in avail
    assert "pymupdf" in avail
    assert "pypdf" in avail


def test_docx_parse_and_comment_copy(tmp_path: Path):
    source = tmp_path / "source.docx"
    d = Document()
    d.add_heading("Title", level=1)
    d.add_paragraph("This is paragraph one.")
    d.add_paragraph("This is paragraph two.")
    d.save(str(source))

    parsed = parse_docx_structured(source)
    assert parsed["paragraph_count"] >= 2
    out = tmp_path / "commented.docx"
    result = create_commented_docx_copy(
        source,
        out,
        [
            {
                "paragraph_index": 1,
                "issue_type": "clarity",
                "severity": "high",
                "critique": "Sentence is vague",
                "suggested_revision": "Use concrete wording.",
                "rationale": "Improve readability",
            }
        ],
    )
    assert out.exists()
    assert result["comments_added"] >= 1
    reopened = Document(str(out))
    assert len(list(reopened.comments)) >= 1


def test_suggested_changes_docx_applies_edits(tmp_path: Path):
    source = tmp_path / "source.docx"
    d = Document()
    d.add_heading("Title", level=1)
    d.add_paragraph("Paragraph one.")
    d.add_paragraph("Paragraph two.")
    d.save(str(source))

    out = tmp_path / "suggested.docx"
    result = create_suggested_changes_docx(
        source_docx=source,
        output_docx=out,
        changes=[
            {
                "paragraph_index": 1,
                "revised_text": "Paragraph one updated.",
                "status": "applied",
            }
        ],
    )
    assert out.exists()
    assert result["changes_applied"] == 1
    reopened = Document(str(out))
    assert reopened.paragraphs[1].text == "Paragraph one updated."
    validation = validate_suggested_changes_docx(source, out)
    assert validation["structure_intact"] is True


def test_scholarly_lookup_offline_no_network():
    cfg = load_config()
    assert cfg.defaults.strict_offline is True


def test_source_mode_detection():
    assert detect_source_mode(Path("x.docx"))["mode"] == "original_docx"
    assert detect_source_mode(Path("x.pdf"))["mode"] == "pdf_only_surrogate"


def test_surrogate_annotation_preserves_text(tmp_path: Path):
    src = tmp_path / "sample.md"
    src.write_text("# T\n\nParagraph one.\n\nParagraph two.", encoding="utf-8")
    parsed = parse_file(src)

    class _R:
        section_specific_comments = []
        extracted_action_items = []
        detailed_reviewer_comments = ["Improve phrasing in intro."]
        methodological_concerns = []
        novelty_concerns = []
        citation_reference_concerns = []
        writing_organization_concerns = []
        figure_table_concerns = []
        major_weaknesses = []

    out = build_annotated_manuscript_output(src, parsed, _R(), tmp_path)
    assert Path(out["reviewed_docx"]).exists()
    assert Path(out["suggested_changes_docx"]).exists()
    assert Path(out["suggested_changes_manifest"]).exists()
    assert out["validation"]["comment_count"] >= 1
    assert out["validation"]["body_text_unchanged"] is True
    assert out["validation"]["comments_attached"] is True
    assert out["source_mode_artifact"]["source_mode"] == "surrogate_other_source"
    assert out["suggested_changes_validation"]["docx_opens"] is True
