import logging

from ai_reviewer.models.base import ChatRequest, ChatResponse, Provider
from ai_reviewer.review.repair import parse_and_repair


class BadRepairProvider(Provider):
    def list_models(self):
        return ["qwen2.5:7b-instruct"]

    def health(self):
        return True, "ok"

    def chat(self, request: ChatRequest):
        return ChatResponse(model=request.model, content="this is not json")

    def embed(self, text: str, model: str, timeout_seconds: int = 90):
        raise NotImplementedError


def test_malformed_output_regression_returns_degraded_schema():
    out = parse_and_repair(
        text="NOT JSON",
        provider=BadRepairProvider(),
        repair_models=["qwen2.5:7b-instruct"],
        timeout_seconds=10,
        logger=logging.getLogger("test"),
    )
    assert out.parsed is not None
    assert out.parsed.document_metadata.get("warning") == "schema_recovery_failed"
    assert out.parse_failures >= 1
