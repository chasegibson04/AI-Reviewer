from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re

from ai_reviewer.models.base import ChatRequest, Provider
from ai_reviewer.review.repair import extract_json_candidate
from ai_reviewer.review.style_clarity_pass import deterministic_style_rewrite, style_rewrite_usefulness_check
from ai_reviewer.tools.docx_tools import extract_existing_docx_comments


RESPONSE_TEXT_FIX = "text_fix"
RESPONSE_STRATEGY = "response_strategy"
RESPONSE_NEEDS_CLARIFICATION = "needs_clarification"
RESPONSE_ALREADY_ADDRESSED = "already_addressed"


def _normalize(text: str) -> str:
    low = str(text or "").lower()
    low = re.sub(r"[“”\"'`]", "", low)
    low = re.sub(r"[\W_]+", " ", low)
    return re.sub(r"\s+", " ", low).strip()


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9][a-z0-9\-]+", _normalize(text)) if len(t) >= 3}


def _overlap(a: str, b: str) -> float:
    ta = _tokens(a)
    tb = _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def _select_responder_model(provider: Provider | None, fallback_model: str | None) -> tuple[str | None, bool]:
    if provider is None:
        return None, False
    try:
        models = set(provider.list_models())
    except Exception:
        models = set()
    if "gemma4:31b" in models:
        return "gemma4:31b", True
    return fallback_model, False


def _heuristic_comment_response(comment_text: str, anchor_text: str, paragraph_text: str, section: str) -> dict[str, Any]:
    comment = str(comment_text or "").strip()
    anchor = str(anchor_text or "").strip()
    paragraph = str(paragraph_text or "").strip()
    low = comment.lower()
    if len(comment.split()) <= 2 or comment in {"?", "??"}:
        return {
            "response_type": RESPONSE_NEEDS_CLARIFICATION,
            "proposed_response": "Comment is too brief; request a specific target sentence and expected change.",
            "proposed_rewrite": None,
            "confidence": "high",
        }
    if any(k in low for k in ["unclear", "vague", "clarify"]) and _overlap(comment, anchor or paragraph) < 0.05:
        return {
            "response_type": RESPONSE_NEEDS_CLARIFICATION,
            "proposed_response": "Ask the reviewer to identify the exact phrase that needs clarification.",
            "proposed_rewrite": None,
            "confidence": "medium",
        }
    if "citation" in low or "reference" in low:
        if re.search(r"\[[0-9,\-\u2013 ]+\]|\([12][0-9]{3}[a-z]?\)", anchor or paragraph):
            return {
                "response_type": RESPONSE_ALREADY_ADDRESSED,
                "proposed_response": "Sentence already includes citation-style support; verify citation relevance and keep.",
                "proposed_rewrite": None,
                "confidence": "medium",
            }
        return {
            "response_type": RESPONSE_STRATEGY,
            "proposed_response": "Add a direct citation at the claim sentence and narrow wording to what that source supports.",
            "proposed_rewrite": None,
            "confidence": "high",
        }
    def _pick_rewrite_target(anchor_value: str, paragraph_value: str) -> str:
        source = (anchor_value or paragraph_value or "").strip()
        if not source:
            return ""
        source = re.sub(r"\s+", " ", source).strip()
        # Treat citation-boundary uppercase starts as sentence boundaries.
        source = re.sub(r"(?<=\])\s+(?=[A-Z])", ". ", source)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", source) if s.strip()]
        if sentences:
            for sentence in sentences:
                wc = len(sentence.split())
                if 10 <= wc <= 40:
                    return sentence
            for sentence in sentences:
                if len(sentence.split()) >= 10:
                    return " ".join(sentence.split()[:40]).strip()
            return sentences[0]
        if len(source.split()) <= 48:
            return source
        return " ".join(source.split()[:40]).strip()

    if any(k in low for k in ["overclaim", "overstate", "unsupported", "too strong", "scope"]):
        sentence = _pick_rewrite_target(anchor, paragraph)
        rewrite = deterministic_style_rewrite(sentence, "concision")
        useful, _, _ = style_rewrite_usefulness_check(sentence, rewrite, "concision")
        if useful:
            return {
                "response_type": RESPONSE_TEXT_FIX,
                "proposed_response": "Qualify certainty and tie the claim to tested evidence.",
                "proposed_rewrite": rewrite,
                "confidence": "medium",
                "rewrite_source_text": sentence,
                "rewrite_issue_kind": "concision",
            }
        return {
            "response_type": RESPONSE_STRATEGY,
            "proposed_response": "Narrow claim language to tested conditions and explicit outcomes.",
            "proposed_rewrite": None,
            "confidence": "medium",
        }
    if any(k in low for k in ["split", "flow", "awkward", "wording", "readability", "definition", "transition", "grammar", "style"]):
        sentence = _pick_rewrite_target(anchor, paragraph)
        issue = "overloaded_sentence" if "split" in low else "readability"
        if issue == "overloaded_sentence":
            split_source = re.sub(r"(?<=\])\s+(?=[A-Z])", ". ", sentence)
            parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", split_source) if s.strip()]
            if len(parts) >= 2:
                sentence = max(parts, key=lambda s: len(s.split()))
        rewrite = deterministic_style_rewrite(sentence, issue)
        useful, _, _ = style_rewrite_usefulness_check(sentence, rewrite, issue)
        if useful:
            return {
                "response_type": RESPONSE_TEXT_FIX,
                "proposed_response": "Apply a local line edit to improve readability while preserving meaning.",
                "proposed_rewrite": rewrite,
                "confidence": "high",
                "rewrite_source_text": sentence,
                "rewrite_issue_kind": issue,
            }
        return {
            "response_type": RESPONSE_STRATEGY,
            "proposed_response": "Revise sentence locally: simplify clause order and keep one main claim per sentence.",
            "proposed_rewrite": None,
            "confidence": "medium",
        }
    if _overlap(comment, anchor or paragraph) < 0.04:
        return {
            "response_type": RESPONSE_NEEDS_CLARIFICATION,
            "proposed_response": "Comment does not clearly map to local text; request a precise anchor.",
            "proposed_rewrite": None,
            "confidence": "low",
        }
    return {
        "response_type": RESPONSE_STRATEGY,
        "proposed_response": f"Address the comment in {section or 'this section'} with a sentence-local revision and explicit rationale.",
        "proposed_rewrite": None,
        "confidence": "low",
    }


