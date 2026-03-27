from ai_reviewer.models.selector import infer_model_roles, split_chat_and_embedding_models
from ai_reviewer.config import load_config


def test_split_chat_embedding_models():
    chat, emb = split_chat_and_embedding_models(["gemma3:27b", "mxbai-embed-large:latest"])
    assert "gemma3:27b" in chat
    assert "mxbai-embed-large:latest" in emb


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
