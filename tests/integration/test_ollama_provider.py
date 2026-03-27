import json

from ai_reviewer.models.ollama_provider import OllamaProvider
from ai_reviewer.models.base import ChatRequest


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or json.dumps(self._payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            from requests import HTTPError
            err = HTTPError("bad")
            err.response = self
            raise err


def test_ollama_provider_list_and_chat(monkeypatch):
    provider = OllamaProvider()

    def fake_request(method, url, timeout=0, **kwargs):
        if url.endswith('/api/tags'):
            return FakeResponse(payload={"models": [{"name": "gemma3:27b"}]})
        if url.endswith('/api/chat'):
            return FakeResponse(payload={"message": {"content": '{"summary":"ok"}'}, "total_duration": 1})
        if url.endswith('/api/version'):
            return FakeResponse(payload={"version": "1.0"})
        raise AssertionError(url)

    monkeypatch.setattr("requests.request", fake_request)
    assert provider.health()[0]
    assert provider.list_models() == ["gemma3:27b"]
    resp = provider.chat(ChatRequest(model="gemma3:27b", system_prompt="s", user_prompt="u"))
    assert "summary" in resp.content
