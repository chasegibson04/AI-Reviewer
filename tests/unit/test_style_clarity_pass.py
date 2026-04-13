from __future__ import annotations

import json

from ai_reviewer.models.base import ChatRequest
from ai_reviewer.review.style_clarity_pass import (
    STYLE_KIND_OVERLOADED,
    classify_style_issue,
    deterministic_style_rewrite,
    run_style_clarity_pass,
    style_results_to_comment_entries,
    style_rewrite_usefulness_check,
)


class _MockProvider:
    def __init__(self, responses: list[str], models: list[str] | None = None):
        self._responses = list(responses)
        self._models = models or ["gemma4:31b"]

    def list_models(self) -> list[str]:
        return list(self._models)

    def chat(self, request: ChatRequest):
        if not self._responses:
            raise RuntimeError("No queued response")

        class _Resp:
            def __init__(self, content: str):
                self.content = content

        return _Resp(self._responses.pop(0))


class _AlwaysFailProvider:
    def __init__(self, models: list[str] | None = None):
        self._models = models or ["gemma4:31b"]
        self.calls = 0

    def list_models(self) -> list[str]:
        return list(self._models)

    def chat(self, request: ChatRequest):
        self.calls += 1
        raise RuntimeError("empty_response")


def test_style_rewrite_usefulness_rejects_noop():
    sentence = "This sentence is clear and direct."
    useful, reason, _ = style_rewrite_usefulness_check(sentence, sentence, "readability")
    assert useful is False
    assert reason in {"no_change_normalized", "trivial_change"}


def test_overloaded_sentence_is_split_locally():
    sentence = (
        "The platform combines stock-solution preparation, low-volume dosing, and inline analysis, "
        "while preserving compatibility with standard robotic labware for medicinal chemistry screening."
    )
    issue = classify_style_issue(sentence)
    assert issue is not None
    assert issue.kind == STYLE_KIND_OVERLOADED
    rewritten = deterministic_style_rewrite(sentence, issue.kind)
    assert len([s for s in rewritten.split(".") if s.strip()]) == 2
    useful, reason, _ = style_rewrite_usefulness_check(sentence, rewritten, issue.kind)
    assert useful is True, reason


def test_style_pass_drops_weak_llm_rewrite_before_candidate_emission():
    paragraph = (
        "The method has the ability to improve throughput in order to accelerate screening in medicinal chemistry."
    )
    provider = _MockProvider(
        responses=[
            json.dumps(
                {
                    "critique": "Tighten wording.",
                    "action": "remove filler",
                    "rewrite": "The method has the ability to improve throughput in order to accelerate screening in medicinal chemistry.",
                }
            )
        ]
    )
    manifest = run_style_clarity_pass(
        paragraphs=[paragraph],
        section_by_idx={0: "introduction"},
        provider=provider,
        model="fallback-model",
        timeout_seconds=20,
        max_candidates=6,
    )
    assert manifest["summary"]["candidate_count"] == 0
    assert manifest["summary"]["rewrites_suppressed"] == 0
    assert manifest["model"]["selected_model"] == "gemma4:31b"


def test_style_results_to_comment_entries_emit_compact_actionable_format():
    manifest = {
        "items": [
            {
                "sentence_id": "p0001.s002",
                "paragraph_index": 1,
                "sentence_text": "This sentence is overloaded and hard to read because it has too many clauses, and it keeps adding conditions.",
                "issue_kind": "overloaded_sentence",
                "rewrite_useful": True,
                "rewrite": "This sentence is overloaded and hard to read. It adds too many conditions in one place.",
                "priority": 0,
                "metrics": {"improvement_signals": 2},
            }
        ]
    }
    entries = style_results_to_comment_entries(manifest, max_comments=4)
    assert len(entries) == 1
    assert entries[0]["from_style_pass"] is True
    assert entries[0]["critique"].startswith("Split this into two sentences")
    assert entries[0]["suggested_revision"].startswith("Proposed edit:")


def test_style_pass_fail_fast_disables_llm_after_first_error():
    paragraphs = [
        "The method has the ability to improve throughput in order to accelerate screening in medicinal chemistry.",
        "This workflow is experimentally demonstrated, with modest to excellent yields of products obtained in each instance on the first attempt.",
    ]
    provider = _AlwaysFailProvider()
    manifest = run_style_clarity_pass(
        paragraphs=paragraphs,
        section_by_idx={0: "introduction", 1: "discussion"},
        provider=provider,
        model="fallback-model",
        timeout_seconds=20,
        max_candidates=10,
    )
    assert provider.calls == 1
    assert manifest["model"]["fail_fast_fallback_triggered"] is True


def test_overloaded_split_does_not_emit_fragment_with_leading_conjunction():
    sentence = (
        "With reaction miniaturization, less starting material is needed to produce more reaction data, "
        "and the acquisition of each experimental data point requires less laboratory space."
    )
    rewritten = deterministic_style_rewrite(sentence, STYLE_KIND_OVERLOADED)
    parts = [p.strip() for p in rewritten.split(".") if p.strip()]
    if len(parts) >= 2:
        assert not parts[1].lower().startswith(("and ", "or ", "but "))


def test_overloaded_split_rejects_punctuation_only_gain():
    sentence = (
        "High-throughput experimentation is a widely practiced method.[1] "
        "Chemists typically design reaction arrays based on literature conditions."
    )
    rewrite = deterministic_style_rewrite(sentence, STYLE_KIND_OVERLOADED)
    useful, reason, _ = style_rewrite_usefulness_check(sentence, rewrite, STYLE_KIND_OVERLOADED)
    assert useful is False
    assert reason in {"no_change_normalized", "punctuation_only_split", "insufficient_split_gain"}


def test_overloaded_split_handles_leading_purpose_clause():
    sentence = (
        "To test the effectiveness of reaction arrays designed by ChatGPT, a workflow to automatically generate reagent proposals "
        "and execute reaction arrays for popular reactions was developed."
    )
    rewrite = deterministic_style_rewrite(sentence, STYLE_KIND_OVERLOADED)
    assert "This workflow was designed to" in rewrite
    useful, reason, _ = style_rewrite_usefulness_check(sentence, rewrite, STYLE_KIND_OVERLOADED)
    assert useful is True, reason
