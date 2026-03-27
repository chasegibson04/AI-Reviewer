from ai_reviewer.ingest.retrieval import retrieve_top_k
from ai_reviewer.ingest.types import DocumentChunk
from ai_reviewer.models.base import ProviderError, ProviderErrorCode


class OverflowEmbedProvider:
    def __init__(self, limit: int = 500):
        self.limit = limit
        self.calls = []

    def embed(self, text: str, model: str, timeout_seconds: int = 90):
        self.calls.append(len(text))
        if len(text) > self.limit:
            raise ProviderError("the input length exceeds the context length", code=ProviderErrorCode.CONTEXT_OVERFLOW)

        class E:
            embedding = [0.1] * 16

        return E()


def test_retrieve_top_k_adapts_to_context_overflow():
    provider = OverflowEmbedProvider(limit=500)
    chunks = [
        DocumentChunk(chunk_id="c1", text="A" * 2000, start_char=0, end_char=2000),
        DocumentChunk(chunk_id="c2", text="B" * 1900, start_char=2000, end_char=3900),
    ]
    out = retrieve_top_k(
        query="Q" * 1700,
        chunks=chunks,
        provider=provider,  # type: ignore[arg-type]
        embedding_model="mxbai-embed-large:latest",
        max_chunk_embed_chars=2000,
    )
    assert len(out) == 2
    assert any(n > 500 for n in provider.calls)
    assert any(n <= 500 for n in provider.calls)

