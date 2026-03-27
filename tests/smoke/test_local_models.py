import pytest

from ai_reviewer.models.base import ChatRequest
from ai_reviewer.models.ollama_provider import OllamaProvider


@pytest.mark.smoke
def test_real_local_models_smoke():
    provider = OllamaProvider()
    ok, _ = provider.health()
    if not ok:
        pytest.skip("Ollama not running")

    models = provider.list_models()
    preferred = [
        "gemma3:27b",
        "llama3.3:70b-instruct-q4_K_M",
        "mistral-small3.1:24b",
    ]
    available = [m for m in preferred if m in models]
    if not available:
        pytest.skip("No preferred smoke models installed")

    for model in available:
        resp = provider.chat(
            ChatRequest(
                model=model,
                system_prompt="Return a short JSON object.",
                user_prompt='{"ok": true, "model": "' + model + '"}',
                temperature=0,
                max_tokens=120,
                timeout_seconds=120,
            )
        )
        assert resp.content


@pytest.mark.smoke
def test_real_embedding_smoke():
    provider = OllamaProvider()
    ok, _ = provider.health()
    if not ok:
        pytest.skip("Ollama not running")

    models = provider.list_models()
    if "mxbai-embed-large:latest" not in models:
        pytest.skip("mxbai-embed-large:latest not installed")

    emb = provider.embed("embedding smoke test", model="mxbai-embed-large:latest", timeout_seconds=60)
    assert len(emb.embedding) > 16
