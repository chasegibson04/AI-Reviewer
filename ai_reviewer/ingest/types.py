from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DocumentChunk:
    chunk_id: str
    text: str
    heading: str | None = None
    start_char: int = 0
    end_char: int = 0
    source_page: int | None = None


@dataclass
class ParsedDocument:
    source_path: Path
    source_path_abs: Path
    source_path_rel: str
    file_size_bytes: int
    document_type: str
    parse_engine: str
    ingest_timestamp: str
    raw_text: str
    cleaned_text: str
    headings: list[str] = field(default_factory=list)
    page_count: int | None = None
    parse_warnings: list[str] = field(default_factory=list)
    chunks: list[DocumentChunk] = field(default_factory=list)


@dataclass
class ParseFailure:
    source_path: Path
    error: str


@dataclass
class RetrievedChunk:
    chunk: DocumentChunk
    score: float
