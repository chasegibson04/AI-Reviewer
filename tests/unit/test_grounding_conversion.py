import json
from pathlib import Path
from ai_reviewer.review.manuscript_annotation import review_to_comment_entries
from ai_reviewer.review.schema import ReviewSchema, Recommendation, DebugMetadata, GroundedComment, SectionComment

def test_grounded_comment_promotion(tmp_path: Path):
    # Mock ReviewSchema with the new grounded_detailed_comments field
    review = ReviewSchema(
        summary="Test",
        recommendation=Recommendation(decision="revise", rationale="test"),
        confidence=0.9,
        detailed_reviewer_comments=["Generic string comment"],
        grounded_detailed_comments=[
            GroundedComment(
                comment="This specific claim is contradicted by Evidence A.",
                evidence_source="evidence_a.pdf",
                manuscript_quote="We found X to be true.",
                severity="high"
            )
        ],
        section_specific_comments=[
            SectionComment(
                section="Methods",
                comment="This section is entirely missing a required negative control for the assay.",
                severity="medium",
                evidence_source="methods_guide.pdf",
                manuscript_quote="We used method Y."
            )
        ],
        extracted_action_items=[],
        model_debug_metadata=DebugMetadata(provider="test", model="test", temperature=0)
    )
    
    entries = review_to_comment_entries(review, max_comments=10)
    print(f"DEBUG: ENTRIES={json.dumps(entries, indent=2)}")
    
    # Check if GroundedComment was promoted
    grounded = [e for e in entries if e["issue_type"] == "grounded review"]
    assert len(grounded) == 1
    assert grounded[0]["critique"] == "This specific claim is contradicted by Evidence A."
    assert grounded[0]["evidence_source"] == "evidence_a.pdf"
    assert grounded[0]["manuscript_quote"] == "We found X to be true."
    
    # Check if SectionComment carried over evidence_source
    section = [e for e in entries if e["issue_type"] == "section_issue"]
    assert len(section) == 1
    assert section[0]["evidence_source"] == "methods_guide.pdf"
    assert section[0]["manuscript_quote"] == "We used method Y."

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
