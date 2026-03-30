from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


MaterialCategory = Literal[
    "manuscript_draft",
    "published_paper",
    "reviewer_comments",
    "supplemental_document",
    "style_guide",
    "journal_instructions",
    "reference_example",
    "methods_reference",
    "miscellaneous",
]


class ProjectDefaults(BaseModel):
    review_model: str
    embedding_model: str | None = None
    profile: str = "balanced"
    strict_schema: bool = True
    retrieval_enabled: bool = True
    keep_raw_outputs: bool = True


class MaterialMetadata(BaseModel):
    material_id: str
    filename: str
    original_path: str
    relative_path: str | None = None
    category: MaterialCategory
    added_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    normalized_text_file: str | None = None


class RunRecord(BaseModel):
    run_id: str
    workflow: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: Literal["success", "failed", "partial"] = "success"
    profile: str | None = None
    model: str | None = None
    embedding_model: str | None = None
    output_dir: str
    warning_count: int = 0
    settings: dict = Field(default_factory=dict)


class EvaluationRecord(BaseModel):
    evaluation_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    anchor_material_id: str
    run_id: str
    profiles: list[str] = Field(default_factory=list)
    output_dir: str


class ProjectMetadata(BaseModel):
    project_id: str
    name: str
    slug: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    archived: bool = False
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    output_root: str = "outputs"
    defaults: ProjectDefaults
    materials: list[MaterialMetadata] = Field(default_factory=list)
    runs: list[RunRecord] = Field(default_factory=list)
    evaluations: list[EvaluationRecord] = Field(default_factory=list)
