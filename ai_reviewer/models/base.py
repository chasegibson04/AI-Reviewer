from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProviderErrorCode(str, Enum):
    UNREACHABLE = "unreachable"
    TIMEOUT = "timeout"
    MODEL_MISSING = "model_missing"
    EMBEDDING_MODEL_MISSING = "embedding_model_missing"
    MALFORMED_RESPONSE = "malformed_response"
    CONTEXT_OVERFLOW = "context_overflow"
    EMPTY_RESPONSE = "empty_response"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass
class ChatRequest:
    model: str
    system_prompt: str
    user_prompt: str
    temperature: float = 0.2
    max_tokens: int = 2048
    timeout_seconds: int = 180
    stream: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponse:
    content: str
    model: str
    total_duration: float | None = None
    eval_count: int | None = None
    prompt_eval_count: int | None = None
    retries_used: int = 0
    prompt_chars: int = 0
    approx_prompt_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddingResponse:
    embedding: list[float]
    model: str
    total_duration: float | None = None
    retries_used: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


class ProviderError(RuntimeError):
    def __init__(self, message: str, code: ProviderErrorCode = ProviderErrorCode.UNKNOWN):
        super().__init__(message)
        self.code = code


class Provider:
    def list_models(self) -> list[str]:
        raise NotImplementedError

    def health(self) -> tuple[bool, str]:
        raise NotImplementedError

    def chat(self, request: ChatRequest) -> ChatResponse:
        raise NotImplementedError

    def embed(self, text: str, model: str, timeout_seconds: int = 90) -> EmbeddingResponse:
        raise NotImplementedError
