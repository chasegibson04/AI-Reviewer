from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class DecisionLabel(str, Enum):
    ACCEPT = "accept"
    RETRY = "retry"
    REJECT = "reject"


class MissingDimension(str, Enum):
    SPECIFICITY = "specificity"
    GROUNDING = "grounding"
    EDITORIAL_USEFULNESS = "editorial_usefulness"
    REVIEWER_USEFULNESS = "reviewer_usefulness"
    DISTINCTNESS = "distinctness"
    ACTIONABILITY = "actionability"
    SYNTHESIS_VALUE = "synthesis_value"


class RouteDecision(BaseModel):
    stage_sequence: list[str] = Field(default_factory=list)
    skipped_stages: list[str] = Field(default_factory=list)
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class StageQualityAssessment(BaseModel):
    decision: DecisionLabel = DecisionLabel.ACCEPT
    quality_score: float = Field(default=0.0, ge=0.0, le=100.0)
    specificity_score: float = Field(default=0.0, ge=0.0, le=100.0)
    grounding_score: float = Field(default=0.0, ge=0.0, le=100.0)
    actionability_score: float = Field(default=0.0, ge=0.0, le=100.0)
    genericity_flag: bool = False
    missing_dimensions: list[MissingDimension] = Field(default_factory=list)
    retry_recommended: bool = False
    retry_reason: str = ""
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class RetryDecision(BaseModel):
    should_retry: bool = False
    retry_instruction: str = ""
    retry_reason: str = ""
    retries_used_stage: int = 0
    retries_used_total: int = 0
    retries_remaining_stage: int = 0
    retries_remaining_total: int = 0


class VersionComparison(BaseModel):
    winner: str = "A"
    materially_improved: bool = False
    improvements: list[str] = Field(default_factory=list)
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class DistinctnessAssessment(BaseModel):
    distinct: bool = True
    overlap_score: float = Field(default=0.0, ge=0.0, le=1.0)
    overlap_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class FinalSynthesisAssessment(BaseModel):
    grounded: bool = True
    adds_value_over_concat: bool = True
    includes_revision_priorities: bool = True
    states_offline_limits: bool = True
    missing_dimensions: list[MissingDimension] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

