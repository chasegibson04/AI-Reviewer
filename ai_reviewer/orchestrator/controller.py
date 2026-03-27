from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ai_reviewer.models.base import ChatRequest, Provider
from ai_reviewer.orchestrator.schemas import (
    DecisionLabel,
    DistinctnessAssessment,
    FinalSynthesisAssessment,
    MissingDimension,
    RetryDecision,
    StageQualityAssessment,
    VersionComparison,
)
from ai_reviewer.review.repair import extract_json_candidate


GENERIC_PHRASES = [
    "the paper could be improved",
    "more details are needed",
    "future work",
    "this study is interesting",
    "overall, the manuscript",
]


@dataclass
class OrchestratorRuntimeState:
    max_stage_retries: int = 1
    max_total_retries: int = 3
    total_retries_used: int = 0

    def can_retry(self, stage_retries_used: int) -> bool:
        return stage_retries_used < self.max_stage_retries and self.total_retries_used < self.max_total_retries

    def consume_retry(self) -> None:
        self.total_retries_used += 1


class OrchestratorController:
    def __init__(
        self,
        provider: Provider,
        model: str,
        temperature: float = 0.0,
        require_json: bool = True,
        fail_open: bool = True,
        enabled: bool = False,
    ):
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.require_json = require_json
        self.fail_open = fail_open
        self.enabled = enabled

    def _llm_json(self, system_prompt: str, user_prompt: str, timeout_seconds: int) -> dict[str, Any]:
        response = self.provider.chat(
            ChatRequest(
                model=self.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=self.temperature,
                max_tokens=900,
                timeout_seconds=timeout_seconds,
                metadata={"json_mode": self.require_json, "orchestrator": True},
            )
        )
        content = response.content
        candidate = extract_json_candidate(content) or content
        return json.loads(candidate)

    def _deterministic_stage_assessment(
        self,
        stage_name: str,
        artifact_text: str,
        quality_signals: dict[str, float | int | bool],
    ) -> StageQualityAssessment:
        text = (artifact_text or "").lower()
        generic_hits = sum(1 for p in GENERIC_PHRASES if p in text)
        summary_len = int(quality_signals.get("summary_len", 0))
        details_count = int(quality_signals.get("details_count", 0))
        actions_count = int(quality_signals.get("actions_count", 0))
        methods_count = int(quality_signals.get("methods_count", 0))
        stats_count = int(quality_signals.get("stats_count", 0))
        writing_count = int(quality_signals.get("writing_count", 0))
        has_paper_terms = bool(re.search(r"phactor|reaction|chatgpt|chemical|assay", text))

        missing: list[MissingDimension] = []
        if not has_paper_terms:
            missing.append(MissingDimension.SPECIFICITY)
        if summary_len < 120:
            missing.append(MissingDimension.GROUNDING)
        if details_count < 3:
            missing.append(MissingDimension.EDITORIAL_USEFULNESS)
        if actions_count < 3:
            missing.append(MissingDimension.ACTIONABILITY)
        if stage_name == "methods" and (methods_count == 0 or stats_count == 0):
            missing.append(MissingDimension.REVIEWER_USEFULNESS)
        if stage_name in {"writing", "editor"} and writing_count == 0:
            missing.append(MissingDimension.EDITORIAL_USEFULNESS)

        score = 100.0
        score -= generic_hits * 10.0
        score -= 20.0 if summary_len < 120 else 0.0
        score -= 15.0 if details_count < 3 else 0.0
        score -= 15.0 if actions_count < 3 else 0.0
        if stage_name == "methods" and (methods_count == 0 or stats_count == 0):
            score -= 20.0
        score = max(0.0, min(100.0, score))

        retry = score < 65.0 or bool(missing)
        return StageQualityAssessment(
            decision=DecisionLabel.RETRY if retry else DecisionLabel.ACCEPT,
            quality_score=score,
            specificity_score=80.0 if has_paper_terms else 35.0,
            grounding_score=75.0 if summary_len >= 120 else 40.0,
            actionability_score=80.0 if actions_count >= 3 else 45.0,
            genericity_flag=generic_hits >= 2,
            missing_dimensions=missing,
            retry_recommended=retry,
            retry_reason="; ".join([m.value for m in missing]) if missing else "",
            rationale="deterministic quality gate",
            confidence=0.8,
        )

    def evaluate_stage_output(
        self,
        stage_name: str,
        artifact_text: str,
        quality_signals: dict[str, float | int | bool],
        timeout_seconds: int,
    ) -> StageQualityAssessment:
        det = self._deterministic_stage_assessment(stage_name, artifact_text, quality_signals)
        if not self.enabled:
            return det
        if not det.retry_recommended:
            return det
        try:
            payload = self._llm_json(
                system_prompt="You are a strict orchestration quality controller. Return JSON only.",
                user_prompt=(
                    "Assess if this stage output should retry. "
                    "Return JSON keys: decision, quality_score, specificity_score, grounding_score, actionability_score, "
                    "genericity_flag, missing_dimensions, retry_recommended, retry_reason, rationale, confidence.\n"
                    f"stage={stage_name}\n"
                    f"quality_signals={quality_signals}\n"
                    f"artifact_excerpt={artifact_text[:3500]}"
                ),
                timeout_seconds=timeout_seconds,
            )
            return StageQualityAssessment.model_validate(payload)
        except Exception:
            if self.fail_open:
                return det
            raise

    def request_retry_decision(
        self,
        assessment: StageQualityAssessment,
        runtime: OrchestratorRuntimeState,
        stage_retries_used: int,
    ) -> RetryDecision:
        can = runtime.can_retry(stage_retries_used)
        should_retry = bool(assessment.retry_recommended and can)
        return RetryDecision(
            should_retry=should_retry,
            retry_instruction=(
                "Regenerate with explicit focus on: " + ", ".join([d.value for d in assessment.missing_dimensions])
                if should_retry
                else ""
            ),
            retry_reason=assessment.retry_reason,
            retries_used_stage=stage_retries_used,
            retries_used_total=runtime.total_retries_used,
            retries_remaining_stage=max(0, runtime.max_stage_retries - stage_retries_used),
            retries_remaining_total=max(0, runtime.max_total_retries - runtime.total_retries_used),
        )

    def compare_stage_versions(
        self,
        assessment_a: StageQualityAssessment,
        assessment_b: StageQualityAssessment,
    ) -> VersionComparison:
        winner = "B" if assessment_b.quality_score >= assessment_a.quality_score else "A"
        improved = (assessment_b.quality_score - assessment_a.quality_score) >= 8.0
        improvements = []
        if assessment_b.actionability_score > assessment_a.actionability_score:
            improvements.append("higher_actionability")
        if assessment_b.specificity_score > assessment_a.specificity_score:
            improvements.append("higher_specificity")
        return VersionComparison(
            winner=winner,
            materially_improved=improved,
            improvements=improvements,
            rationale="deterministic delta comparison",
            confidence=0.8,
        )

    def evaluate_distinctness(self, outputs: dict[str, str], timeout_seconds: int) -> DistinctnessAssessment:
        keys = sorted(outputs.keys())
        norms = {k: set(re.findall(r"[a-z]{4,}", outputs[k].lower())) for k in keys}
        overlaps = []
        for i, a in enumerate(keys):
            for b in keys[i + 1 :]:
                sa, sb = norms[a], norms[b]
                if not sa or not sb:
                    continue
                j = len(sa & sb) / max(1, len(sa | sb))
                overlaps.append((a, b, j))
        max_overlap = max((x[2] for x in overlaps), default=0.0)
        issues = [f"{a}~{b}:{j:.2f}" for a, b, j in overlaps if j > 0.75]
        assessment = DistinctnessAssessment(
            distinct=max_overlap < 0.78,
            overlap_score=max_overlap,
            overlap_issues=issues,
            recommendations=["Increase profile-specific constraints where overlap is high."] if issues else [],
            confidence=0.75,
        )
        if not self.enabled:
            return assessment
        if assessment.distinct:
            return assessment
        try:
            payload = self._llm_json(
                system_prompt="You are a strict orchestrator distinctness evaluator. JSON only.",
                user_prompt=(
                    "Return JSON keys: distinct, overlap_score, overlap_issues, recommendations, confidence.\n"
                    f"deterministic_overlap={issues}\n"
                    f"summaries={{k: v[:1500] for k,v in outputs.items()}}"
                ),
                timeout_seconds=timeout_seconds,
            )
            return DistinctnessAssessment.model_validate(payload)
        except Exception:
            if self.fail_open:
                return assessment
            raise

    def final_synthesis_quality_check(self, synthesis_json: dict[str, Any], timeout_seconds: int) -> FinalSynthesisAssessment:
        required = ["consolidated_strengths", "consolidated_weaknesses", "priority_actions", "revision_plan"]
        missing = [r for r in required if not synthesis_json.get(r)]
        md: list[MissingDimension] = []
        if missing:
            md.append(MissingDimension.SYNTHESIS_VALUE)
        if not any("offline" in str(x).lower() for x in synthesis_json.get("confidence_notes", [])):
            md.append(MissingDimension.GROUNDING)
        base = FinalSynthesisAssessment(
            grounded=MissingDimension.GROUNDING not in md,
            adds_value_over_concat=MissingDimension.SYNTHESIS_VALUE not in md,
            includes_revision_priorities=bool(synthesis_json.get("priority_actions")),
            states_offline_limits=any("offline" in str(x).lower() for x in synthesis_json.get("confidence_notes", [])),
            missing_dimensions=md,
            recommendations=["Expand prioritized actions and offline boundary note."] if md else [],
            confidence=0.8,
        )
        if not self.enabled:
            return base
        return base

