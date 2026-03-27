import pytest

from ai_reviewer.models.base import ChatRequest, ProviderError, ProviderErrorCode
from ai_reviewer.models.ollama_provider import OllamaProvider


class FakeResp:
    def __init__(self, payload):
        self._payload = payload
        self.text = ""

    def json(self):
        return self._payload

    def raise_for_status(self):
        return


def test_missing_model_error(monkeypatch):
    provider = OllamaProvider(strict_offline=False)

    def fake_request(method, url, timeout=0, **kwargs):
        if url.endswith('/api/chat'):
            return FakeResp({"error": "model not found"})
        if url.endswith('/api/version'):
            return FakeResp({"version": "x"})
        if url.endswith('/api/tags'):
            return FakeResp({"models": []})
        return FakeResp({})

    monkeypatch.setattr("requests.request", fake_request)
    with pytest.raises(ProviderError) as exc:
        provider.chat(ChatRequest(model="missing", system_prompt="s", user_prompt="u", timeout_seconds=1))
    assert exc.value.code == ProviderErrorCode.MODEL_MISSING
