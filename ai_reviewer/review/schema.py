from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Recommendation(BaseModel):
    decision: Literal["accept", "revise", "reject"] = "revise"
    rationale: str


class SectionComment(BaseModel):
    section: str
    comment: str
    severity: Literal["low", "medium", "high"] = "medium"
    evidence_source: str | None = None
    manuscript_quote: str | None = None


class ActionItem(BaseModel):
    action: str
    priority: Literal["low", "medium", "high"] = "medium"
    owner: Literal["author", "reviewer"] = "author"
    evidence_source: str | None = None


class DebugMetadata(BaseModel):
    provider: str
    model: str
    temperature: float
    retries_used: int = 0
    parse_failures: int = 0
    total_duration: float | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None


class GroundedComment(BaseModel):
    comment: str
    evidence_source: str | None = None
    manuscript_quote: str | None = None
    severity: Literal["low", "medium", "high"] = "medium"


class ReviewSchema(BaseModel):
    document_metadata: dict[str, str] = Field(default_factory=dict)
    summary: str
    major_strengths: list[str] = Field(default_factory=list)
    major_weaknesses: list[str] = Field(default_factory=list)
    novelty_concerns: list[str] = Field(default_factory=list)
    methodological_concerns: list[str] = Field(default_factory=list)
    statistical_concerns: list[str] = Field(default_factory=list)
    writing_organization_concerns: list[str] = Field(default_factory=list)
    figure_table_concerns: list[str] = Field(default_factory=list)
    citation_reference_concerns: list[str] = Field(default_factory=list)
    reproducibility_concerns: list[str] = Field(default_factory=list)
    suggested_experiments_analyses: list[str] = Field(default_factory=list)
    recommendation: Recommendation
    confidence: float = Field(ge=0, le=1)
    detailed_reviewer_comments: list[str] = Field(default_factory=list)
    grounded_detailed_comments: list[GroundedComment] = Field(default_factory=list)
    section_specific_comments: list[SectionComment] = Field(default_factory=list)
    extracted_action_items: list[ActionItem] = Field(default_factory=list)
    model_debug_metadata: DebugMetadata


class ClaimEvidenceVerification(BaseModel):
    claim_id: str
    claim_text: str
    verdict: Literal["supported", "partially_supported", "unsupported", "contradicted", "unresolved"]
    evidence_summary: str
    supporting_source: str | None = None
    rationale: str
    confidence: float


class DeepVerificationSchema(BaseModel):
    project_id: str
    run_id: str
    verifications: list[ClaimEvidenceVerification] = Field(default_factory=list)
    summary: str


class CompareSchema(BaseModel):
    summary_of_major_revisions: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
    regressions: list[str] = Field(default_factory=list)
    added_claims: list[str] = Field(default_factory=list)
    removed_claims: list[str] = Field(default_factory=list)
    changed_claims: list[str] = Field(default_factory=list)
    response_to_reviewers_bullets: list[str] = Field(default_factory=list)
    debug: DebugMetadata
