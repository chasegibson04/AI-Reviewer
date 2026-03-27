import logging

from ai_reviewer.models.base import ChatRequest, ChatResponse, Provider
from ai_reviewer.review.repair import parse_and_repair


class DummyProvider(Provider):
    def list_models(self):
        return ["qwen2.5:7b-instruct"]

    def health(self):
        return True, "ok"

    def chat(self, request: ChatRequest):
        return ChatResponse(model=request.model, content='{"summary": "ok", "confidence": 0.7}')

    def embed(self, text: str, model: str, timeout_seconds: int = 90):
        raise NotImplementedError


def test_repair_fallback_produces_valid_schema():
    malformed = '{"summary": "x", "confidence": 0.7,}'
    out = parse_and_repair(
        malformed,
        provider=DummyProvider(),
        repair_models=["qwen2.5:7b-instruct"],
        timeout_seconds=5,
        logger=logging.getLogger("test"),
    )
    assert out.parsed is not None
    assert out.parsed.summary


def test_repair_heuristic_extraction_from_prose():
    prose = """
**Overall Summary**
This manuscript presents a practical AI-assisted workflow for reaction array design using ChatGPT and phactor.

**Key Observations & Strengths**
- Clear workflow framing.
- Useful practical integration with automation software.

**Potential Areas for Improvement/Questions**
- Add stronger baseline comparisons.
- Report uncertainty and replicate variability.
"""
    out = parse_and_repair(
        prose,
        provider=DummyProvider(),
        repair_models=["qwen2.5:7b-instruct"],
        timeout_seconds=5,
        logger=logging.getLogger("test"),
        allow_self_repair=False,
    )
    assert out.parsed is not None
    assert out.repair_stage == "heuristic_extraction"
    assert len(out.parsed.major_strengths) >= 1
    assert len(out.parsed.major_weaknesses) >= 1


def test_repair_heuristic_extraction_handles_numbered_weakness_heading():
    prose = """
**1. Overall Purpose & Summary**
This manuscript presents a practical AI-assisted workflow for reaction array design.

**3. Strengths**
- Clear integration with automation.
- Practical demonstration with useful yields.

**4. Weaknesses**
- Limited reaction scope.
- Missing baseline comparison.
"""
    out = parse_and_repair(
        prose,
        provider=DummyProvider(),
        repair_models=["qwen2.5:7b-instruct"],
        timeout_seconds=5,
        logger=logging.getLogger("test"),
        allow_self_repair=False,
    )
    assert out.parsed is not None
    assert out.repair_stage == "heuristic_extraction"
    assert any("Limited reaction scope" in w for w in out.parsed.major_weaknesses)
