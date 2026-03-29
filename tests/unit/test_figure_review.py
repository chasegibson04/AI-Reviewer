from __future__ import annotations

from types import SimpleNamespace

from ai_reviewer.config import FigureReviewConfig
from ai_reviewer.figures.figure_review import FigureArtifact, critique_figures


def test_critique_figures_flags_strong_claim_with_low_caption_confidence():
    cfg = FigureReviewConfig(enabled=True, style_checks_enabled=True, include_nearby_text=True)
    fig = FigureArtifact(
        figure_id="figure_001",
        page=1,
        image_path="figure_001.png",
        caption="",
        caption_confidence=0.2,
        page_text_excerpt="Figure 1 demonstrates that the model proves robust generalization across all tasks.",
        caption_source="none",
    )
    doc = SimpleNamespace(cleaned_text="Figure 1 demonstrates that the model proves robust generalization.")
    out = critique_figures([fig], doc, cfg)
    issues = out["critique"][0]["content_issues"]
    assert any("claim language appears strong" in i.lower() for i in issues)
    assert out["visual_mode"] == "text_only"

