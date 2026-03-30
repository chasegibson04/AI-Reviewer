from __future__ import annotations

from ai_reviewer.review.rigorous_adapters import (
    build_deep_reconciliation_summary,
    build_specialist_qc_summary,
)
from ai_reviewer.review.schema import (
    ActionItem,
    DebugMetadata,
    Recommendation,
    ReviewSchema,
    SectionComment,
)


def _sample_review() -> ReviewSchema:
    return ReviewSchema(
        document_metadata={"title": "T"},
        summary="Clear manuscript with a few issues.",
        major_strengths=["Strong methods framing."],
        major_weaknesses=["Clarify this section.", "Add more detail."],
        novelty_concerns=["Novelty positioning could be tighter."],
        methodological_concerns=["Control condition details are incomplete."],
        statistical_concerns=["Replicate count is not clearly reported."],
        writing_organization_concerns=["Clarify the paragraph transition.", "Sentence is overloaded and hard to parse."],
        figure_table_concerns=[],
        citation_reference_concerns=["Two claims appear under-cited."],
        reproducibility_concerns=["Provide seed and randomization details."],
        suggested_experiments_analyses=[],
        recommendation=Recommendation(decision="revise", rationale="Needs revision"),
        confidence=0.71,
        detailed_reviewer_comments=[
            "Clarify this section.",
            "Rewrite sentence in the abstract for calibration.",
        ],
        section_specific_comments=[
            SectionComment(section="Abstract", comment="Claim language is broad.", severity="medium", evidence_source=None, manuscript_quote=None),
            SectionComment(section="Methods", comment="Specify control workflow.", severity="high", evidence_source=None, manuscript_quote=None),
        ],
        extracted_action_items=[
            ActionItem(action="Add explicit control condition description.", priority="high", owner="author", evidence_source=None)
        ],
        model_debug_metadata=DebugMetadata(provider="ollama", model="m", temperature=0.1),
    )


def test_build_specialist_qc_summary_shape_and_scores() -> None:
    review = _sample_review()
    out = build_specialist_qc_summary(review)
    assert "specialist_counts" in out
    assert "qc_flags" in out
    assert "category_scores_0_to_5" in out
    scores = out["category_scores_0_to_5"]
    assert 0.0 <= scores["section_specificity_score"] <= 5.0
    assert 0.0 <= scores["rigor_score"] <= 5.0
    assert 0.0 <= scores["writing_score"] <= 5.0
    assert out["qc_flags"]["generic_item_count"] >= 1


def test_build_deep_reconciliation_summary_shape() -> None:
    payload = {
        "consolidated_strengths": ["Clear contribution statement."],
        "consolidated_weaknesses": ["Clarify this section.", "Clarify this section."],
        "priority_actions": ["Clarify this section."],
        "revision_plan": ["Revise abstract claims."],
        "confidence_notes": ["Offline-only validation; support not verified."],
    }
    out = build_deep_reconciliation_summary(payload)
    qc = out["reconciliation_qc"]
    assert qc["duplicate_cross_field_count"] >= 1
    assert qc["unresolved_risk_notes"]
    assert 0.0 <= out["reconciliation_quality_score_0_to_5"] <= 5.0
