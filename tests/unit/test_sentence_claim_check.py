from __future__ import annotations

from ai_reviewer.review.sentence_claim_check import (
    SENTENCE_CATEGORY_LITERATURE,
    SENTENCE_CATEGORY_MANUSCRIPT,
    SENTENCE_CATEGORY_PUBLIC,
    SENTENCE_CATEGORY_STYLE_ONLY,
    VERDICT_LIKELY_OVERCLAIM,
    VERDICT_NEEDS_CITATION,
    VERDICT_UNCLEAR_SUPPORT,
    claim_check_results_to_comment_entries,
    classify_sentence,
    project_claim_check_comments,
    privacy_gate,
    render_sentence_claim_check_summary_markdown,
    run_sentence_claim_check,
    segment_reviewable_sentences,
)


class _AlwaysFailProvider:
    def __init__(self):
        self.calls = 0

    def list_models(self):
        return ["gemma4:31b"]

    def chat(self, request):
        self.calls += 1
        raise RuntimeError("empty_response")


def test_sentence_segmentation_keeps_stable_ids_and_sections():
    paragraphs = [
        "Cover page title",
        "Chemical synthesis is central to drug discovery. It often requires optimization.",
        "We observed 90% yield under condition A.",
    ]
    section_by_idx = {0: "front_matter", 1: "introduction", 2: "results"}
    sentences = segment_reviewable_sentences(paragraphs, section_by_idx)
    assert [s.sentence_id for s in sentences] == ["p0001.s000", "p0001.s001", "p0002.s000"]
    assert [s.section for s in sentences] == ["introduction", "introduction", "results"]


def test_sentence_segmentation_skips_reference_and_caption_artifacts():
    paragraphs = [
        "Nature 557, 228-232 (2018).",
        "Figure 2. Heatmap of conversion to product.",
        "The manuscript was written through contributions of all authors.",
        "Chemical synthesis is central to drug discovery.",
    ]
    section_by_idx = {0: "body", 1: "results", 2: "discussion", 3: "introduction"}
    sentences = segment_reviewable_sentences(paragraphs, section_by_idx)
    assert [s.sentence_id for s in sentences] == ["p0003.s000"]
    assert sentences[0].text == "Chemical synthesis is central to drug discovery."


def test_sentence_classification_categories():
    assert classify_sentence("Chemical synthesis enables drug discovery.", "introduction") == SENTENCE_CATEGORY_PUBLIC
    assert (
        classify_sentence("Previous studies reported similar trends [12].", "introduction")
        == SENTENCE_CATEGORY_LITERATURE
    )
    assert (
        classify_sentence("We observed 90% conversion in this study.", "results")
        == SENTENCE_CATEGORY_MANUSCRIPT
    )
    assert classify_sentence("Figure 2.", "results") == SENTENCE_CATEGORY_STYLE_ONLY
    assert classify_sentence("Nature 557, 228-232 (2018).", "results") == SENTENCE_CATEGORY_STYLE_ONLY
    assert (
        classify_sentence("The manuscript was written through contributions of all authors.", "discussion")
        == SENTENCE_CATEGORY_STYLE_ONLY
    )


def test_privacy_gate_allows_public_and_blocks_manuscript_specific():
    safe = privacy_gate("Chemical synthesis enables drug discovery broadly.", SENTENCE_CATEGORY_PUBLIC)
    unsafe = privacy_gate("We observed 90% conversion in this study.", SENTENCE_CATEGORY_MANUSCRIPT)
    assert safe.safe_for_external_search is True
    assert safe.minimized_query is not None and safe.minimized_query
    assert unsafe.safe_for_external_search is False
    assert unsafe.minimized_query is None


def test_privacy_gate_allows_cited_ambiguous_public_claim_but_blocks_manuscript_markers():
    safe_ambiguous = privacy_gate(
        "Prior analyses observed this trend across related systems (2019).",
        "ambiguous/mixed",
    )
    blocked_ambiguous = privacy_gate(
        "In this study, we observed this trend in our reaction array (2019).",
        "ambiguous/mixed",
    )
    assert safe_ambiguous.safe_for_external_search is True
    assert safe_ambiguous.reason == "ambiguous_but_public_cited_claim"
    assert safe_ambiguous.minimized_query
    assert blocked_ambiguous.safe_for_external_search is False
    assert blocked_ambiguous.minimized_query is None


def test_provider_abstraction_local_only_when_external_disabled():
    paragraphs = [
        "Chemical synthesis enables drug discovery and reaction optimization.",
        "We observed 90% conversion in this study.",
    ]
    section_by_idx = {0: "introduction", 1: "results"}
    manifest = run_sentence_claim_check(
        paragraphs=paragraphs,
        section_by_idx=section_by_idx,
        provider=None,
        model=None,
        timeout_seconds=20,
        supporting_cards=None,
        external_search_enabled=False,
        external_provider=None,
    )
    summary = manifest["summary"]
    assert summary["sentences_checked"] == 2
    assert summary["external_used_count"] == 0
    assert summary["local_only_count"] == 2
    assert manifest["search_layer"]["status"] == "disabled"


