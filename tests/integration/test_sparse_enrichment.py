import logging
from pathlib import Path

from ai_reviewer.config import load_config
from ai_reviewer.ingest.loaders import parse_file
from ai_reviewer.models.base import ChatRequest, ChatResponse, Provider
from ai_reviewer.review.engine import run_review
from ai_reviewer.review.profiles import get_profile


class SparseThenRichProvider(Provider):
    def __init__(self) -> None:
        self.calls = 0

    def list_models(self):
        return ["gemma3:27b", "mistral-small3.1:24b"]

    def health(self):
        return True, "ok"

    def chat(self, request: ChatRequest):
        self.calls += 1
        if self.calls == 1:
            # Valid schema but intentionally sparse to trigger enrichment.
            return ChatResponse(
                model=request.model,
                content=(
                    '{'
                    '"document_metadata":{"title":"Fixture"},'
                    '"summary":"too short",'
                    '"major_strengths":[],'
                    '"major_weaknesses":[],'
                    '"novelty_concerns":[],'
                    '"methodological_concerns":[],'
                    '"statistical_concerns":[],'
                    '"writing_organization_concerns":[],'
                    '"figure_table_concerns":[],'
                    '"citation_reference_concerns":[],'
                    '"reproducibility_concerns":[],'
                    '"suggested_experiments_analyses":[],'
                    '"recommendation":{"decision":"revise","rationale":"ok"},'
                    '"confidence":0.5,'
                    '"detailed_reviewer_comments":[],'
                    '"section_specific_comments":[],'
                    '"extracted_action_items":[],'
                    '"model_debug_metadata":{"provider":"ollama","model":"gemma3:27b","temperature":0.2,"parse_failures":0}'
                    '}'
                ),
            )
        return ChatResponse(
            model=request.model,
            content=(
                '{'
                '"document_metadata":{"title":"Fixture"},'
                '"summary":"This manuscript proposes a concrete AI-assisted reaction array workflow and reports section-specific outcomes for amide, Suzuki, and Buchwald-Hartwig coupling use cases.",'
                '"major_strengths":["Clear workflow framing","Useful practical setup"],'
                '"major_weaknesses":["Limited benchmark baselines","Narrow error analysis","Insufficient uncertainty handling"],'
                '"novelty_concerns":[],'
                '"methodological_concerns":["Need stronger controls"],'
                '"statistical_concerns":["Missing variability reporting"],'
                '"writing_organization_concerns":["Condense repetitive background"],'
                '"figure_table_concerns":[],'
                '"citation_reference_concerns":[],'
                '"reproducibility_concerns":["Need exact prompts and configs"],'
                '"suggested_experiments_analyses":["Add blinded baseline comparison"],'
                '"recommendation":{"decision":"revise","rationale":"promising but needs stronger evidence."},'
                '"confidence":0.68,'
                '"detailed_reviewer_comments":["Methods section needs clearer control description","Results should include uncertainty estimates","Discussion should narrow claims"],'
                '"section_specific_comments":[{"section":"Methods","comment":"Specify replicate counts.","severity":"high"}],'
                '"extracted_action_items":[{"action":"Add control baseline details","priority":"high","owner":"author"},{"action":"Report confidence intervals","priority":"high","owner":"author"},{"action":"Tighten claim language","priority":"medium","owner":"author"}],'
                '"model_debug_metadata":{"provider":"ollama","model":"mistral-small3.1:24b","temperature":0.1,"parse_failures":0}'
                '}'
            ),
        )

    def embed(self, text: str, model: str, timeout_seconds: int = 90):
        from ai_reviewer.models.base import EmbeddingResponse

        return EmbeddingResponse(embedding=[0.1] * 32, model=model)


def test_sparse_output_triggers_enrichment(tmp_path: Path):
    src = tmp_path / "paper.md"
    src.write_text("# Title\n\n## Results\nThe manuscript reports reaction optimization outcomes.", encoding="utf-8")
    doc = parse_file(src)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    provider = SparseThenRichProvider()

    result = run_review(
        provider=provider,
        doc=doc,
        profile=get_profile("editor"),
        model="gemma3:27b",
        repair_models=["mistral-small3.1:24b"],
        config=load_config(),
        bundle_dir=bundle,
        embedding_model=None,
        strict_schema_override=True,
        logger=logging.getLogger("test_sparse_enrichment"),
    )

    assert provider.calls >= 2
    assert "AI-assisted reaction array workflow" in result.review.summary
    assert len(result.review.extracted_action_items) >= 3

