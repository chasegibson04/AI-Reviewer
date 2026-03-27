from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, Field


class SlackWorkflowRequest(BaseModel):
    command: str
    project: str | None = None
    profile: str | None = None
    model: str | None = None
    strict_schema: bool = True
    retrieval: bool = True


class SlackSubmission(BaseModel):
    request_id: str
    user_id: str
    channel_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    file_path: str
    file_name: str
    workflow: SlackWorkflowRequest


class SlackResultSummary(BaseModel):
    request_id: str
    project_id: str
    status: str
    run_id: str | None = None
    headline: str
    outputs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
