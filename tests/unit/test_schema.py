from ai_reviewer.review.schema import ReviewSchema


def test_review_schema_validation():
    payload = {
        "document_metadata": {"title": "x"},
        "summary": "Summary",
        "major_strengths": ["a"],
        "major_weaknesses": ["b"],
        "novelty_concerns": [],
        "methodological_concerns": [],
        "statistical_concerns": [],
        "writing_organization_concerns": [],
        "figure_table_concerns": [],
        "citation_reference_concerns": [],
        "reproducibility_concerns": [],
        "suggested_experiments_analyses": [],
        "recommendation": {"decision": "revise", "rationale": "needs work"},
        "confidence": 0.75,
        "detailed_reviewer_comments": ["ok"],
        "section_specific_comments": [],
        "extracted_action_items": [],
        "model_debug_metadata": {
            "provider": "ollama",
            "model": "gemma3:27b",
            "temperature": 0.2,
            "parse_failures": 0,
        },
    }
    parsed = ReviewSchema.model_validate(payload)
    assert parsed.recommendation.decision == "revise"
