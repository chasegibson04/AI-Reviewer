import logging
from pathlib import Path

from ai_reviewer.config import load_config
from ai_reviewer.ingest.loaders import parse_file
from ai_reviewer.models.base import ChatRequest, ChatResponse, Provider
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
