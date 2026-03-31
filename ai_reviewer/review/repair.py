from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import ValidationError

from ai_reviewer.models.base import ChatRequest, Provider, ProviderError
from ai_reviewer.review.schema import ReviewSchema


class ParseFailureType(str, Enum):
    NON_JSON_OUTPUT = "non_json_output"
    PARTIAL_JSON = "partial_json"
    TRUNCATED_JSON = "truncated_json"
    WRONG_FIELD_NAMES = "wrong_field_names"
    WRONG_FIELD_TYPES = "wrong_field_types"
    NESTED_STRUCTURE_ERRORS = "nested_structure_errors"
    EXTRA_COMMENTARY = "extra_commentary"
    REFUSAL_OR_EMPTY = "refusal_or_empty"
    MALFORMED_UNICODE = "malformed_unicode"
    UNKNOWN = "unknown"


@dataclass
class ParseOutcome:
    parsed: ReviewSchema | None
    raw_json: dict[str, Any] | None
    repaired_text: str | None
    warnings: list[str]
    parse_failures: int
    failure_types: list[ParseFailureType] = field(default_factory=list)
    used_repair_model: str | None = None
    repair_stage: str = "initial"


def extract_json_candidate(text: str) -> str | None:
    block = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if block:
        return block.group(1)

    fenced = re.search(r"```\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return fenced.group(1)

    braces = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if braces:
        return braces.group(0)

    return None


def classify_failure(text: str, exc: Exception | None = None) -> ParseFailureType:
    lowered = text.strip().lower()
    if not lowered:
        return ParseFailureType.REFUSAL_OR_EMPTY
    if "i can't" in lowered or "cannot comply" in lowered or "refuse" in lowered:
        return ParseFailureType.REFUSAL_OR_EMPTY
    if "```" in text and "{" in text and "}" in text:
        return ParseFailureType.EXTRA_COMMENTARY
    if "{" in text and "}" not in text:
        return ParseFailureType.TRUNCATED_JSON
    if "{" in text and "}" in text:
        if isinstance(exc, ValidationError):
            msg = str(exc).lower()
            if "field required" in msg:
                return ParseFailureType.WRONG_FIELD_NAMES
            if "input should be" in msg or "type=" in msg:
                return ParseFailureType.WRONG_FIELD_TYPES
            return ParseFailureType.NESTED_STRUCTURE_ERRORS
        if isinstance(exc, json.JSONDecodeError):
            return ParseFailureType.PARTIAL_JSON
        return ParseFailureType.PARTIAL_JSON
    if "\\u" in text or "\\x" in text:
        return ParseFailureType.MALFORMED_UNICODE
    return ParseFailureType.NON_JSON_OUTPUT


def _try_validate(payload: dict[str, Any]) -> ReviewSchema:
    return ReviewSchema.model_validate(payload)


def _loose_json_repair(raw: str) -> str:
    repaired = raw.strip()
    repaired = repaired.replace("\u201c", '"').replace("\u201d", '"')
    repaired = repaired.replace("\u2018", "'").replace("\u2019", "'")
    repaired = re.sub(r"[\x00-\x1f]", "", repaired)
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    return repaired


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    # Common local-model pattern: {"review": {...}}
    if isinstance(payload.get("review"), dict):
        inner = dict(payload["review"])
        for k, v in payload.items():
            if k != "review" and k not in inner:
                inner[k] = v
        payload = inner

    # Field aliases from non-schema outputs.
    alias_map = {
        "overall_assessment": "summary",
        "strengths": "major_strengths",
        "weaknesses": "major_weaknesses",
        "novelty_issues": "novelty_concerns",
        "methodological_issues": "methodological_concerns",
        "statistical_issues": "statistical_concerns",
        "writing_issues": "writing_organization_concerns",
        "figure_issues": "figure_table_concerns",
        "citation_issues": "citation_reference_concerns",
        "reproducibility_issues": "reproducibility_concerns",
        "suggested_experiments": "suggested_experiments_analyses",
        "comments": "detailed_reviewer_comments",
        "detailed_comments": "detailed_reviewer_comments",
        "section_comments": "section_specific_comments",
        "action_items": "extracted_action_items",
        "specific_suggestions": "extracted_action_items",
    }
    for src, dst in alias_map.items():
        if src in payload and dst not in payload:
            payload[dst] = payload[src]

    if isinstance(payload.get("recommendation"), str):
        rec = payload["recommendation"].strip().lower()
        decision = "revise"
        if "reject" in rec:
            decision = "reject"
        elif "accept" in rec and "revise" not in rec:
            decision = "accept"
        payload["recommendation"] = {"decision": decision, "rationale": payload["recommendation"]}
    if isinstance(payload.get("decision"), str) and "recommendation" not in payload:
        payload["recommendation"] = {"decision": payload["decision"], "rationale": payload.get("decision_rationale", "")}

    if isinstance(payload.get("extracted_action_items"), list):
        norm_items = []
        for item in payload["extracted_action_items"]:
            if isinstance(item, dict):
                norm_items.append(
                    {
                        "action": item.get("action") or item.get("item") or "",
                        "priority": item.get("priority") or "medium",
                        "owner": item.get("owner") or "author",
                    }
                )
            elif isinstance(item, str):
                norm_items.append({"action": item, "priority": "medium", "owner": "author"})
        payload["extracted_action_items"] = norm_items

    if isinstance(payload.get("detailed_reviewer_comments"), dict):
        payload["detailed_reviewer_comments"] = [
            f"[{k}] {v}" for k, v in payload["detailed_reviewer_comments"].items() if str(v).strip()
        ]
    if isinstance(payload.get("detailed_reviewer_comments"), list):
        norm_comments = []
        for item in payload["detailed_reviewer_comments"]:
            if isinstance(item, str):
                norm_comments.append(item)
            elif isinstance(item, dict):
                section = item.get("section") or "unknown"
                comment = item.get("comment") or item.get("text") or ""
                if comment:
                    norm_comments.append(f"[{section}] {comment}")
        payload["detailed_reviewer_comments"] = norm_comments

    # Promote free-form title into document metadata if available.
    if "title" in payload:
        payload.setdefault("document_metadata", {})
        if isinstance(payload["document_metadata"], dict) and "title" not in payload["document_metadata"]:
            payload["document_metadata"]["title"] = str(payload["title"])

    if isinstance(payload.get("section_specific_comments"), dict):
        payload["section_specific_comments"] = [
            {"section": k, "comment": str(v), "severity": "medium"}
            for k, v in payload["section_specific_comments"].items()
            if str(v).strip()
        ]
    if isinstance(payload.get("section_specific_comments"), list):
        norm_sections = []
        for item in payload["section_specific_comments"]:
            if isinstance(item, dict):
                norm_sections.append(
                    {
                        "section": item.get("section") or item.get("title") or "unknown",
                        "comment": item.get("comment") or item.get("text") or "",
                        "severity": item.get("severity") or "medium",
                        "evidence_source": item.get("evidence_source") or "manuscript_internal",
                        "manuscript_quote": item.get("manuscript_quote"),
                    }
                )
            elif isinstance(item, str):
                norm_sections.append({"section": "unknown", "comment": item, "severity": "medium", "evidence_source": "manuscript_internal", "manuscript_quote": None})
        payload["section_specific_comments"] = norm_sections

    if isinstance(payload.get("grounded_detailed_comments"), list):
        norm_grounded = []
        for item in payload["grounded_detailed_comments"]:
            if isinstance(item, dict):
                norm_grounded.append({
                    "comment": item.get("comment") or item.get("text") or "",
                    "evidence_source": item.get("evidence_source") or "manuscript_internal",
                    "manuscript_quote": item.get("manuscript_quote"),
                    "severity": item.get("severity") or "medium",
                })
            elif isinstance(item, str):
                norm_grounded.append({"comment": item, "evidence_source": "manuscript_internal", "manuscript_quote": None, "severity": "medium"})
        payload["grounded_detailed_comments"] = norm_grounded

    # Minimal defaults so strict validation can still succeed when content is mostly present.
    payload.setdefault("document_metadata", {})
    payload.setdefault("summary", "")
    payload.setdefault("major_strengths", [])
    payload.setdefault("major_weaknesses", [])
    payload.setdefault("novelty_concerns", [])
    payload.setdefault("methodological_concerns", [])
    payload.setdefault("statistical_concerns", [])
    payload.setdefault("writing_organization_concerns", [])
    payload.setdefault("figure_table_concerns", [])
    payload.setdefault("citation_reference_concerns", [])
    payload.setdefault("reproducibility_concerns", [])
    payload.setdefault("suggested_experiments_analyses", [])
    payload.setdefault("recommendation", {"decision": "revise", "rationale": ""})
    payload.setdefault("confidence", 0.5)
    payload.setdefault("detailed_reviewer_comments", [])
    payload.setdefault("grounded_detailed_comments", [])
    payload.setdefault("section_specific_comments", [])
    payload.setdefault("extracted_action_items", [])
    payload.setdefault(
        "model_debug_metadata",
        {
            "provider": "ollama",
            "model": "unknown",
            "temperature": 0.0,
            "retries_used": 0,
            "parse_failures": 0,
            "total_duration": None,
            "prompt_eval_count": None,
            "eval_count": None,
        },
    )
    return payload


def _heuristic_from_prose(text: str) -> dict[str, Any] | None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None

    lowered = text.lower()
    if (
        "overall summary" not in lowered
        and "overall purpose" not in lowered
        and "overall impressions" not in lowered
        and "key observations" not in lowered
        and "specific issues" not in lowered
        and "potential areas for improvement" not in lowered
    ):
        return None

    summary = ""
    strengths: list[str] = []
    weaknesses: list[str] = []
    comments: list[str] = []

    section = "summary"
    def _norm_heading(value: str) -> str:
        h = value.lower().strip("* ").strip(":").strip()
        h = re.sub(r"^[ivxlcdm]+\.\s*", "", h)
        h = re.sub(r"^\d+[\.\)]\s*", "", h)
        return h.strip()

    for ln in lines:
        low = ln.lower().strip("* ").strip()
        heading = _norm_heading(low)
        if heading.startswith("overall summary") or heading.startswith("overall purpose") or heading.startswith("overall impressions"):
            section = "summary"
            continue
        if (
            heading.startswith("key observations")
            or re.match(r"^strengths", heading)
            or heading == "strengths"
        ):
            section = "strengths"
            continue
        if (
            heading.startswith("potential areas for improvement")
            or heading.startswith("areas for improvement")
            or re.match(r"^weaknesses", heading)
            or heading == "weaknesses"
            or heading.startswith("suggestions for improvement")
            or "specific issues" in heading
        ):
            section = "weaknesses"
            continue
        if low.startswith("in conclusion"):
            continue

        if section == "summary":
            if ln.startswith("*") or ln.startswith("-"):
                continue
            if len(summary) < 1400:
                summary = (summary + " " + ln.strip("* ")).strip()
        elif section == "strengths":
            if ln.startswith("*") or ln.startswith("-"):
                val = ln.lstrip("*- ").strip()
                if val:
                    strengths.append(val)
        elif section == "weaknesses":
            if ln.startswith("*") or ln.startswith("-"):
                val = ln.lstrip("*- ").strip()
                if val:
                    weaknesses.append(val)

    if not summary:
        summary = " ".join(lines[:6])[:1200]
    comments = (strengths[:2] + weaknesses[:3])[:5]
    if len(summary) < 80 and not strengths and not weaknesses:
        return None

    payload: dict[str, Any] = {
        "document_metadata": {},
        "summary": summary,
        "major_strengths": strengths[:8],
        "major_weaknesses": weaknesses[:8],
        "novelty_concerns": [],
        "methodological_concerns": [],
        "statistical_concerns": [],
        "writing_organization_concerns": [],
        "figure_table_concerns": [],
        "citation_reference_concerns": [],
        "reproducibility_concerns": [],
        "suggested_experiments_analyses": [],
        "recommendation": {"decision": "revise", "rationale": "Recovered from prose-form model output."},
        "confidence": 0.55,
        "detailed_reviewer_comments": comments,
        "section_specific_comments": [],
        "extracted_action_items": [{"action": w, "priority": "medium", "owner": "author"} for w in weaknesses[:5]],
        "model_debug_metadata": {
            "provider": "ollama",
            "model": "unknown",
            "temperature": 0.0,
            "retries_used": 0,
            "parse_failures": 0,
            "total_duration": None,
            "prompt_eval_count": None,
            "eval_count": None,
        },
    }
    return payload


def parse_and_repair(
    text: str,
    provider: Provider,
    repair_models: list[str],
    timeout_seconds: int,
    logger: logging.Logger,
    primary_model: str = "unknown",
    allow_self_repair: bool = True,
) -> ParseOutcome:
    warnings: list[str] = []
    parse_failures = 0
    failure_types: list[ParseFailureType] = []

    candidate = extract_json_candidate(text)
    if not candidate:
        parse_failures += 1
        failure_types.append(classify_failure(text))
        warnings.append("No JSON block found in model output.")
        candidate = text

    try:
        payload = _normalize_payload(json.loads(candidate))
        parsed = _try_validate(payload)
        return ParseOutcome(parsed, payload, None, warnings, parse_failures, failure_types, repair_stage="initial")
    except (json.JSONDecodeError, ValidationError) as exc:
        parse_failures += 1
        failure_types.append(classify_failure(candidate, exc))
        warnings.append(f"Initial parse failed: {exc}")
        logger.debug("initial_parse_failed error=%s", exc)

    repaired_candidate = _loose_json_repair(candidate)
    try:
        payload = _normalize_payload(json.loads(repaired_candidate))
        parsed = _try_validate(payload)
        warnings.append("Recovered using local JSON cleanup repair.")
        return ParseOutcome(parsed, payload, repaired_candidate, warnings, parse_failures, failure_types, repair_stage="local_cleanup")
    except (json.JSONDecodeError, ValidationError) as exc:
        parse_failures += 1
        failure_types.append(classify_failure(repaired_candidate, exc))
        warnings.append(f"Local cleanup repair failed: {exc}")
        logger.debug("loose_repair_failed error=%s", exc)

    heuristic = _heuristic_from_prose(text)
    if heuristic is not None:
        try:
            payload = _normalize_payload(heuristic)
            parsed = _try_validate(payload)
            warnings.append("Recovered using heuristic prose-to-schema extraction.")
            return ParseOutcome(parsed, payload, None, warnings, parse_failures, failure_types, repair_stage="heuristic_extraction")
        except ValidationError as exc:
            parse_failures += 1
            failure_types.append(classify_failure(text, exc))
            warnings.append(f"Heuristic prose extraction failed: {exc}")
            logger.debug("heuristic_extraction_failed error=%s", exc)

    candidate_models: list[str] = []
    if allow_self_repair:
        candidate_models.append(primary_model)
    candidate_models.extend([m for m in repair_models if m != primary_model])

    repair_prompt = (
        "Repair the following output into strict JSON that conforms to the required review schema. "
        "Return only valid JSON with no markdown and no explanation.\n\n"
        f"BROKEN_OUTPUT:\n{candidate}\n"
    )

    for model in candidate_models:
        try:
            logger.debug("repair_attempt model=%s", model)
            repair_resp = provider.chat(
                ChatRequest(
                    model=model,
                    system_prompt="You are a JSON schema repair engine. Return only strict JSON.",
                    user_prompt=repair_prompt,
                    temperature=0.0,
                    max_tokens=2200,
                    timeout_seconds=timeout_seconds,
                )
            )
            repaired = extract_json_candidate(repair_resp.content) or repair_resp.content
            payload = _normalize_payload(json.loads(repaired))
            parsed = _try_validate(payload)
            warnings.append(f"Recovered with repair model {model}.")
            return ParseOutcome(
                parsed,
                payload,
                repaired,
                warnings,
                parse_failures,
                failure_types,
                used_repair_model=model,
                repair_stage="model_repair",
            )
        except (ProviderError, json.JSONDecodeError, ValidationError) as exc:
            parse_failures += 1
            failure_types.append(classify_failure(candidate, exc))
            warnings.append(f"Repair model {model} failed: {exc}")
            logger.debug("repair_model_failed model=%s error=%s", model, exc)

    warnings.append("Falling back to degraded parser with explicit warning metadata.")
    minimal = {
        "document_metadata": {
            "warning": "schema_recovery_failed",
            "parse_failure_types": ",".join(ft.value for ft in failure_types) or "unknown",
        },
        "summary": text[:1500],
        "major_strengths": [],
        "major_weaknesses": ["Structured output could not be fully recovered."],
        "novelty_concerns": [],
        "methodological_concerns": [],
        "statistical_concerns": [],
        "writing_organization_concerns": [],
        "figure_table_concerns": [],
        "citation_reference_concerns": [],
        "reproducibility_concerns": [],
        "suggested_experiments_analyses": [],
        "recommendation": {"decision": "revise", "rationale": "Output format recovery failed."},
        "confidence": 0.2,
        "detailed_reviewer_comments": ["Inspect raw_model_response.txt for details."],
        "section_specific_comments": [],
        "extracted_action_items": [],
        "model_debug_metadata": {
            "provider": "ollama",
            "model": "unknown",
            "temperature": 0.0,
            "retries_used": 0,
            "parse_failures": parse_failures,
            "total_duration": None,
            "prompt_eval_count": None,
            "eval_count": None,
        },
    }
    parsed = ReviewSchema.model_validate(minimal)
    return ParseOutcome(
        parsed,
        minimal,
        repaired_candidate,
        warnings,
        parse_failures,
        failure_types,
        repair_stage="degraded",
    )