def test_literature_claim_with_citation_defaults_to_partially_supported_under_fallback():
    paragraphs = ["Previous studies reported this trend in similar systems [12]."]
    section_by_idx = {0: "introduction"}
    manifest = run_sentence_claim_check(
        paragraphs=paragraphs,
        section_by_idx=section_by_idx,
        provider=None,
        model=None,
        timeout_seconds=20,
        supporting_cards=None,
        external_search_enabled=False,
        external_provider=None,
    )
    assert manifest["summary"]["sentences_checked"] == 1
    assert manifest["sentences"][0]["verdict"] == "partially supported"


def test_claim_check_fail_fast_disables_llm_after_first_error():
    paragraphs = [
        "Chemical synthesis enables drug discovery in many contexts.",
        "Previous studies reported similar trends [12].",
    ]
    section_by_idx = {0: "introduction", 1: "introduction"}
    provider = _AlwaysFailProvider()
    manifest = run_sentence_claim_check(
        paragraphs=paragraphs,
        section_by_idx=section_by_idx,
        provider=provider,
        model="fallback-model",
        timeout_seconds=20,
        supporting_cards=None,
        external_search_enabled=False,
        external_provider=None,
    )
    assert manifest["summary"]["sentences_checked"] == 2
    assert provider.calls == 1
    assert manifest["model"]["fail_fast_fallback_triggered"] is True


def test_output_verdict_mapping_to_comment_entries():
    manifest = {
        "sentences": [
            {
                "sentence_id": "p0001.s000",
                "paragraph_index": 1,
                "sentence_text": "This claim is always true in every case.",
                "verdict": VERDICT_LIKELY_OVERCLAIM,
                "feedback": "Wording is broader than support.",
                "privacy": {"safe_for_external_search": False, "reason": "manuscript_specific_or_novel"},
            },
            {
                "sentence_id": "p0001.s001",
                "paragraph_index": 1,
                "sentence_text": "Prior work showed this trend.",
                "verdict": VERDICT_NEEDS_CITATION,
                "feedback": "Cite a direct source.",
                "privacy": {"safe_for_external_search": True, "reason": "public_literature_claim"},
            },
            {
                "sentence_id": "p0001.s002",
                "paragraph_index": 1,
                "sentence_text": "Support is uncertain in this sentence.",
                "verdict": VERDICT_UNCLEAR_SUPPORT,
                "feedback": "Evidence remains unclear.",
                "privacy": {"safe_for_external_search": False, "reason": "ambiguous_or_mixed_claim"},
            },
        ]
    }
    comments = claim_check_results_to_comment_entries(manifest, max_comments=5)
    assert len(comments) == 2
    assert comments[0]["issue_type"] == "evidence/overclaim"
    assert comments[1]["issue_type"] == "wording/precision"


def test_comment_mapping_suppresses_reference_line_needs_citation():
    manifest = {
        "sentences": [
            {
                "sentence_id": "p0100.s001",
                "paragraph_index": 100,
                "section": "results",
                "category": SENTENCE_CATEGORY_LITERATURE,
                "sentence_text": "Nature 557, 228-232 (2018).",
                "verdict": VERDICT_NEEDS_CITATION,
                "feedback": "Literature-style claim lacks explicit citation in sentence.",
                "action": "add citation",
                "privacy": {"safe_for_external_search": True, "reason": "public_literature_claim"},
            }
        ]
    }
    comments = claim_check_results_to_comment_entries(manifest, max_comments=5)
    assert comments == []


def test_comment_mapping_uses_only_materially_useful_rewrite():
    manifest = {
        "sentences": [
            {
                "sentence_id": "p0003.s002",
                "paragraph_index": 3,
                "section": "discussion",
                "category": SENTENCE_CATEGORY_PUBLIC,
                "sentence_text": "This method is always superior for all cases.",
                "verdict": VERDICT_LIKELY_OVERCLAIM,
                "feedback": "High-certainty wording appears broader than available support.",
                "action": "narrow claim",
                "rewrite": "This method may be superior for the tested cases.",
                "privacy": {"safe_for_external_search": False, "reason": "ambiguous_or_mixed_claim"},
            },
            {
                "sentence_id": "p0003.s003",
                "paragraph_index": 3,
                "section": "discussion",
                "category": SENTENCE_CATEGORY_PUBLIC,
                "sentence_text": "Support remains uncertain in this sentence.",
                "verdict": VERDICT_UNCLEAR_SUPPORT,
                "feedback": "Support remains unclear from available local evidence.",
                "action": "add citation",
                "rewrite": "Support remains uncertain in this sentence.",
                "privacy": {"safe_for_external_search": False, "reason": "ambiguous_or_mixed_claim"},
            },
        ]
    }
    comments = claim_check_results_to_comment_entries(manifest, max_comments=5)
    assert len(comments) == 2
    assert comments[0]["suggested_revision"].startswith("Proposed edit:")
    assert comments[1]["suggested_revision"] == "Add a citation directly after this sentence."


