from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests

from ai_reviewer.models.base import (
    ChatRequest,
    ChatResponse,
    EmbeddingResponse,
    Provider,
    ProviderError,
    ProviderErrorCode,
)
from ai_reviewer.models.selector import is_embedding_model

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


def _approx_tokens(text: str) -> int:
    return max(1, int(len(text) / 4))


def _normalize_duration(value: Any, fallback: float | None = None) -> float | None:
    try:
        v = float(value)
    except Exception:
        return fallback
    if v > 1_000_000:
        v = v / 1_000_000_000.0
    return v


class OllamaProvider(Provider):
    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_URL,
        strict_offline: bool = True,
        connect_timeout_seconds: int = 10,
        chat_attempts: int = 3,
        embed_attempts: int = 2,
        base_backoff_seconds: float = 1.0,
        logger: logging.Logger | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.strict_offline = strict_offline
        self.connect_timeout_seconds = connect_timeout_seconds
        self.chat_attempts = max(1, chat_attempts)
        self.embed_attempts = max(1, embed_attempts)
        self.base_backoff_seconds = max(0.1, base_backoff_seconds)
        self.logger = logger or logging.getLogger("ai_reviewer.ollama")
        if strict_offline and not self.base_url.startswith("http://127.0.0.1") and not self.base_url.startswith("http://localhost"):
            raise ProviderError(
                "Strict offline mode permits only localhost/127.0.0.1 Ollama URLs.",
                code=ProviderErrorCode.UNSUPPORTED,
            )

    def _request(self, method: str, path: str, timeout: int, **kwargs: Any) -> requests.Response:
        url = f"{self.base_url}{path}"
        self.logger.debug("ollama_request method=%s url=%s timeout=%s", method, url, timeout)
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.ConnectionError as exc:
            raise ProviderError(
                f"Could not connect to Ollama at {self.base_url}. Is 'ollama serve' running?",
                code=ProviderErrorCode.UNREACHABLE,
            ) from exc
        except requests.Timeout as exc:
            raise ProviderError(
                f"Request timed out after {timeout}s for {path}.",
                code=ProviderErrorCode.TIMEOUT,
            ) from exc
        except requests.HTTPError as exc:
            body = ""
            try:
                body = exc.response.text
            except Exception:
                pass
            raise ProviderError(
                f"Ollama HTTP error on {path}: {exc}. Body={body[:400]}",
                code=ProviderErrorCode.UNKNOWN,
            ) from exc

    def health(self) -> tuple[bool, str]:
        try:
            resp = self._request("GET", "/api/version", timeout=self.connect_timeout_seconds)
            version = resp.json().get("version", "unknown")
            return True, f"Ollama reachable at {self.base_url} (version={version})"
        except Exception as exc:
            return False, str(exc)

    def list_models(self) -> list[str]:
        resp = self._request("GET", "/api/tags", timeout=self.connect_timeout_seconds)
        payload = resp.json()
        models = [m.get("name", "") for m in payload.get("models", []) if m.get("name")]
        return sorted(set(models))

    def _validate_chat_response(self, payload: dict[str, Any], model: str) -> str:
        if payload.get("error"):
            msg = str(payload["error"])
            lower = msg.lower()
            if "not found" in lower:
                raise ProviderError(f"Model not found: {model}", code=ProviderErrorCode.MODEL_MISSING)
            if "context" in lower:
                raise ProviderError(
                    f"Likely context overflow for model {model}: {msg}",
                    code=ProviderErrorCode.CONTEXT_OVERFLOW,
                )
            raise ProviderError(f"Ollama model error ({model}): {msg}", code=ProviderErrorCode.UNKNOWN)

        if "message" not in payload and "response" not in payload:
            raise ProviderError(
                f"Malformed chat envelope. keys={list(payload.keys())[:15]}",
                code=ProviderErrorCode.MALFORMED_RESPONSE,
            )

        content = ""
        if isinstance(payload.get("message"), dict):
            content = payload["message"].get("content", "")
        if not content and isinstance(payload.get("response"), str):
            content = payload["response"]
        if not content or not content.strip():
            raise ProviderError("Model returned empty content.", code=ProviderErrorCode.EMPTY_RESPONSE)
        return content

    def chat(self, request: ChatRequest) -> ChatResponse:
        if is_embedding_model(request.model):
            raise ProviderError(
                f"Embedding-only model cannot be used for chat: {request.model}",
                code=ProviderErrorCode.UNSUPPORTED,
            )
        body = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
            "stream": request.stream,
        }
        if request.metadata.get("json_mode"):
            body["format"] = "json"

        prompt_chars = len(request.system_prompt) + len(request.user_prompt)
        prompt_tokens = _approx_tokens(request.system_prompt) + _approx_tokens(request.user_prompt)

        last_err: Exception | None = None
        for attempt in range(1, self.chat_attempts + 1):
            try:
                started = time.time()
                response = self._request(
                    "POST",
                    "/api/chat",
                    timeout=request.timeout_seconds,
                    json=body,
                )
                if request.stream:
                    lines = [line for line in response.text.splitlines() if line.strip()]
                    if not lines:
                        raise ProviderError("Streaming response had no JSON lines.", code=ProviderErrorCode.EMPTY_RESPONSE)
                    payload = json.loads(lines[-1])
                else:
                    payload = response.json()
                content = self._validate_chat_response(payload, request.model)
                elapsed = time.time() - started
                self.logger.debug(
                    "chat_ok model=%s attempt=%s elapsed=%.2fs prompt_chars=%s prompt_tokens~=%s",
                    request.model,
                    attempt,
                    elapsed,
                    prompt_chars,
                    prompt_tokens,
                )
                return ChatResponse(
                    content=content,
                    model=request.model,
                    total_duration=_normalize_duration(payload.get("total_duration"), elapsed),
                    eval_count=payload.get("eval_count"),
                    prompt_eval_count=payload.get("prompt_eval_count"),
                    retries_used=attempt - 1,
                    prompt_chars=prompt_chars,
                    approx_prompt_tokens=prompt_tokens,
                    raw=payload,
                )
            except ProviderError as exc:
                last_err = exc
                self.logger.warning(
                    "chat_attempt_failed model=%s attempt=%s/%s code=%s error=%s",
                    request.model,
                    attempt,
                    self.chat_attempts,
                    getattr(exc, "code", ProviderErrorCode.UNKNOWN),
                    exc,
                )
                if attempt >= self.chat_attempts:
                    break
                # warm-up and transient hiccup tolerance
                time.sleep(self.base_backoff_seconds * attempt)

        assert last_err is not None
        raise last_err

    def embed(self, text: str, model: str, timeout_seconds: int = 90) -> EmbeddingResponse:
        body = {"model": model, "input": text}
        last_err: Exception | None = None

        for attempt in range(1, self.embed_attempts + 1):
            try:
                response = self._request("POST", "/api/embed", timeout=timeout_seconds, json=body)
                payload = response.json()
                if payload.get("error"):
                    msg = str(payload["error"])
                    if "not found" in msg.lower():
                        raise ProviderError(
                            f"Embedding model missing: {model}",
                            code=ProviderErrorCode.EMBEDDING_MODEL_MISSING,
                        )
                    raise ProviderError(f"Embedding call failed: {msg}", code=ProviderErrorCode.UNKNOWN)

                embeddings = payload.get("embeddings")
                if not embeddings or not isinstance(embeddings, list):
                    raise ProviderError("Malformed embedding response.", code=ProviderErrorCode.MALFORMED_RESPONSE)
                vector = embeddings[0]
                if not vector:
                    raise ProviderError("Empty embedding vector.", code=ProviderErrorCode.EMPTY_RESPONSE)
                return EmbeddingResponse(
                    embedding=vector,
                    model=model,
                    total_duration=_normalize_duration(payload.get("total_duration")),
                    retries_used=attempt - 1,
                    raw=payload,
                )
            except ProviderError as exc:
                msg = str(exc).lower()
                if (
                    getattr(exc, "code", ProviderErrorCode.UNKNOWN) == ProviderErrorCode.UNKNOWN
                    and ("context length" in msg or "input length exceeds" in msg or "context" in msg)
                ):
                    exc.code = ProviderErrorCode.CONTEXT_OVERFLOW
                last_err = exc
                if exc.code == ProviderErrorCode.CONTEXT_OVERFLOW:
                    self.logger.debug(
                        "embed_attempt_context_overflow model=%s attempt=%s/%s",
                        model,
                        attempt,
                        self.embed_attempts,
                    )
                else:
                    self.logger.warning(
                        "embed_attempt_failed model=%s attempt=%s/%s code=%s error=%s",
                        model,
                        attempt,
                        self.embed_attempts,
                        getattr(exc, "code", ProviderErrorCode.UNKNOWN),
                        exc,
                    )
                if exc.code == ProviderErrorCode.CONTEXT_OVERFLOW:
                    break
                if attempt >= self.embed_attempts:
                    break
                time.sleep(self.base_backoff_seconds * attempt)

        assert last_err is not None
        raise last_err
