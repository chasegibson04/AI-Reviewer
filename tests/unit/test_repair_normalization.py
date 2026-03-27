from ai_reviewer.review.repair import parse_and_repair


class DummyProvider:
    def chat(self, request):  # pragma: no cover - should not be called in this test
        raise RuntimeError("unexpected model repair call")


def test_parse_and_repair_normalizes_wrapped_review():
    raw = """```json
{
  "review": {
    "overall_assessment": "Strong contribution",
    "strengths": ["clear design"],
    "weaknesses": ["limited baselines"],
    "methodological_issues": ["single dataset"],
    "writing_issues": ["intro is long"],
    "decision": "revise",
    "comments": ["needs stronger ablations"],
    "action_items": ["add baseline table"]
  }
}
```"""
    out = parse_and_repair(
        raw,
        provider=DummyProvider(),  # type: ignore[arg-type]
        repair_models=["mistral-small3.1:24b"],
        timeout_seconds=30,
        logger=__import__("logging").getLogger("test"),
        primary_model="gemma3:27b",
        allow_self_repair=False,
    )
    assert out.parsed is not None
    assert out.parsed.summary == "Strong contribution"
    assert out.parsed.major_strengths
    assert out.parsed.major_weaknesses
    assert out.parsed.recommendation.decision == "revise"
    assert out.parsed.extracted_action_items


def test_parse_and_repair_normalizes_legacy_review_shape():
    raw = """```json
{
  "title": "Review of Manuscript",
  "overall_assessment": "Useful manuscript with clear workflow.",
  "strengths": ["Clear workflow"],
  "weaknesses": ["Needs broader validation"],
  "detailed_comments": [{"section": "Methods", "comment": "Add prompt details."}],
  "specific_suggestions": ["Expand substrate scope", "Report uncertainty"],
  "recommendation": "Accept with minor revisions"
}
```"""
    out = parse_and_repair(
        raw,
        provider=DummyProvider(),  # type: ignore[arg-type]
        repair_models=["mistral-small3.1:24b"],
        timeout_seconds=30,
        logger=__import__("logging").getLogger("test"),
        primary_model="gemma3:27b",
        allow_self_repair=False,
    )
    assert out.parsed is not None
    assert out.parsed.summary.startswith("Useful manuscript")
    assert out.parsed.document_metadata.get("title") == "Review of Manuscript"
    assert out.parsed.recommendation.decision in {"accept", "revise"}
    assert len(out.parsed.extracted_action_items) >= 2
    assert any("Methods" in c for c in out.parsed.detailed_reviewer_comments)