def test_comment_mapping_suppresses_reference_title_question_overclaim():
    manifest = {
        "sentences": [
            {
                "sentence_id": "p0108.s002",
                "paragraph_index": 108,
                "section": "introduction",
                "category": SENTENCE_CATEGORY_PUBLIC,
                "sentence_text": "Analysis of past and present synthetic methodologies on medicinal chemistry: where have all the new reactions gone?",
                "verdict": VERDICT_LIKELY_OVERCLAIM,
                "feedback": "High-certainty wording appears broader than available support.",
                "action": "narrow claim",
                "privacy": {"safe_for_external_search": True, "reason": "public_background_claim"},
            }
        ]
    }
    assert claim_check_results_to_comment_entries(manifest, max_comments=5) == []


def test_comment_projection_suppresses_low_information_and_citation_dense_rows():
    manifest = {
        "sentences": [
            {
                "sentence_id": "p0001.s000",
                "paragraph_index": 1,
                "section": "introduction",
                "category": SENTENCE_CATEGORY_LITERATURE,
                "sentence_text": "This is supported [1][2][3].",
                "verdict": VERDICT_NEEDS_CITATION,
                "feedback": "Add citation.",
                "action": "add citation",
                "privacy": {"safe_for_external_search": True, "reason": "public_literature_claim"},
            },
            {
                "sentence_id": "p0001.s001",
                "paragraph_index": 1,
                "section": "introduction",
                "category": SENTENCE_CATEGORY_PUBLIC,
                "sentence_text": "Likely true.",
                "verdict": VERDICT_UNCLEAR_SUPPORT,
                "feedback": "Unclear support.",
                "action": "add citation",
                "privacy": {"safe_for_external_search": True, "reason": "public_background_claim"},
            },
            {
                "sentence_id": "p0001.s002",
                "paragraph_index": 1,
                "section": "discussion",
                "category": SENTENCE_CATEGORY_PUBLIC,
                "sentence_text": "This claim is always true in every tested scenario.",
                "verdict": VERDICT_LIKELY_OVERCLAIM,
                "feedback": "Wording is broader than support.",
                "action": "narrow claim",
                "privacy": {"safe_for_external_search": False, "reason": "ambiguous_or_mixed_claim"},
            },
        ]
    }
    projection = project_claim_check_comments(manifest, max_comments=8)
    assert len(projection["entries"]) == 1
    assert projection["entries"][0]["claim_check_verdict"] == VERDICT_LIKELY_OVERCLAIM
    counts = projection["summary"]["suppressed_reason_counts"]
    assert counts.get("citation_dense_fragment", 0) + counts.get("figure_table_or_artifact_line", 0) >= 1
    assert counts.get("low_information_sentence", 0) >= 1


def test_privacy_gate_blocks_literature_line_with_local_markers():
    blocked = privacy_gate(
        "Our study reported 90% conversion in this reaction array [12].",
        SENTENCE_CATEGORY_LITERATURE,
    )
    assert blocked.safe_for_external_search is False
    assert blocked.reason == "literature_sentence_contains_local_markers"
    assert blocked.minimized_query is None


def test_sentence_claim_check_summary_markdown_includes_projection_counts():
    manifest = {
        "summary": {
            "sentences_checked": 3,
            "category_counts": {SENTENCE_CATEGORY_PUBLIC: 1},
            "verdict_counts": {VERDICT_LIKELY_OVERCLAIM: 1},
            "local_only_count": 3,
            "external_eligible_count": 1,
            "external_used_count": 0,
        },
        "model": {"selected_model": None, "gemma4_31b_used": False, "fallback_used": True},
        "search_layer": {"status": "disabled"},
        "comment_projection": {
            "summary": {
                "candidate_count": 2,
                "surfaced_count": 1,
                "suppressed_count": 1,
                "suppressed_reason_counts": {"verdict_not_actionable": 1},
                "high_value_surfaced_count": 1,
                "low_value_surfaced_count": 0,
            },
            "suppressed_examples": {"verdict_not_actionable": ["p0001.s001"]},
        },
    }
    md = render_sentence_claim_check_summary_markdown(manifest)
    assert "Surfaced comments: 1" in md
    assert "Suppressed rows: 1" in md
    assert "verdict_not_actionable: 1" in md
