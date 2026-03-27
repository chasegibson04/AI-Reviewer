from pathlib import Path

from ai_reviewer.ingest.loaders import parse_file
from ai_reviewer.training.takeaways import extract_takeaways


def test_takeaways_schema_and_content(tmp_path: Path):
    p = tmp_path / "guide.md"
    p.write_text(
        "# Writing Guide\n\nUse clear and concise language. Section headings should be consistent. "
        "Reviewer comments should be specific and evidence-driven.",
        encoding="utf-8",
    )
    doc = parse_file(p)
    t = extract_takeaways("abc123", "training_materials/external_guides/guide.md", "external_guides", doc)
    assert t.file_id == "abc123"
    assert t.summary
    assert t.style_guidance
    assert isinstance(t.confidence, float)

