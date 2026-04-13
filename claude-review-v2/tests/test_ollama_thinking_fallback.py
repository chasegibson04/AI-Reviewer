from copy import deepcopy

from src.bridge.python import review_mcp_server as bridge


def test_chat_empty_thinking_falls_back_to_generate_response() -> None:
    original = bridge._ollama_request
    calls: list[tuple[str, dict | None]] = []

    def fake(endpoint: str, payload: dict | None = None, timeout_seconds: float = 45.0):  # noqa: ARG001
        calls.append((endpoint, deepcopy(payload)))
        if endpoint == "/api/chat":
            return {
                "ok": True,
                "payload": {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "thinking": "internal reasoning only",
                    },
                    "done": True,
                    "done_reason": "length",
                },
            }
        if endpoint == "/api/generate":
            return {"ok": True, "payload": {"response": "OK_SHORT"}}
        return {"ok": False, "error": f"unexpected endpoint: {endpoint}"}

    bridge._ollama_request = fake  # type: ignore[assignment]
    try:
        out = bridge._ollama_chat_completion(
            model="gemma4:31b",
            system_prompt="You are concise.",
            user_prompt="Reply exactly OK_SHORT",
            max_tokens=32,
            temperature=0.0,
            timeout_seconds=10.0,
            json_mode=False,
        )
    finally:
        bridge._ollama_request = original  # type: ignore[assignment]

    assert out.get("ok") is True
    assert out.get("content") == "OK_SHORT"
    assert calls[0][0] == "/api/chat"
    assert isinstance(calls[0][1], dict) and calls[0][1].get("think") is False
    assert calls[1][0] == "/api/generate"
    assert isinstance(calls[1][1], dict) and calls[1][1].get("think") is False


def test_chat_retries_without_think_when_field_unknown() -> None:
    original = bridge._ollama_request
    calls: list[tuple[str, dict | None]] = []
    seen_first = {"hit": False}

    def fake(endpoint: str, payload: dict | None = None, timeout_seconds: float = 45.0):  # noqa: ARG001
        calls.append((endpoint, deepcopy(payload)))
        if endpoint != "/api/chat":
            return {"ok": False, "error": "unexpected endpoint"}
        if not seen_first["hit"]:
            seen_first["hit"] = True
            return {"ok": False, "error": 'HTTP 400: unknown field "think"'}
        return {"ok": True, "payload": {"message": {"role": "assistant", "content": "OK"}}}

    bridge._ollama_request = fake  # type: ignore[assignment]
    try:
        out = bridge._ollama_chat_completion(
            model="gemma4:31b",
            system_prompt="System",
            user_prompt="User",
            max_tokens=16,
            temperature=0.0,
            timeout_seconds=10.0,
            json_mode=False,
        )
    finally:
        bridge._ollama_request = original  # type: ignore[assignment]

    assert out.get("ok") is True
    assert out.get("content") == "OK"
    assert len(calls) == 2
    first_payload = calls[0][1] if isinstance(calls[0][1], dict) else {}
    second_payload = calls[1][1] if isinstance(calls[1][1], dict) else {}
    assert first_payload.get("think") is False
    assert "think" not in second_payload
