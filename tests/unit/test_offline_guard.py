import pytest

from ai_reviewer.models.base import ProviderError
from ai_reviewer.models.ollama_provider import OllamaProvider
from ai_reviewer.models.base import ChatRequest


def test_strict_offline_blocks_remote_url():
    with pytest.raises(ProviderError):
        OllamaProvider(base_url="http://8.8.8.8:11434", strict_offline=True)


def test_non_strict_offline_allows_remote_url():
    provider = OllamaProvider(base_url="http://8.8.8.8:11434", strict_offline=False)
    assert provider.base_url == "http://8.8.8.8:11434"


def test_embedding_model_blocked_for_chat():
    provider = OllamaProvider()
    with pytest.raises(ProviderError):
        provider.chat(
            ChatRequest(
                model="bge-m3:latest",
                system_prompt="json",
                user_prompt="{}",
                max_tokens=10,
                timeout_seconds=5,
            )
        )
