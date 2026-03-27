import json
from pathlib import Path

from ai_reviewer.review.render import write_review_bundle
from ai_reviewer.review.schema import ReviewSchema


def _review() -> ReviewSchema:
    return ReviewSchema.model_validate(
        {
            "document_metadata": {"title": "Golden"},
            "summary": "Golden summary",
            "major_strengths": ["s1"],
            "major_weaknesses": ["w1"],
            "novelty_concerns": [],
            "methodological_concerns": [],
            "statistical_concerns": [],
            "writing_organization_concerns": [],
            "figure_table_concerns": [],
            "citation_reference_concerns": [],
            "reproducibility_concerns": [],
            "suggested_experiments_analyses": [],
            "recommendation": {"decision": "revise", "rationale": "ok"},
            "confidence": 0.8,
            "detailed_reviewer_comments": ["c1"],
            "section_specific_comments": [],
            "extracted_action_items": [],
            "model_debug_metadata": {
                "provider": "ollama",
                "model": "gemma3:27b",
                "temperature": 0.2,
                "parse_failures": 0,
            },
        }
    )


def test_markdown_golden_sections(tmp_path: Path):
    bundle = tmp_path / "bundle"
    write_review_bundle(bundle, _review(), raw_response="{}", repaired_response=None, warnings=[], keep_raw=True)
    md = (bundle / "reports" / "review.md").read_text(encoding="utf-8")
    assert "## Summary" in md
    assert "## Recommendation" in md
    assert "## Model Debug Metadata" in md


def test_json_golden_keys(tmp_path: Path):
    bundle = tmp_path / "bundle"
    write_review_bundle(bundle, _review(), raw_response="{}", repaired_response=None, warnings=[], keep_raw=True)
    payload = json.loads((bundle / "artifacts" / "review.validated.json").read_text(encoding="utf-8"))
    expected = {
        "document_metadata",
        "summary",
        "major_strengths",
        "major_weaknesses",
        "novelty_concerns",
        "methodological_concerns",
        "statistical_concerns",
        "writing_organization_concerns",
        "figure_table_concerns",
        "citation_reference_concerns",
        "reproducibility_concerns",
        "suggested_experiments_analyses",
        "recommendation",
        "confidence",
        "detailed_reviewer_comments",
        "section_specific_comments",
        "extracted_action_items",
        "model_debug_metadata",
    }
    assert expected.issubset(set(payload.keys()))
