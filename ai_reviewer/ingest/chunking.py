from __future__ import annotations

from ai_reviewer.ingest.types import DocumentChunk, ParsedDocument


def chunk_document(doc: ParsedDocument, max_chars: int = 2500, overlap: int = 250) -> list[DocumentChunk]:
    text = doc.cleaned_text
    if not text:
        doc.parse_warnings.append("Cannot chunk empty document.")
        return []

    chunks: list[DocumentChunk] = []
    start = 0
    idx = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunk_text = text[start:end]

        if end < len(text):
            boundary = chunk_text.rfind("\n\n")
            if boundary > int(max_chars * 0.45):
                end = start + boundary
                chunk_text = text[start:end]

        chunks.append(
            DocumentChunk(
                chunk_id=f"{doc.source_path.stem}-{idx:03d}",
                text=chunk_text,
                start_char=start,
                end_char=end,
            )
        )
        idx += 1
        if end >= len(text):
            break
        start = max(end - overlap, 0)

    doc.chunks = chunks
    return chunks
