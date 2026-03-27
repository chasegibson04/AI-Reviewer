from ai_reviewer.review.render import render_markdown
from ai_reviewer.review.schema import ReviewSchema


def _sample_review() -> ReviewSchema:
    return ReviewSchema.model_validate(
        {
            "document_metadata": {"title": "Paper"},
            "summary": "A summary",
            "major_strengths": ["Strong"],
            "major_weaknesses": ["Weak"],
            "novelty_concerns": [],
            "methodological_concerns": [],
            "statistical_concerns": [],
            "writing_organization_concerns": [],
            "figure_table_concerns": [],
            "citation_reference_concerns": [],
            "reproducibility_concerns": [],
            "suggested_experiments_analyses": [],
            "recommendation": {"decision": "revise", "rationale": "x"},
            "confidence": 0.5,
            "detailed_reviewer_comments": ["detail"],
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


def test_render_markdown_contains_sections():
    text = render_markdown(_sample_review())
    assert "## Summary" in text
    assert "## Recommendation" in text
    assert "Major Strengths" in text
