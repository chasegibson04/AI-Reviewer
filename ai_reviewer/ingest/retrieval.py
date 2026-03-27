from __future__ import annotations

import math
from typing import Iterable

from ai_reviewer.ingest.types import DocumentChunk, RetrievedChunk
from ai_reviewer.models.base import Provider, ProviderError, ProviderErrorCode


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def retrieve_top_k(
    query: str,
    chunks: Iterable[DocumentChunk],
    provider: Provider,
    embedding_model: str,
    top_k: int = 6,
    timeout_seconds: int = 90,
    max_chunk_embed_chars: int = 6000,
) -> list[RetrievedChunk]:
    def _adaptive_embed(text: str, *, start_chars: int, min_chars: int = 350) -> list[float]:
        current = max(min(start_chars, len(text)), 1)
        lengths = [current]
        while current >= max(min_chars, 2):
            lengths.append(current)
            current //= 2
            if current <= 1:
                break
        if min_chars <= len(text) and lengths[-1] != min_chars:
            lengths.append(min_chars)
        if lengths[0] != max(len(text), 1):
            lengths.insert(0, len(text))
        # dedupe while preserving order
        lengths = list(dict.fromkeys(max(1, x) for x in lengths))

        last_exc: Exception | None = None
        for length in lengths:
            try:
                return provider.embed(text[:length], model=embedding_model, timeout_seconds=timeout_seconds).embedding
            except ProviderError as exc:
                last_exc = exc
                if exc.code != ProviderErrorCode.CONTEXT_OVERFLOW:
                    raise
                continue
        assert last_exc is not None
        raise last_exc

    chunk_list = list(chunks)
    query_emb = _adaptive_embed(query, start_chars=min(max_chunk_embed_chars, 1800), min_chars=128)

    scored: list[RetrievedChunk] = []
    for chunk in chunk_list:
        emb = _adaptive_embed(chunk.text, start_chars=max_chunk_embed_chars, min_chars=320)
        scored.append(RetrievedChunk(chunk=chunk, score=_cosine(query_emb, emb)))

    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:top_k]
