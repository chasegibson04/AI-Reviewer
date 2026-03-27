from ai_reviewer.config import load_config
from ai_reviewer.review.deep_run import _select_stage_models


def test_deep_run_model_fallback_selection():
    cfg = load_config()
    stack = _select_stage_models(["gemma3:27b", "mistral-small3.1:24b"], cfg)
    assert stack["context_synthesis"] == "gemma3:27b"
    assert stack["reconciliation"] in {"mistral-small3.1:24b", "gemma3:27b"}