def _llm_comment_response(
    provider: Provider,
    model: str,
    comment_text: str,
    anchor_text: str,
    paragraph_text: str,
    section: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    payload = {
        "comment_text": comment_text,
        "anchor_text": anchor_text,
        "paragraph_text": paragraph_text[:550],
        "section": section,
        "allowed_response_types": [
            RESPONSE_TEXT_FIX,
            RESPONSE_STRATEGY,
            RESPONSE_NEEDS_CLARIFICATION,
            RESPONSE_ALREADY_ADDRESSED,
        ],
    }
    system_prompt = (
        "You are an author-side scientific editor responding to reviewer comments. "
        "Return JSON only with keys: response_type, proposed_response, proposed_rewrite, confidence. "
        "Use concise practical actions. Avoid defensive language."
    )
    resp = provider.chat(
        ChatRequest(
            model=model,
            system_prompt=system_prompt,
            user_prompt=json.dumps(payload, ensure_ascii=False),
            temperature=0.1,
            max_tokens=360,
            timeout_seconds=timeout_seconds,
            metadata={"purpose": "existing_comment_responder"},
        )
    )
    parsed = json.loads(extract_json_candidate(resp.content) or resp.content)
    response_type = str(parsed.get("response_type", "")).strip().lower()
    if response_type not in {
        RESPONSE_TEXT_FIX,
        RESPONSE_STRATEGY,
        RESPONSE_NEEDS_CLARIFICATION,
        RESPONSE_ALREADY_ADDRESSED,
    }:
        response_type = RESPONSE_STRATEGY
    rewrite_raw = parsed.get("proposed_rewrite")
    rewrite_value = str(rewrite_raw).strip() if isinstance(rewrite_raw, str) else None
    if rewrite_value and rewrite_value.lower() == "none":
        rewrite_value = None
    return {
        "response_type": response_type,
        "proposed_response": str(parsed.get("proposed_response", "")).strip(),
        "proposed_rewrite": rewrite_value,
        "confidence": str(parsed.get("confidence", "")).strip().lower() or "medium",
    }


def run_existing_comment_responder(
    source_docx: Path,
    paragraphs: list[str],
    section_by_idx: dict[int, str],
    provider: Provider | None,
    model: str | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    existing = extract_existing_docx_comments(source_docx)
    selected_model, gemma_used = _select_responder_model(provider, model)
    llm_available = provider is not None and selected_model is not None
    llm_enabled = llm_available
    llm_fail_fast_triggered = False
    fallback_used_any = not llm_available
    responses: list[dict[str, Any]] = []
    type_counts = {
        RESPONSE_TEXT_FIX: 0,
        RESPONSE_STRATEGY: 0,
        RESPONSE_NEEDS_CLARIFICATION: 0,
        RESPONSE_ALREADY_ADDRESSED: 0,
    }

    for row in existing:
        pidx = row.get("paragraph_index")
        para = ""
        section = "body"
        if isinstance(pidx, int) and 0 <= pidx < len(paragraphs):
            para = paragraphs[pidx]
            section = section_by_idx.get(pidx, "body")
        comment_text = str(row.get("comment_text", "")).strip()
        anchor = str(row.get("anchor_text", "")).strip()
        used_fallback = not llm_enabled
        try:
            if llm_enabled:
                resp = _llm_comment_response(
                    provider=provider,  # type: ignore[arg-type]
                    model=selected_model,  # type: ignore[arg-type]
                    comment_text=comment_text,
                    anchor_text=anchor,
                    paragraph_text=para,
                    section=section,
                    timeout_seconds=timeout_seconds,
                )
                used_fallback = False
            else:
                resp = _heuristic_comment_response(comment_text, anchor, para, section)
        except Exception:
            resp = _heuristic_comment_response(comment_text, anchor, para, section)
            used_fallback = True
            fallback_used_any = True
            llm_enabled = False
            llm_fail_fast_triggered = True

        response_type = str(resp.get("response_type", RESPONSE_STRATEGY))
        raw_rewrite = resp.get("proposed_rewrite")
        proposed_rewrite = str(raw_rewrite).strip() if isinstance(raw_rewrite, str) else None
        if proposed_rewrite and proposed_rewrite.lower() == "none":
            proposed_rewrite = None
        if response_type == RESPONSE_TEXT_FIX and proposed_rewrite:
            original = str(resp.get("rewrite_source_text", "")).strip() or anchor or para
            issue_kind = str(resp.get("rewrite_issue_kind", "")).strip() or "readability"
            useful, reason, _ = style_rewrite_usefulness_check(original, proposed_rewrite, issue_kind)
            if useful and len(proposed_rewrite.split()) > 55:
                useful = False
                reason = "rewrite_too_long"
            if not useful:
                response_type = RESPONSE_STRATEGY
                proposed_rewrite = None
                existing_response = str(resp.get("proposed_response", "")).strip()
                if existing_response:
                    resp["proposed_response"] = existing_response
                else:
                    resp["proposed_response"] = f"Rewrite candidate suppressed ({reason}); apply a targeted local revision instead."

        type_counts[response_type] = type_counts.get(response_type, 0) + 1
        responses.append(
            {
                "comment_id": row.get("comment_id"),
                "author": row.get("author"),
                "comment_text": comment_text,
                "paragraph_index": pidx,
                "section": section,
                "anchor_text": anchor,
                "proposed_response": str(resp.get("proposed_response", "")).strip(),
                "proposed_rewrite": proposed_rewrite,
                "response_type": response_type,
                "confidence": str(resp.get("confidence", "medium")).strip().lower() or "medium",
                "model_used": selected_model if llm_available and not used_fallback else None,
                "fallback_used": used_fallback,
            }
        )

    return {
        "source_docx": str(source_docx),
        "model": {
            "selected_model": selected_model,
            "gemma4_31b_used": bool(gemma_used and llm_available),
            "fallback_used": fallback_used_any or any(bool(x.get("fallback_used")) for x in responses),
            "fail_fast_fallback_triggered": llm_fail_fast_triggered,
        },
        "summary": {
            "existing_comments_detected": len(existing),
            "responses_generated": len(responses),
            "response_type_counts": type_counts,
        },
        "responses": responses,
    }


def render_comment_response_manifest_markdown(manifest: dict[str, Any]) -> str:
    summary = manifest.get("summary", {})
    rows = manifest.get("responses", [])
    lines = [
        "# Existing Comment Response Manifest",
        "",
        f"- Existing comments detected: {summary.get('existing_comments_detected', 0)}",
        f"- Responses generated: {summary.get('responses_generated', 0)}",
        "",
        "| Comment ID | Section | Response Type | Confidence | Proposed Response |",
        "|---|---|---|---|---|",
    ]
    if isinstance(rows, list):
        for row in rows:
            cid = str(row.get("comment_id", "")).strip() or "-"
            section = str(row.get("section", "")).strip() or "body"
            rtype = str(row.get("response_type", "")).strip() or RESPONSE_STRATEGY
            conf = str(row.get("confidence", "")).strip() or "medium"
            response = str(row.get("proposed_response", "")).strip().replace("\n", " ")
            response = re.sub(r"\s+", " ", response)[:220]
            lines.append(f"| {cid} | {section} | {rtype} | {conf} | {response} |")
            rewrite = str(row.get("proposed_rewrite", "")).strip()
            if rewrite and rewrite.lower() != "none":
                lines.append(f"|  |  | proposed_rewrite |  | `{rewrite[:220]}` |")
    return "\n".join(lines).strip() + "\n"
