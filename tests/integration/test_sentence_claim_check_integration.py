from __future__ import annotations

from ai_reviewer.review.sentence_claim_check import (
    MockExternalSearchProvider,
    run_sentence_claim_check,
)


def test_sentence_claim_check_with_mocked_external_provider_respects_privacy_gate():
    paragraphs = [
        "Chemical synthesis is central to pharmaceutical discovery and optimization.",
        "We observed 90% conversion in this manuscript under condition A.",
    ]
    section_by_idx = {0: "introduction", 1: "results"}
    mock = MockExternalSearchProvider(
        {
            "chemical synthesis central pharmaceutical discovery optimization": [
                "Background review discusses synthesis bottlenecks in medicinal chemistry."
            ]
        }
    )
    manifest = run_sentence_claim_check(
        paragraphs=paragraphs,
        section_by_idx=section_by_idx,
        provider=None,
        model=None,
        timeout_seconds=20,
        supporting_cards=None,
        external_search_enabled=True,
        external_provider=mock,
    )
    summary = manifest["summary"]
    assert summary["sentences_checked"] == 2
    assert summary["external_eligible_count"] == 1
    assert summary["external_used_count"] == 1
    assert len(mock.queries) == 1
    assert paragraphs[0].lower() not in mock.queries[0].lower()
    assert "90% conversion" not in " ".join(mock.queries).lower()
    assert manifest["search_layer"]["status"] == "mocked"
