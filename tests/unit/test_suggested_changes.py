from __future__ import annotations

import json
from pathlib import Path

from docx import Document

from ai_reviewer.models.base import ChatRequest
from ai_reviewer.review.manuscript_annotation import _comment_entry_quality_ok, _generate_suggested_changes


class DummyProvider:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)

    def chat(self, request: ChatRequest):
        if not self._responses:
            raise RuntimeError(f"No response queued for {request.metadata}")
        class _Resp:
            def __init__(self, content: str):
                self.content = content
        return _Resp(self._responses.pop(0))


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    doc.save(str(path))


def test_suggested_changes_global_issue_skips(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    _write_docx(base_docx, ["Intro text with enough length to be eligible."])
    comments = [
        {
            "comment_id": "c1",
            "paragraph_index": 0,
            "issue_type": "structure/organization",
            "severity": "high",
            "critique": "Global framing issue.",
            "suggested_revision": "Clarify framing.",
        }
    ]
    changes, applied = _generate_suggested_changes(
        base_docx=base_docx,
        comments=comments,
        source_mode={"mode": "original_docx"},
        project_id="p1",
        run_id="r1",
        provider=None,
        model=None,
        rewrite_model=None,
        timeout_seconds=30,
    )
    assert applied == []
    assert changes[0]["skip_reason"] == "global_issue_not_localized"


def test_suggested_changes_rewrite_revision_path(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    original = "The experiment was performed under standard conditions and yielded moderate conversion."
    _write_docx(base_docx, [original])
    comments = [
        {
            "comment_id": "c1",
            "paragraph_index": 0,
            "issue_type": "grammar/style",
            "severity": "medium",
            "critique": "Passive voice obscures the actor.",
            "suggested_revision": "Use active voice.",
        }
    ]
    responses = [
        json.dumps({"revised_text": "The experiment was performed under standard conditions, but the wording is clumsy.", "rationale": "Attempt 1", "confidence": 0.3}),
        json.dumps({"ok": False, "fluency_score": 0.2, "faithfulness_score": 0.9, "alignment_score": 0.4, "issues": ["fluency too low"]}),
        json.dumps({"revised_text": "We performed the experiment under standard conditions and observed moderate conversion.", "rationale": "Active voice and clarity.", "confidence": 0.7}),
        json.dumps({"ok": True, "fluency_score": 0.9, "faithfulness_score": 0.9, "alignment_score": 0.8, "issues": []}),
    ]
    provider = DummyProvider(responses)
    changes, applied = _generate_suggested_changes(
        base_docx=base_docx,
        comments=comments,
        source_mode={"mode": "original_docx"},
        project_id="p1",
        run_id="r1",
        provider=provider,
        model="test-chat",
        rewrite_model="test-chat",
        timeout_seconds=30,
    )
    assert applied
    assert changes[0]["status"] == "applied"
    assert "performed the experiment" in (changes[0]["revised_text"] or "")


def test_suggested_changes_rejects_numeric_loss(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    original = "Samples were incubated at 37 C for 24 h in 1.5 ml tubes."
    _write_docx(base_docx, [original])
    comments = [
        {
            "comment_id": "c1",
            "paragraph_index": 0,
            "issue_type": "grammar/style",
            "severity": "medium",
            "critique": "Tighten wording.",
            "suggested_revision": "Rewrite for clarity.",
        }
    ]
    responses = [
        json.dumps({"revised_text": "Samples were incubated in sealed tubes under controlled conditions.", "rationale": "Shorter.", "confidence": 0.2}),
    ]
    provider = DummyProvider(responses)
    changes, applied = _generate_suggested_changes(
        base_docx=base_docx,
        comments=comments,
        source_mode={"mode": "original_docx"},
        project_id="p1",
        run_id="r1",
        provider=provider,
        model="test-chat",
        rewrite_model="test-chat",
        timeout_seconds=30,
    )
    assert applied == []
    assert changes[0]["skip_reason"] == "numeric_loss"


def test_suggested_changes_rejects_markdown_heading(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    original = "Chemical synthesis is a primary bottleneck in drug development."
    _write_docx(base_docx, [original])
    comments = [
        {
            "comment_id": "c1",
            "paragraph_index": 0,
            "issue_type": "clarity",
            "severity": "low",
            "critique": "Tighten wording.",
            "suggested_revision": "Rewrite for clarity.",
        }
    ]
    responses = [
        json.dumps({"revised_text": "## [INTRODUCTION] Chemical synthesis is a primary bottleneck in drug development.", "rationale": "Heading added.", "confidence": 0.2}),
    ]
    provider = DummyProvider(responses)
    changes, applied = _generate_suggested_changes(
        base_docx=base_docx,
        comments=comments,
        source_mode={"mode": "original_docx"},
        project_id="p1",
        run_id="r1",
        provider=provider,
        model="test-chat",
        rewrite_model="test-chat",
        timeout_seconds=30,
    )
    assert applied == []
    assert changes[0]["skip_reason"] == "markdown_heading"


def test_suggested_changes_structure_issue_can_apply_when_localized(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    original = "This section outlines the workflow and then jumps abruptly to results without a transition."
    _write_docx(base_docx, [original])
    comments = [
        {
            "comment_id": "c1",
            "paragraph_index": 0,
            "issue_type": "structure/organization",
            "severity": "medium",
            "critique": "The sentence transition is abrupt and should bridge workflow setup to results.",
            "suggested_revision": "Add a transition clause before presenting results.",
            "anchor_text": "jumps abruptly to results",
        }
    ]
    responses = [
        json.dumps(
            {
                "revised_text": "This section outlines the workflow and then introduces the results with a clear transition to maintain narrative continuity.",
                "rationale": "Adds transition language and improves flow.",
                "confidence": 0.8,
            }
        ),
        json.dumps({"ok": True, "fluency_score": 0.95, "faithfulness_score": 0.9, "alignment_score": 0.85, "issues": []}),
    ]
    provider = DummyProvider(responses)
    changes, applied = _generate_suggested_changes(
        base_docx=base_docx,
        comments=comments,
        source_mode={"mode": "original_docx"},
        project_id="p1",
        run_id="r1",
        provider=provider,
        model="test-chat",
        rewrite_model="test-chat",
        timeout_seconds=30,
    )
    assert changes[0]["status"] == "applied"
    assert applied


def test_suggested_changes_unsupported_addition_falls_back_to_safe_local_rewrite(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    original = "The workflow integrates model output into the execution software for reaction setup, and then passes formatted instructions to the automation layer."
    _write_docx(base_docx, [original])
    comments = [
        {
            "comment_id": "c1",
            "paragraph_index": 0,
            "issue_type": "clarity",
            "severity": "medium",
            "critique": "Clarify the workflow sentence and keep claims grounded.",
            "suggested_revision": "Improve precision and avoid broad claims.",
        }
    ]
    responses = [
        json.dumps(
            {
                "revised_text": (
                    "The workflow integrates model output into the execution software for reaction setup, and then passes formatted instructions to the automation layer. "
                    "We conducted comparative studies and observed statistically significant gains."
                ),
                "rationale": "Adds contextual comparison.",
                "confidence": 0.8,
            }
        )
    ]
    provider = DummyProvider(responses)
    changes, applied = _generate_suggested_changes(
        base_docx=base_docx,
        comments=comments,
        source_mode={"mode": "original_docx"},
        project_id="p1",
        run_id="r1",
        provider=provider,
        model="test-chat",
        rewrite_model="test-chat",
        timeout_seconds=30,
    )
    assert applied
    assert changes[0]["status"] == "applied"
    assert changes[0]["verification"]["reason"] == "unsupported_addition"


def test_comment_entry_quality_gate_rejects_low_value_suggestion():
    entry = {
        "critique": "Provide detailed experimental procedures, including specific parameters and settings.",
        "suggested_revision": "Proposed edit: phactor.",
    }
    paragraph = "phactor. An interfacing script written in python is provided online."
    assert _comment_entry_quality_ok(entry, paragraph) is False
