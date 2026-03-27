from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


TrainingCategory = Literal[
    "published_papers",
    "formatting_color_guides",
    "external_guides",
    "other_groups_papers",
    "in_progress_examples",
]


class TrainingTakeaways(BaseModel):
    file_id: str
    source_path: str
    category: TrainingCategory
    summary: str
    style_guidance: list[str] = Field(default_factory=list)
    formatting_layout_guidance: list[str] = Field(default_factory=list)
    language_grammar_guidance: list[str] = Field(default_factory=list)
    reviewer_tone_guidance: list[str] = Field(default_factory=list)
    notable_conventions: list[str] = Field(default_factory=list)
    confidence: float = 0.6
    quality_notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TrainingFileRecord(BaseModel):
    file_id: str
    relative_path: str
    absolute_path: str
    category: TrainingCategory
    fingerprint: str
    size_bytes: int
    modified_timestamp: float
    parse_status: Literal["ok", "failed"]
    digest_status: Literal["ok", "failed"]
    last_processed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    warnings: list[str] = Field(default_factory=list)
    included_in_guidance: bool = True
    parsed_metadata_file: str | None = None
    takeaway_file: str | None = None
    error: str | None = None


class TrainingManifest(BaseModel):
    schema_version: int = 1
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_root: str
    files: dict[str, TrainingFileRecord] = Field(default_factory=dict)


class GlobalGuidance(BaseModel):
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    active_file_count: int = 0
    active_by_category: dict[str, int] = Field(default_factory=dict)
    global_summary: str = ""
    style_guidance: list[str] = Field(default_factory=list)
    formatting_guidance: list[str] = Field(default_factory=list)
    language_guidance: list[str] = Field(default_factory=list)
    reviewer_tone_guidance: list[str] = Field(default_factory=list)
    category_guidance: dict[str, list[str]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)

