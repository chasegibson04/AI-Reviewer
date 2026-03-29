import logging
from pathlib import Path

from ai_reviewer.config import load_config
from ai_reviewer.ingest.loaders import parse_file
from ai_reviewer.models.base import ChatRequest, ChatResponse, Provider
import ai_reviewer.review.engine as engine
from ai_reviewer.review.engine import run_review
from ai_reviewer.review.profiles import get_profile


class StubProvider(Provider):
    def list_models(self):
        return ["gemma3:27b", "mxbai-embed-large:latest", "mistral-small3.1:24b"]

    def health(self):
        return True, "ok"

    def chat(self, request: ChatRequest):
        return ChatResponse(
            model=request.model,
            content=(
                '{'
                '"document_metadata":{"title":"Fixture"},'
                '"summary":"Test summary",'
                '"major_strengths":["x"],'
                '"major_weaknesses":["y"],'
                '"novelty_concerns":[],'
                '"methodological_concerns":[],'
                '"statistical_concerns":[],'
                '"writing_organization_concerns":[],'
                '"figure_table_concerns":[],'
                '"citation_reference_concerns":[],'
                '"reproducibility_concerns":[],'
                '"suggested_experiments_analyses":[],'
                '"recommendation":{"decision":"revise","rationale":"ok"},'
                '"confidence":0.7,'
                '"detailed_reviewer_comments":["fine"],'
                '"section_specific_comments":[],'
                '"extracted_action_items":[],'
                '"model_debug_metadata":{"provider":"ollama","model":"gemma3:27b","temperature":0.2,"parse_failures":0}'
                '}'
            ),
            total_duration=1.2,
        )

    def embed(self, text: str, model: str, timeout_seconds: int = 90):
        from ai_reviewer.models.base import EmbeddingResponse

        return EmbeddingResponse(embedding=[0.2] * 32, model=model)


def test_ingest_review_pipeline(tmp_path: Path):
    p = tmp_path / "paper.md"
    p.write_text("# Title\n\n## Methods\nWe evaluate carefully.", encoding="utf-8")
    doc = parse_file(p)

    cfg = load_config()
    bundle = tmp_path / "bundle"
    bundle.mkdir()

    result = run_review(
        provider=StubProvider(),
        doc=doc,
        profile=get_profile("balanced"),
        model="gemma3:27b",
        repair_models=["mistral-small3.1:24b"],
        config=cfg,
        bundle_dir=bundle,
        embedding_model="mxbai-embed-large:latest",
        strict_schema_override=True,
        logger=logging.getLogger("test"),
    )
    assert result.review.summary == "Test summary"
    assert (bundle / "reports" / "review.md").exists()
    assert (bundle / "artifacts" / "review.validated.json").exists()
    assert (bundle / "specialist_review_summary.json").exists()
    assert (bundle / "specialist_review_summary.md").exists()


def test_figure_review_concerns_are_aggregated(tmp_path: Path, monkeypatch):
    p = tmp_path / "paper.md"
    p.write_text("# Title\n\nFigure 1 demonstrates an effect.", encoding="utf-8")
    doc = parse_file(p)

    cfg = load_config()
    cfg.figure_review.enabled = True
    bundle = tmp_path / "bundle_fig"
    bundle.mkdir()

    def fake_figure_review(_doc, _bundle, _cfg):
        return {
            "critique": {
                "figure_count": 3,
                "critique": [
                    {"figure_id": "figure_001", "content_issues": ["Caption not detected via PDF text extraction; figure interpretation may be limited."]},
                    {"figure_id": "figure_002", "content_issues": ["Caption not detected via PDF text extraction; figure interpretation may be limited."]},
                    {"figure_id": "figure_003", "content_issues": ["Caption is very short; may not provide enough context for interpretation."]},
                ],
            }
        }

    monkeypatch.setattr(engine, "run_figure_review", fake_figure_review)
    result = run_review(
        provider=StubProvider(),
        doc=doc,
        profile=get_profile("balanced"),
        model="gemma3:27b",
        repair_models=["mistral-small3.1:24b"],
        config=cfg,
        bundle_dir=bundle,
        embedding_model="mxbai-embed-large:latest",
        strict_schema_override=True,
        logger=logging.getLogger("test"),
    )
    concerns = result.review.figure_table_concerns
    assert any("lacked reliable caption text" in c.lower() for c in concerns)
    assert any("figure_003" in c.lower() for c in concerns)
