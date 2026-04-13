from __future__ import annotations

from ai_reviewer.eval.comment_quality import compare_metric_dicts, compute_comment_quality_metrics, evaluate_rewrite_pair


def test_evaluate_rewrite_pair_detects_noop_and_material_improvement():
    no_op = evaluate_rewrite_pair("This sentence is clear enough.", "This sentence is clear enough.")
    assert no_op["no_op"] is True
    improved = evaluate_rewrite_pair(
        "This sentence is very long, and it includes several clauses, and it becomes hard to parse.",
        "This sentence is long and includes several clauses. It is hard to parse.",
    )
    assert improved["materially_better"] is True


def test_compute_comment_quality_metrics_core_fields():
    manifest = {
        "comment_targets": [
            {
                "paragraph_index": 3,
                "issue_type": "style/clarity",
                "critique": "Split this into two sentences to separate setup from outcome.",
                "suggested_revision": "Proposed edit: We tested condition A. We observed 90% conversion.",
                "anchor_text": "We tested condition A and observed 90% conversion in one run.",
                "from_style_pass": True,
                "style_issue_kind": "overloaded_sentence",
            },
            {
                "paragraph_index": 3,
                "issue_type": "wording/precision",
                "critique": "Improve clarity.",
                "suggested_revision": "Add a citation directly after this claim.",
                "anchor_text": "This claim has no citation.",
                "from_claim_check": True,
                "claim_check_verdict": "needs citation",
            },
            {
                "paragraph_index": 3,
                "issue_type": "wording/precision",
                "critique": "Improve clarity.",
                "suggested_revision": "Add a citation directly after this claim.",
                "anchor_text": "This claim has no citation.",
            },
        ],
        "style_clarity_pass": {"summary": {"candidate_count": 10, "rewrites_suppressed": 4}},
        "sentence_claim_check": {
            "search_layer": {"enabled": False, "status": "disabled", "provider": None},
            "summary": {
                "sentences_checked": 2,
                "verdict_counts": {
                    "needs citation": 1,
                    "likely overclaim": 0,
                    "wording stronger than evidence": 0,
                    "unclear support": 1,
                },
            },
            "comment_projection": {
                "summary": {
                    "candidate_count": 3,
                    "surfaced_count": 1,
                    "suppressed_count": 2,
                    "suppressed_reason_counts": {"verdict_not_actionable": 2},
                }
            },
            "sentences": [
                {
                    "sentence_id": "p0001.s001",
                    "sentence_text": "Prior work reported this outcome [12].",
                    "category": "literature/citation-supported claim",
                    "privacy": {"safe_for_external_search": True, "reason": "public_literature_claim"},
                    "used_external_search": False,
                },
                {
                    "sentence_id": "p0002.s000",
                    "sentence_text": "We observed 90% conversion in this study.",
                    "category": "manuscript-specific result or novel assertion",
                    "privacy": {"safe_for_external_search": False, "reason": "manuscript_specific_or_novel"},
                    "used_external_search": False,
                },
            ],
        },
        "comment_response_manifest": {
            "summary": {"existing_comments_detected": 2, "responses_generated": 2},
            "responses": [
                {"response_type": "text_fix", "proposed_response": "Apply this local rewrite."},
                {"response_type": "needs_clarification", "proposed_response": "Ask for sentence-level target."},
            ],
        },
        "artifact_quality_checks": {
            "deduplication": {
                "merged_total": 1,
                "unmerged_duplicate_pairs_final": 1,
                "unmerged_same_anchor_overlap_final": 1,
            }
        },
    }
    metrics = compute_comment_quality_metrics(manifest)
    assert metrics["anchor_localization"]["avg_anchor_length_words"] > 0
    assert "paragraph_wide_local_anchor_rate" in metrics["anchor_localization"]
    assert metrics["rewrite_usefulness"]["rewrite_candidate_count"] == 1
    assert metrics["deduplication_quality"]["near_duplicate_pair_count"] >= 1
    assert "overlapping_comment_rate" in metrics["deduplication_quality"]
    assert metrics["claim_check_coverage"]["sentences_classified"] == 2
    assert metrics["claim_check_coverage"]["surfaced_comment_count"] >= 1
    assert metrics["claim_check_coverage"]["suppressed_comment_count"] == 2
    assert metrics["privacy_search_safety"]["safe_externalization_count"] == 1
    assert metrics["privacy_search_safety"]["blocked_externalization_count"] == 1
    assert metrics["existing_comment_responder_coverage"]["source_comments_read_count"] == 2
    assert metrics["style_pass_outcomes"]["style_comments_surfaced_count"] == 1
    assert metrics["overall_comment_mix"]["counts"]["style/clarity"] == 1


def test_compare_metric_dicts_returns_numeric_deltas():
    before = {"anchor_localization": {"avg_anchor_length_words": 18.0}}
    after = {"anchor_localization": {"avg_anchor_length_words": 12.0}}
    comparison = compare_metric_dicts(before, after, ["anchor_localization.avg_anchor_length_words"])
    row = comparison["anchor_localization.avg_anchor_length_words"]
    assert row["before"] == 18.0
    assert row["after"] == 12.0
    assert row["delta"] == -6.0
