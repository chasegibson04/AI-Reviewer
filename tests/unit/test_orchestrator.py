import json

from ai_reviewer.models.base import ChatRequest, ChatResponse, Provider
from ai_reviewer.orchestrator.controller import OrchestratorController, OrchestratorRuntimeState


class _StubProvider(Provider):
    def __init__(self, payload: dict):
        self.payload = payload

    def list_models(self):
        return ["qwen3:8b"]

    def health(self):
        return True, "ok"

    def chat(self, request: ChatRequest):
        return ChatResponse(content=json.dumps(self.payload), model=request.model)

    def embed(self, text: str, model: str, timeout_seconds: int = 90):
        raise NotImplementedError


def test_retry_budget_enforced():
    st = OrchestratorRuntimeState(max_stage_retries=1, max_total_retries=2)
    assert st.can_retry(0) is True
    st.consume_retry()
    assert st.can_retry(1) is False
    assert st.can_retry(0) is True
    st.consume_retry()
    assert st.can_retry(0) is False


def test_stage_assessment_deterministic_retry_for_sparse():
    orch = OrchestratorController(_StubProvider({}), model="qwen3:8b", enabled=False)
    qa = orch.evaluate_stage_output(
        stage_name="writing",
        artifact_text="Overall, the manuscript could be improved.",
        quality_signals={
            "summary_len": 50,
            "details_count": 1,
            "actions_count": 0,
            "methods_count": 0,
            "stats_count": 0,
            "writing_count": 0,
        },
        timeout_seconds=10,
    )
    assert qa.retry_recommended is True
    assert qa.quality_score < 65


def test_fail_open_uses_deterministic_when_llm_invalid_json():
    class _BadProvider(_StubProvider):
        def chat(self, request: ChatRequest):
            return ChatResponse(content="not-json", model=request.model)

    orch = OrchestratorController(_BadProvider({}), model="qwen3:8b", enabled=True, fail_open=True)
    qa = orch.evaluate_stage_output(
        stage_name="methods",
        artifact_text="phactor reaction chatgpt",
        quality_signals={
            "summary_len": 30,
            "details_count": 0,
            "actions_count": 0,
            "methods_count": 0,
            "stats_count": 0,
            "writing_count": 0,
        },
        timeout_seconds=10,
    )
    assert qa.retry_recommended is True


def test_distinctness_overlap_detected():
    orch = OrchestratorController(_StubProvider({}), model="qwen3:8b", enabled=False)
    out = orch.evaluate_distinctness(
        {
            "balanced": "this paper reaction phactor methods results discussion",
            "adversarial": "this paper reaction phactor methods results discussion",
            "methods": "methods controls ablation uncertainty results",
        },
        timeout_seconds=10,
    )
    assert out.overlap_score >= 0.5

