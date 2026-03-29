from __future__ import annotations

import re
from collections import Counter
from typing import Any

from ai_reviewer.review.schema import ReviewSchema


_GENERIC_PATTERNS = [
    r"^\s*clarify\b",
    r"^\s*improve\b",
    r"^\s*discuss\b",
    r"^\s*elaborate\b",
    r"^\s*provide more\b",
    r"^\s*add more\b",
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _looks_generic(text: str) -> bool:
    t = text.strip()
    if len(t) < 28:
        return True
    low = t.lower()
    if any(re.search(p, low) for p in _GENERIC_PATTERNS):
        return True
    return False


def _clip_score(raw: float) -> float:
    return max(0.0, min(5.0, round(raw, 2)))


def build_specialist_qc_summary(review: ReviewSchema) -> dict[str, Any]:
    section_names = [c.section.strip() for c in review.section_specific_comments if c.section.strip()]
    unique_sections = sorted(set(section_names))
    section_count = len(section_names)
    writing_count = len([x for x in review.writing_organization_concerns if str(x).strip()])
    rigor_count = (
        len([x for x in review.methodological_concerns if str(x).strip()])
        + len([x for x in review.statistical_concerns if str(x).strip()])
        + len([x for x in review.reproducibility_concerns if str(x).strip()])
    )
    action_count = len([x for x in review.extracted_action_items if str(x.action).strip()])
    detail_count = len([x for x in review.detailed_reviewer_comments if str(x).strip()])
    novelty_count = len([x for x in review.novelty_concerns if str(x).strip()])
    citation_count = len([x for x in review.citation_reference_concerns if str(x).strip()])

    text_items: list[str] = []
    text_items.extend([x for x in review.major_weaknesses if str(x).strip()])
    text_items.extend([x for x in review.writing_organization_concerns if str(x).strip()])
    text_items.extend([x for x in review.detailed_reviewer_comments if str(x).strip()])
    text_items.extend([x.comment for x in review.section_specific_comments if str(x.comment).strip()])
    normalized = [_norm(x) for x in text_items]
    dup_counter = Counter(normalized)
    duplicate_items = sorted([k for k, v in dup_counter.items() if v > 1 and k])
    generic_items = [x for x in text_items if _looks_generic(x)]

    section_specificity = 1.2
    section_specificity += min(2.0, section_count * 0.2)
    section_specificity += min(1.0, len(unique_sections) * 0.2)
    section_specificity -= min(1.2, len(generic_items) * 0.08)

    rigor_score = 1.0 + min(2.4, rigor_count * 0.35) + min(0.8, citation_count * 0.15) + min(0.8, novelty_count * 0.15)
    writing_score = 1.0 + min(2.8, writing_count * 0.35) + min(0.7, detail_count * 0.12)
    actionability = 1.0 + min(3.0, action_count * 0.45) + min(0.6, section_count * 0.1)
    trust = 3.5 - min(2.0, len(duplicate_items) * 0.35) - min(1.8, len(generic_items) * 0.1)

    scores = {
        "section_specificity_score": _clip_score(section_specificity),
        "rigor_score": _clip_score(rigor_score),
        "writing_score": _clip_score(writing_score),
        "actionability_score": _clip_score(actionability),
        "trustworthiness_score": _clip_score(trust),
    }
    overall = _clip_score(
        (scores["section_specificity_score"] * 0.2)
        + (scores["rigor_score"] * 0.25)
        + (scores["writing_score"] * 0.2)
        + (scores["actionability_score"] * 0.2)
        + (scores["trustworthiness_score"] * 0.15)
    )

    recommendations: list[str] = []
    if scores["section_specificity_score"] < 2.5:
        recommendations.append("Increase section-specific targeting; avoid generic body-level comments.")
    if scores["trustworthiness_score"] < 2.5:
        recommendations.append("Reduce duplicated or templated findings before emitting final report/comments.")
    if scores["actionability_score"] < 2.8:
        recommendations.append("Convert high-level concerns into concrete revision actions where safely localizable.")
    if scores["writing_score"] < 2.8:
        recommendations.append("Add more sentence-level writing/flow critiques with clear rewrite guidance.")

    return {
        "specialist_counts": {
            "sections": section_count,
            "unique_sections": unique_sections,
            "writing_findings": writing_count,
            "rigor_findings": rigor_count,
            "action_items": action_count,
            "detail_comments": detail_count,
            "citation_concerns": citation_count,
            "novelty_concerns": novelty_count,
        },
        "qc_flags": {
            "generic_item_count": len(generic_items),
            "duplicate_item_count": len(duplicate_items),
            "generic_examples": generic_items[:6],
            "duplicate_examples": duplicate_items[:6],
        },
        "category_scores_0_to_5": scores,
        "overall_score_0_to_5": overall,
        "recommendations": recommendations,
    }


def build_deep_reconciliation_summary(reconciliation_payload: dict[str, Any]) -> dict[str, Any]:
    strengths = [str(x).strip() for x in reconciliation_payload.get("consolidated_strengths", []) if str(x).strip()]
    weaknesses = [str(x).strip() for x in reconciliation_payload.get("consolidated_weaknesses", []) if str(x).strip()]
    priorities = [str(x).strip() for x in reconciliation_payload.get("priority_actions", []) if str(x).strip()]
    revisions = [str(x).strip() for x in reconciliation_payload.get("revision_plan", []) if str(x).strip()]
    confidence_notes = [str(x).strip() for x in reconciliation_payload.get("confidence_notes", []) if str(x).strip()]

    duplicates = sorted([k for k, v in Counter([_norm(x) for x in weaknesses + priorities]).items() if v > 1 and k])
    generic_weakness = [x for x in weaknesses if _looks_generic(x)]
    unresolved_risk = [x for x in confidence_notes if "offline" in x.lower() or "fallback" in x.lower() or "not verified" in x.lower()]

    quality_score = 1.2
    quality_score += min(1.0, len(strengths) * 0.1)
    quality_score += min(1.0, len(weaknesses) * 0.1)
    quality_score += min(1.0, len(priorities) * 0.1)
    quality_score += min(0.6, len(revisions) * 0.1)
    quality_score -= min(1.6, len(duplicates) * 0.4)
    quality_score -= min(1.2, len(generic_weakness) * 0.25)
    quality_score -= min(0.8, len(unresolved_risk) * 0.2)
    if len(weaknesses) < 4:
        quality_score -= 0.4
    if len(priorities) < 3:
        quality_score -= 0.3
    quality_score = _clip_score(quality_score)

    return {
        "reconciliation_qc": {
            "strength_count": len(strengths),
            "weakness_count": len(weaknesses),
            "priority_action_count": len(priorities),
            "revision_plan_count": len(revisions),
            "duplicate_cross_field_count": len(duplicates),
            "generic_weakness_count": len(generic_weakness),
            "unresolved_risk_notes": unresolved_risk[:8],
        },
        "reconciliation_quality_score_0_to_5": quality_score,
        "recommended_followups": [
            "Tighten weak/generic weaknesses into manuscript-specific findings." if generic_weakness else "No generic-weakness cleanup required.",
            "Deduplicate repeated weakness/priority statements." if duplicates else "No major duplicate cleanup required.",
        ],
    }
