import json
from pathlib import Path

from ai_reviewer.config import load_config
from ai_reviewer.ingest.loaders import parse_file
from ai_reviewer.logging_utils import configure_logging, create_run_dir
from ai_reviewer.models.base import ChatRequest, ChatResponse, Provider
from ai_reviewer.orchestrator.controller import OrchestratorController
from ai_reviewer.review.engine import run_review
from ai_reviewer.review.profiles import get_profile


def _review_payload() -> dict:
    return {
        "document_metadata": {"title": "x", "source": "x", "profile": "writing"},
        "summary": "This manuscript about phactor reactions has writing issues in long sentences and clarity.",
        "major_strengths": ["Clear objective"],
        "major_weaknesses": ["Long dense prose", "Passive voice", "Formatting artifacts"],
        "novelty_concerns": [],
        "methodological_concerns": [],
        "statistical_concerns": [],
        "writing_organization_concerns": ["Use active voice"],
        "figure_table_concerns": [],
        "citation_reference_concerns": [],
        "reproducibility_concerns": [],
        "suggested_experiments_analyses": [],
        "recommendation": {"decision": "revise", "rationale": "needs revision"},
        "confidence": 0.7,
        "detailed_reviewer_comments": ["Rewrite sentence-level phrasing"],
        "section_specific_comments": [{"section": "Introduction", "comment": "Tighten prose", "severity": "medium"}],
        "extracted_action_items": [{"action": "Rewrite key long sentences", "priority": "high", "owner": "author"}],
        "model_debug_metadata": {"provider": "ollama", "model": "mistral-small3.2:latest", "temperature": 0.1, "retries_used": 0, "parse_failures": 0},
    }


class _PipelineProvider(Provider):
    def __init__(self, bad_orchestrator: bool):
        self.bad_orchestrator = bad_orchestrator

    def list_models(self):
        return []

    def health(self):
        return True, "ok"

    def chat(self, request: ChatRequest):
        if request.metadata.get("orchestrator"):
            content = "not-json" if self.bad_orchestrator else json.dumps(
                {
                    "decision": "accept",
                    "quality_score": 90,
                    "specificity_score": 90,
                    "grounding_score": 90,
                    "actionability_score": 90,
                    "genericity_flag": False,
                    "missing_dimensions": [],
                    "retry_recommended": False,
                    "retry_reason": "",
                    "rationale": "ok",
                    "confidence": 0.9,
                }
            )
            return ChatResponse(content=content, model=request.model)
        return ChatResponse(content=json.dumps(_review_payload()), model=request.model)

    def embed(self, text: str, model: str, timeout_seconds: int = 90):
        raise NotImplementedError


def test_orchestrator_fail_open_pipeline(tmp_path: Path):
    src = tmp_path / "paper.md"
    src.write_text("# Intro\nphactor reaction arrays with chatgpt.", encoding="utf-8")
    doc = parse_file(src)
    cfg = load_config()
    run = create_run_dir(tmp_path / "runs", "review")
    bundle = run / "001_doc"
    bundle.mkdir(parents=True, exist_ok=True)
    logger = configure_logging(run, level="INFO")
    orch = OrchestratorController(
        provider=_PipelineProvider(bad_orchestrator=True),
        model="qwen3:8b",
        enabled=True,
        fail_open=True,
    )
    result = run_review(
        provider=_PipelineProvider(bad_orchestrator=True),
        doc=doc,
        profile=get_profile("writing"),
        model="mistral-small3.2:latest",
        repair_models=["qwen2.5:7b-instruct"],
        config=cfg,
        bundle_dir=bundle,
        embedding_model=None,
        strict_schema_override=True,
        logger=logger,
        orchestrator=orch,
    )
    assert result.review.summary
    assert (bundle / "orchestrator_decisions.json").exists()

