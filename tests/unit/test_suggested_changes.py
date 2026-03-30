from __future__ import annotations

import json
from pathlib import Path

from docx import Document

from ai_reviewer.models.base import ChatRequest
from ai_reviewer.review.manuscript_annotation import (
    _balance_comment_entries,
    _comment_entry_quality_ok,
    _dedupe_comment_entries,
    _generate_suggested_changes,
    _localize_comment_entries,
    _revise_comment_entries,
    _section_lookup_for_docx,
)


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


def test_suggested_changes_rejects_awkward_rewrite_without_safe_fallback(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    _write_docx(
        base_docx,
        [
            "## Methods",
            "Reactions were dosed with catalyst and base before the plate was sealed and analysed under the stated conditions.",
        ],
    )
    comments = [
        {
            "comment_id": "c1",
            "paragraph_index": 1,
            "issue_type": "section_issue",
            "severity": "medium",
            "critique": "Name the exact criterion controlling the step.",
            "suggested_revision": "Clarify the condition boundary.",
            "anchor_text": "Reactions were dosed with catalyst and base before the plate was sealed and analysed under the stated conditions.",
        }
    ]
    responses = [
        json.dumps(
            {
                "revised_text": "This sentence should be clearer about the criterion controlling the step.",
                "rationale": "Editorial note.",
                "confidence": 0.2,
            }
        ),
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
    assert changes[0]["skip_reason"] == "editorial_meta_text"


def test_suggested_changes_rejects_low_faithfulness_without_fallback(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    _write_docx(
        base_docx,
        [
            "## Methods",
            "The reaction mixture was stirred at room temperature for 18 h before quenching with water.",
        ],
    )
    comments = [
        {
            "comment_id": "c1",
            "paragraph_index": 1,
            "issue_type": "section_issue",
            "severity": "medium",
            "critique": "State the exact condition that defines the end of the step.",
            "suggested_revision": "Clarify the stopping condition.",
            "anchor_text": "The reaction mixture was stirred at room temperature for 18 h before quenching with water.",
        }
    ]
    responses = [
        json.dumps(
            {
                "revised_text": "The reaction mixture was stirred overnight and then processed.",
                "rationale": "Shorter sentence.",
                "confidence": 0.5,
            }
        ),
        json.dumps({"ok": False, "fluency_score": 0.86, "faithfulness_score": 0.41, "alignment_score": 0.72, "issues": ["meaning drift from specific conditions"]}),
        json.dumps(
            {
                "revised_text": "The reaction mixture was stirred overnight and then processed.",
                "rationale": "Second attempt.",
                "confidence": 0.5,
            }
        ),
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
    assert changes[0]["skip_reason"] in {"low_faithfulness", "verifier_issue_flag", "numeric_loss"}


def test_suggested_changes_rejects_unsupported_addition_without_safe_fallback(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    _write_docx(
        base_docx,
        [
            "## Methods",
            "The samples were combined in solvent and heated under the reported conditions before analysis.",
        ],
    )
    comments = [
        {
            "comment_id": "c1",
            "paragraph_index": 1,
            "issue_type": "section_issue",
            "severity": "medium",
            "critique": "Clarify the exact condition or scope limit controlling this step.",
            "suggested_revision": "State the limiting condition.",
            "anchor_text": "The samples were combined in solvent and heated under the reported conditions before analysis.",
        }
    ]
    responses = [
        json.dumps(
            {
                "revised_text": "The samples were combined in solvent and heated under the reported conditions before analysis, and we conducted comparative studies that showed statistically significant gains.",
                "rationale": "Adds interpretive context.",
                "confidence": 0.8,
            }
        ),
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
    assert changes[0]["skip_reason"] == "unsupported_addition"


def test_suggested_changes_splits_multiple_local_targets_in_one_paragraph(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    original = (
        "This workflow is experimentally demonstrated across the tested set. "
        "The reaction mixture was stirred at room temperature for 18 h before quenching with water."
    )
    _write_docx(base_docx, [original])
    comments = [
        {
            "comment_id": "c1",
            "paragraph_index": 0,
            "issue_type": "evidence/overclaim concern",
            "severity": "high",
            "critique": "Narrow the claim to the tested set.",
            "suggested_revision": "Qualify the claim.",
            "anchor_text": "This workflow is experimentally demonstrated across the tested set.",
        },
        {
            "comment_id": "c2",
            "paragraph_index": 0,
            "issue_type": "clarity",
            "severity": "medium",
            "critique": "The procedural readout should be easier to follow.",
            "suggested_revision": "Split setup from readout.",
            "anchor_text": "The reaction mixture was stirred at room temperature for 18 h before quenching with water.",
        },
    ]
    responses = [
        json.dumps({"revised_text": "This workflow is experimentally demonstrated in the tested cases.", "rationale": "Narrows scope.", "confidence": 0.8}),
        json.dumps({"ok": True, "fluency_score": 0.9, "faithfulness_score": 0.88, "alignment_score": 0.86, "issues": []}),
        json.dumps({"revised_text": "The reaction mixture was stirred at room temperature for 18 h. The mixture was then quenched with water.", "rationale": "Improves readability.", "confidence": 0.78}),
        json.dumps({"ok": True, "fluency_score": 0.9, "faithfulness_score": 0.9, "alignment_score": 0.84, "issues": []}),
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
    assert len(changes) == 2
    assert len(applied) == 2
    assert all(change["status"] == "applied" for change in changes)


def test_comment_entry_quality_gate_rejects_low_value_suggestion():
    entry = {
        "critique": "Provide detailed experimental procedures, including specific parameters and settings.",
        "suggested_revision": "Proposed edit: phactor.",
    }
    paragraph = "phactor. An interfacing script written in python is provided online."
    assert _comment_entry_quality_ok(entry, paragraph) is False


def test_section_lookup_keeps_methods_and_introduction_despite_pdf_noise(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    _write_docx(
        base_docx,
        [
            "s44160-023-00351-1",
            "https://doi.org/10.1038/s44160-023-00351-1",
            "## Nature Synthesis",
            "Miniaturization of popular reactions from the medicinal chemists toolbox",
            "Chemical space exploration in drug discovery generally requires access to many molecules with diverse physicochemical properties.",
            "Fig. 1 | Popularity of common reactions in the synthesis of pharmaceuticals.",
            "Given our earlier success in reaction miniaturization, we initiated our studies by targeting the Suzuki coupling.",
            "## Methods",
            "## High-throughput experimentation",
            "For nanoscale HTE all reactions were prepared at the 1 ul scale in a 1,536-well microplate using a liquid-handling robot.",
            "## General procedure for Suzuki coupling",
            "In a nitrogen-filled glovebox, pyridin-3-ylboronic acid was combined with catalyst in anhydrous DMSO and stirred overnight.",
        ],
    )
    lookup = _section_lookup_for_docx(base_docx)
    assert lookup[4] == "introduction"
    assert lookup[6] in {"results", "discussion"}
    assert lookup[9] == "methods"
    assert lookup[11] == "methods"


def test_section_lookup_keeps_front_matter_from_poisoning_intro(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    _write_docx(
        base_docx,
        [
            "paper-slug-123456",
            "## Title of the paper",
            "Babak Mahjour, Jillian Hoffstadt, Tim Cernak",
            "Cite This: Org. Process Res. Dev. 2023, 27, 1510-1516",
            "## Introduction",
            (
                "Chemical synthesis is a primary bottleneck in drug development. "
                "High-throughput experimentation is a widely practiced method for discovery and optimization."
            ),
            "## Experimental",
            "For nanoscale HTE all reactions were prepared at the 1 ul scale in a 1,536-well microplate using a robot.",
        ],
    )
    lookup = _section_lookup_for_docx(base_docx)
    assert lookup[0] == "front_matter"
    assert lookup[1] == "front_matter"
    assert lookup[2] == "front_matter"
    assert lookup[3] == "front_matter"
    assert lookup[5] == "introduction"
    assert lookup[7] == "methods"


def test_section_lookup_recovers_miniaturization_intro_transition(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    _write_docx(
        base_docx,
        [
            "s44160-023-00351-1",
            "https://doi.org/10.1038/s44160-023-00351-1",
            "## Nature Synthesis",
            "## Miniaturization of popular reactions from the medicinal chemists toolbox",
            (
                "Chemical space exploration in drug discovery generally requires access to many molecules with diverse "
                "physicochemical properties. The recent ability to computationally predict properties has shifted the bottleneck."
            ),
            (
                "Inspired by Moore's Law of transistor miniaturization, label-free reaction miniaturization has emerged as a "
                "technology with considerable promise to enable studies of the seemingly infinite chemical and reaction condition space."
            ),
            (
                "Buchwald-Hartwig coupling, heteroatom alkylation by reductive amination and N-Boc-deprotection have emerged as "
                "reactions of choice for pharmaceutical chemical space exploration."
            ),
            (
                "Given our earlier success in the miniaturization of Pd-catalysed C-N coupling, we initiated our studies by "
                "targeting the Suzuki coupling."
            ),
            "## Methods",
            "For nanoscale HTE all reactions were prepared at the 1 ul scale in a 1,536-well microplate using a robot.",
        ],
    )
    lookup = _section_lookup_for_docx(base_docx)
    assert lookup[4] == "introduction"
    assert lookup[5] == "introduction"
    assert lookup[6] == "introduction"
    assert lookup[7] == "results"
    assert lookup[9] == "methods"


def test_section_lookup_preserves_long_body_paragraph_with_merged_page_noise(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    _write_docx(
        base_docx,
        [
            "## Introduction",
            (
                "The robotic liquid handlers typically used in low-volume reagent dosing rely on involatile, homogeneous reagent "
                "stock solutions with low viscosity. Thus, high-throughput reaction methodology typically favours high-boiling "
                "solvents that fully dissolve all reaction components."
            ),
            "Nature Synthesis | Volume 2 | November 2023 | 1082-1091",
            "## Methods",
            (
                "In a nitrogen-filled glovebox, pyridin-3-ylboronic acid was combined with catalyst in anhydrous DMSO and stirred overnight."
            ),
        ],
    )
    lookup = _section_lookup_for_docx(base_docx)
    assert lookup[1] == "introduction"
    assert lookup[2] == "header_footer"
    assert lookup[4] == "methods"


def test_balance_comment_entries_spreads_across_sections(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    _write_docx(
        base_docx,
        [
            "## Introduction",
            "Chemical synthesis is a primary bottleneck in drug development and motivates the workflow.",
            "## Experimental",
            "For nanoscale HTE all reactions were prepared at the 1 ul scale in a 1,536-well microplate using a robot.",
            "## Results",
            "All 1,440 reactions were performed in ultraHTE format and relative conversion was measured by UPLC.",
            "## Discussion",
            "This work highlights the importance of scope boundaries and interpretation discipline.",
        ],
    )
    entries = [
        {"comment_id": "c1", "paragraph_index": 5, "severity": "high", "priority_score": 5},
        {"comment_id": "c2", "paragraph_index": 5, "severity": "medium", "priority_score": 4},
        {"comment_id": "c3", "paragraph_index": 5, "severity": "medium", "priority_score": 3},
        {"comment_id": "c4", "paragraph_index": 3, "severity": "high", "priority_score": 5},
        {"comment_id": "c5", "paragraph_index": 1, "severity": "high", "priority_score": 5},
        {"comment_id": "c6", "paragraph_index": 7, "severity": "medium", "priority_score": 4},
    ]
    balanced = _balance_comment_entries(entries, base_docx, max_comments=4)
    chosen = {entry["comment_id"] for entry in balanced}
    assert "c5" in chosen
    assert "c4" in chosen
    assert "c1" in chosen
    assert "c6" in chosen


def test_comment_quality_gate_rejects_generic_section_filler():
    entry = {
        "critique": "The discussion section could benefit from more detail.",
        "suggested_revision": "Suggested wording direction: improve the section.",
        "anchor_text": "This work highlights the importance of scope boundaries.",
    }
    paragraph = "This work highlights the importance of scope boundaries and interpretation discipline."
    assert _comment_entry_quality_ok(entry, paragraph) is False


def test_revise_comment_entries_makes_local_intro_comment(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    sentence = (
        "Recently, it has become increasingly possible to predict the outcome of chemical reactions with machine learning, "
        "although there are limited reaction data available to train such statistical models."
    )
    _write_docx(base_docx, [sentence])
    entries = [
        {
            "comment_id": "c1",
            "paragraph_index": 0,
            "issue_type": "clarity",
            "severity": "medium",
            "anchor_text": sentence,
            "span_sentence": sentence,
            "critique": "Improve clarity.",
            "suggested_revision": "Proposed edit:",
        }
    ]
    revised = _revise_comment_entries(entries, base_docx)
    assert "background and the paper-specific turn" in revised[0]["critique"]
    assert revised[0]["suggested_revision"].startswith("Suggested wording direction:")
    assert "introduction section" in revised[0]["rationale"]


def test_revise_comment_entries_varies_by_section_style(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    intro = "Chemical synthesis is a primary bottleneck in drug development and motivates the workflow."
    methods = "In a nitrogen-filled glovebox, the reaction plate was sealed, centrifuged, and quenched the next morning."
    _write_docx(base_docx, ["## Introduction", intro, "## Methods", methods])
    entries = [
        {
            "comment_id": "c1",
            "paragraph_index": 1,
            "issue_type": "clarity",
            "severity": "medium",
            "anchor_text": intro,
            "span_sentence": intro,
            "critique": "Improve clarity.",
            "suggested_revision": "Proposed edit:",
        },
        {
            "comment_id": "c2",
            "paragraph_index": 3,
            "issue_type": "methods concern",
            "severity": "medium",
            "anchor_text": methods,
            "span_sentence": methods,
            "critique": "Needs more detail.",
            "suggested_revision": "Proposed edit:",
        },
    ]
    revised = _revise_comment_entries(entries, base_docx)
    assert "background and the paper-specific turn" in revised[0]["critique"]
    assert "procedural sentence bundles setup details" in revised[1]["critique"]


def test_dedupe_comment_entries_suppresses_duplicate_anchor_issue():
    entries = [
        {
            "comment_id": "c1",
            "paragraph_index": 7,
            "issue_type": "clarity",
            "severity": "medium",
            "anchor_text": "This sentence is carrying both background and the paper-specific turn in one long sentence.",
            "span_sentence": "This sentence is carrying both background and the paper-specific turn in one long sentence.",
        },
        {
            "comment_id": "c2",
            "paragraph_index": 7,
            "issue_type": "clarity",
            "severity": "low",
            "anchor_text": "This sentence is carrying both background and the paper-specific turn in one long sentence.",
            "span_sentence": "This sentence is carrying both background and the paper-specific turn in one long sentence.",
        },
        {
            "comment_id": "c3",
            "paragraph_index": 7,
            "issue_type": "evidence/overclaim concern",
            "severity": "high",
            "anchor_text": "This sentence is carrying both background and the paper-specific turn in one long sentence.",
            "span_sentence": "This sentence is carrying both background and the paper-specific turn in one long sentence.",
        },
    ]
    deduped = _dedupe_comment_entries(entries)
    kept = {item["comment_id"] for item in deduped}
    assert "c1" in kept
    assert "c2" not in kept
    assert "c3" in kept


def test_localize_comment_entries_rewrites_generic_methods_comment(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    _write_docx(
        base_docx,
        [
            "## Methods",
            "For nanoscale HTE all reactions were prepared at the 1 ul scale in a 1,536-well microplate using a liquid-handling robot inside a glovebox, then sealed, centrifuged, and quenched the next morning.",
        ],
    )
    entries = [
        {
            "comment_id": "c1",
            "paragraph_index": 1,
            "issue_type": "section_issue",
            "severity": "medium",
            "critique": "The Methods section could benefit from more detail.",
            "suggested_revision": "Proposed edit: revise the sentence that carries this claim so it states one concrete condition and one explicit limitation.",
        }
    ]
    localized = _localize_comment_entries(entries, base_docx)
    assert "This procedural sentence" in localized[0]["critique"]
    assert "glovebox" in localized[0]["anchor_text"].lower()
    assert localized[0]["suggested_revision"].startswith("Proposed edit:")


def test_suggested_changes_nonlocal_methods_expansion_abstains(tmp_path: Path):
    base_docx = tmp_path / "base.docx"
    original = (
        "For nanoscale HTE all reactions were prepared at the 1 ul scale in a 1,536-well microplate using the liquid-handling robot inside a glovebox. "
        "The source plate contained all required substrates, reagents, catalysts, and building blocks, and the reaction plate was sealed, centrifuged, and left at ambient temperature overnight before quenching."
    )
    _write_docx(base_docx, [original])
    comments = [
        {
            "comment_id": "c1",
            "paragraph_index": 0,
            "issue_type": "section_issue",
            "severity": "medium",
            "critique": "The methods section needs significant expansion and should include more details on optimization, controls, and validation steps.",
            "suggested_revision": "Proposed edit: revise the sentence that carries this claim so it states one concrete condition and one explicit limitation.",
        }
    ]
    provider = DummyProvider([])
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
    assert changes[0]["skip_reason"] == "no_safe_local_rewrite"
