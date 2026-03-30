from ai_reviewer.models.selector import (
    infer_model_roles,
    model_capability,
    normalize_deep_run_routing_mode,
    select_deep_run_stage_models,
    split_chat_and_embedding_models,
)
from ai_reviewer.config import load_config


def test_split_chat_embedding_models():
    chat, emb = split_chat_and_embedding_models(["gemma3:27b", "mxbai-embed-large:latest", "bge-m3:latest"])
    assert "gemma3:27b" in chat
    assert "mxbai-embed-large:latest" in emb
    assert "bge-m3:latest" in emb


def test_infer_model_roles_respects_defaults():
    cfg = load_config()
    installed = [
        "gemma3:27b",
        "llama3.3:70b-instruct-q4_K_M",
        "mxbai-embed-large:latest",
        "mistral-small3.1:24b",
    ]
    roles = infer_model_roles(installed, cfg)
    assert roles.balanced_model == "gemma3:27b"
    assert roles.deep_model == "llama3.3:70b-instruct-q4_K_M"
    assert roles.embedding_model == "mxbai-embed-large:latest"
    assert "mistral-small3.1:24b" in roles.repair_candidates


def test_multimodal_capability_classification():
    cap = model_capability("qwen3-vl:8b")
    assert cap.kind == "multimodal"


def test_mac_arm_model_allowance(monkeypatch):
    import ai_reviewer.models.selector as selector
    monkeypatch.setattr(selector, "detect_platform", lambda: type("X", (), {"is_mac_arm": True})())
    cfg = load_config()
    installed = ["qwen3:14b", "mxbai-embed-large:latest"]
    roles = infer_model_roles(installed, cfg)
    assert roles.balanced_model == "qwen3:14b"


def test_normalize_deep_run_routing_mode():
    assert normalize_deep_run_routing_mode("MAX-QUALITY") == "max_quality"
    assert normalize_deep_run_routing_mode("weird") == "default"


def test_select_deep_run_stage_models_default_avoids_embeddings():
    cfg = load_config()
    installed = [
        "llama3.3:70b-instruct-q4_K_M",
        "mistral-small3.2:latest",
        "phi4-mini:latest",
        "qwen2.5:7b-instruct",
        "mxbai-embed-large:latest",
    ]
    stack = select_deep_run_stage_models(installed, cfg, mode="default")
    assert stack["high_level_review"] == "llama3.3:70b-instruct-q4_K_M"
    assert stack["line_edits"] == "mistral-small3.2:latest"
    assert stack["reconciliation"] == "qwen2.5:7b-instruct"
    assert "embed" not in "".join(stack.values()).lower()


def test_select_deep_run_stage_models_max_quality_upgrades_reconciliation_and_editing():
    cfg = load_config()
    installed = [
        "llama3.3:70b-instruct-q4_K_M",
        "gemma3:27b",
        "mistral-small3.1:24b",
        "phi4-mini:latest",
        "qwen2.5:7b-instruct",
        "mxbai-embed-large:latest",
    ]
    stack = select_deep_run_stage_models(installed, cfg, mode="max_quality")
    assert stack["high_level_review"] == "llama3.3:70b-instruct-q4_K_M"
    assert stack["methods_verification"] == "llama3.3:70b-instruct-q4_K_M"
    assert stack["supporting_digest"] == "gemma3:27b"
    assert stack["reconciliation"] == "gemma3:27b"
    assert stack["line_edits"] == "gemma3:27b"
    assert stack["style_alignment"] == "gemma3:27b"


def test_select_deep_run_stage_models_max_quality_mac_safe_fallback(monkeypatch):
    import ai_reviewer.models.selector as selector

    monkeypatch.setattr(selector, "detect_platform", lambda: type("X", (), {"is_mac_arm": True})())
    cfg = load_config()
    installed = [
        "qwen3:14b",
        "gemma3:12b",
        "phi4-mini:latest",
        "mxbai-embed-large:latest",
    ]
    stack = select_deep_run_stage_models(installed, cfg, mode="max_quality")
    assert stack["high_level_review"] == "qwen3:14b"
    assert stack["final_arbitration"] == "qwen3:14b"
    assert stack["line_edits"] == "qwen3:14b"
    assert "mxbai-embed-large:latest" not in stack.values()


def test_select_deep_run_stage_models_mac_arm_prefers_stronger_installed_text_models(monkeypatch):
    import ai_reviewer.models.selector as selector

    monkeypatch.setattr(selector, "detect_platform", lambda: type("X", (), {"is_mac_arm": True})())
    cfg = load_config()
    installed = [
        "deepseek-coder-v2:latest",
        "qwen3:32b",
        "qwen3-vl:8b",
        "gemma3:27b",
        "qwen3:14b",
        "mistral-small3.1:24b",
        "qwen2.5:7b-instruct",
        "mxbai-embed-large:latest",
        "bge-m3:latest",
        "qwen3:8b",
        "phi4-reasoning:latest",
        "mistral-small3.2:latest",
    ]
    stack = select_deep_run_stage_models(installed, cfg, mode="max_quality")
    assert stack["high_level_review"] == "qwen3:32b"
    assert stack["adversarial_review"] == "qwen3:32b"
    assert stack["methods_verification"] == "qwen3:32b"
    assert stack["final_arbitration"] == "qwen3:32b"
    assert stack["supporting_digest"] == "gemma3:27b"
    assert stack["line_edits"] == "gemma3:27b"
    assert "qwen3-vl:8b" not in stack.values()
    assert "mxbai-embed-large:latest" not in stack.values()
    assert "bge-m3:latest" not in stack.values()
