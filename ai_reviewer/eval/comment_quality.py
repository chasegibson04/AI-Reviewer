from __future__ import annotations

import difflib
import re
from typing import Any


SENTENCE_LOCAL_ISSUES = {
    "style/clarity",
    "evidence/overclaim",
    "wording/precision",
    "grammar/mechanics",
}

CLAUSE_STYLE_KINDS = {
    "definition_clarity",
    "concision",
    "redundancy",
    "transition",
}

MIX_ISSUE_BUCKETS = {
    "style/clarity",
    "evidence/overclaim",
    "wording/precision",
    "grammar/mechanics",
    "structure/flow",
}

FACTUAL_CATEGORIES = {
    "public/background factual claim",
    "literature/citation-supported claim",
    "manuscript-specific result or novel assertion",
    "interpretation/inference",
    "ambiguous/mixed",
}

VERDICT_NEEDS_CITATION = "needs citation"
VERDICT_LIKELY_OVERCLAIM = "likely overclaim"
VERDICT_UNCLEAR_SUPPORT = "unclear support"
VERDICT_WORDING_STRONGER = "wording stronger than evidence"

ACTIONABLE_MARKERS = {
    "add",
    "split",
    "qualify",
    "narrow",
    "define",
    "clarify",
    "cite",
    "replace",
    "remove",
    "state",
    "tighten",
    "anchor",
}

GENERIC_MARKERS = {
    "improve clarity",
    "more detail",
    "could be improved",
    "needs work",
    "is unclear",
    "be clearer",
    "strengthen this section",
}


def _normalize(text: str) -> str:
    low = str(text or "").lower()
    low = re.sub(r"[“”\"'`]", "", low)
    low = re.sub(r"[\W_]+", " ", low)
    return re.sub(r"\s+", " ", low).strip()


def _word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", str(text or "").strip()) if w])


def _split_sentences(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    parts = re.split(r"(?<=[.!?])\s+", raw)
    out = [p.strip() for p in parts if p.strip()]
    if not out:
        return []
    return out


def _sentence_count(text: str) -> int:
    pieces = _split_sentences(text)
    if pieces:
        return len(pieces)
    return 1 if str(text or "").strip() else 0


def _clause_count(text: str) -> int:
    raw = str(text or "")
    if not raw.strip():
        return 0
    clauses = len([x for x in re.split(r"[;:]", raw) if x.strip()])
    conj = len(re.findall(r"\b(and|but|while|whereas|although|which|that)\b", raw, flags=re.IGNORECASE))
    return max(1, clauses + conj)


def _token_overlap(a: str, b: str) -> float:
    ta = {t for t in re.findall(r"[a-z0-9][a-z0-9-]+", _normalize(a)) if len(t) >= 3}
    tb = {t for t in re.findall(r"[a-z0-9][a-z0-9-]+", _normalize(b)) if len(t) >= 3}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def _extract_proposed_edit(text: str) -> str | None:
    value = str(text or "").strip()
    if not value.lower().startswith("proposed edit:"):
        return None
    rewrite = value.split(":", 1)[-1].strip()
    return rewrite or None


def evaluate_rewrite_pair(anchor: str, rewrite: str) -> dict[str, Any]:
    src = str(anchor or "").strip()
    dst = str(rewrite or "").strip()
    if not src or not dst:
        return {"no_op": False, "trivial": False, "materially_better": False, "reason": "empty"}
    nsrc = _normalize(src)
    ndst = _normalize(dst)
    if not nsrc or not ndst:
        return {"no_op": False, "trivial": False, "materially_better": False, "reason": "empty"}
    if nsrc == ndst:
        return {"no_op": True, "trivial": False, "materially_better": False, "reason": "no_change_normalized"}
    sim = difflib.SequenceMatcher(None, nsrc, ndst).ratio()
    word_delta = abs(_word_count(src) - _word_count(dst))
    if sim >= 0.97 or (sim >= 0.94 and word_delta <= 2):
        return {"no_op": False, "trivial": True, "materially_better": False, "reason": "trivial_change"}
    if _sentence_count(dst) > 2:
        return {"no_op": False, "trivial": False, "materially_better": False, "reason": "too_many_sentences"}
    overlap = _token_overlap(src, dst)
    if overlap < 0.42:
        return {"no_op": False, "trivial": False, "materially_better": False, "reason": "semantic_drift"}
    improvements = 0
    if _word_count(dst) <= max(7, int(_word_count(src) * 0.92)):
        improvements += 1
    if _clause_count(dst) < _clause_count(src):
        improvements += 1
    if _sentence_count(src) == 1 and _sentence_count(dst) == 2:
        improvements += 1
    materially_better = improvements >= 1
    return {
        "no_op": False,
        "trivial": False,
        "materially_better": materially_better,
        "reason": None if materially_better else "insufficient_improvement",
    }


def _comment_is_actionable(critique: str, suggestion: str) -> bool:
    text = f"{critique} {suggestion}".lower()
    if any(marker in text for marker in GENERIC_MARKERS):
        return False
    return any(re.search(rf"\b{re.escape(marker)}\b", text) for marker in ACTIONABLE_MARKERS)


def _comment_is_generic(critique: str, suggestion: str) -> bool:
    text = f"{critique} {suggestion}".lower()
    if not text.strip():
        return True
    return any(marker in text for marker in GENERIC_MARKERS)


def _entries_near_duplicate(a: dict[str, Any], b: dict[str, Any]) -> bool:
    pa = a.get("paragraph_index")
    pb = b.get("paragraph_index")
    if not isinstance(pa, int) or not isinstance(pb, int) or pa != pb:
        return False
    issue_a = str(a.get("issue_type", "")).strip().lower()
    issue_b = str(b.get("issue_type", "")).strip().lower()
    anchor_a = _normalize(str(a.get("anchor_text", "") or a.get("span_sentence", "")))
    anchor_b = _normalize(str(b.get("anchor_text", "") or b.get("span_sentence", "")))
    critique_a = _normalize(str(a.get("critique", "")))
    critique_b = _normalize(str(b.get("critique", "")))
    if not anchor_a or not anchor_b:
        return False
    anchor_sim = difflib.SequenceMatcher(None, anchor_a, anchor_b).ratio()
    critique_sim = difflib.SequenceMatcher(None, critique_a, critique_b).ratio() if critique_a and critique_b else 0.0
    if issue_a == issue_b and (anchor_sim >= 0.84 or critique_sim >= 0.86):
        return True
    if anchor_sim >= 0.9 and critique_sim >= 0.82:
        return True
    return False


def _is_sentence_local_comment(entry: dict[str, Any]) -> bool:
    if entry.get("from_style_pass") or entry.get("from_claim_check"):
        return True
    issue = str(entry.get("issue_type", "")).strip().lower()
    return issue in SENTENCE_LOCAL_ISSUES


def _is_clause_local_comment(entry: dict[str, Any]) -> bool:
    if entry.get("from_style_pass"):
        kind = str(entry.get("style_issue_kind", "")).strip().lower()
        return kind in CLAUSE_STYLE_KINDS
    issue = str(entry.get("issue_type", "")).strip().lower()
    return issue in {"wording/precision", "grammar/mechanics"}


def _is_high_value_claim_comment(entry: dict[str, Any]) -> bool:
    verdict = str(entry.get("claim_check_verdict", "")).strip().lower()
    if verdict in {
        VERDICT_LIKELY_OVERCLAIM,
        VERDICT_WORDING_STRONGER,
        VERDICT_NEEDS_CITATION,
    }:
        return True
    if verdict == VERDICT_UNCLEAR_SUPPORT:
        critique = str(entry.get("critique", "")).lower()
        suggestion = str(entry.get("suggested_revision", "")).lower()
        anchor = str(entry.get("anchor_text", "") or entry.get("span_sentence", ""))
        return _word_count(anchor) >= 10 and (
            "citation" in suggestion or "narrow" in suggestion or "qualify" in suggestion or "scope" in critique
        )
    return False


def compute_comment_quality_metrics(manifest: dict[str, Any]) -> dict[str, Any]:
    comments = manifest.get("comment_targets", [])
    if not isinstance(comments, list):
        comments = []

    anchor_lengths: list[int] = []
    sentence_local_total = 0
    sentence_local_excess = 0
    paragraph_wide_local_count = 0
    clause_local_total = 0
    clause_local_excess = 0

    comment_lengths: list[int] = []
    actionable_count = 0
    generic_count = 0
    verbosity_threshold_words = 36
    verbose_count = 0

    rewrite_candidates = 0
    no_op_rewrites = 0
    trivial_rewrites = 0
    materially_better_rewrites = 0

    for entry in comments:
        if not isinstance(entry, dict):
            continue
        critique = str(entry.get("critique", "")).strip()
        suggestion = str(entry.get("suggested_revision", "")).strip()
        anchor = str(entry.get("anchor_text", "") or entry.get("span_sentence", "")).strip()
        if anchor:
            anchor_lengths.append(_word_count(anchor))
        if _is_sentence_local_comment(entry):
            sentence_local_total += 1
            if _sentence_count(anchor) > 1 or _word_count(anchor) > 44:
                sentence_local_excess += 1
            paragraph_excerpt = str(entry.get("paragraph_excerpt", "")).strip()
            if paragraph_excerpt:
                norm_anchor = _normalize(anchor)
                norm_para = _normalize(paragraph_excerpt)
                para_words = _word_count(paragraph_excerpt)
                anchor_words = _word_count(anchor)
                if (
                    para_words >= 12
                    and anchor_words >= 8
                    and (
                        norm_anchor == norm_para
                        or (
                            anchor_words >= int(0.8 * para_words)
                            and _token_overlap(anchor, paragraph_excerpt) >= 0.92
                        )
                    )
                ):
                    paragraph_wide_local_count += 1
        if _is_clause_local_comment(entry):
            clause_local_total += 1
            if _sentence_count(anchor) > 1 or _word_count(anchor) > 24:
                clause_local_excess += 1
        combined_len = _word_count(f"{critique} {suggestion}")
        comment_lengths.append(combined_len)
        if combined_len > verbosity_threshold_words:
            verbose_count += 1
        if _comment_is_actionable(critique, suggestion):
            actionable_count += 1
        if _comment_is_generic(critique, suggestion):
            generic_count += 1
        rewrite = _extract_proposed_edit(suggestion)
        if rewrite:
            rewrite_candidates += 1
            outcome = evaluate_rewrite_pair(anchor, rewrite)
            if outcome["no_op"]:
                no_op_rewrites += 1
            elif outcome["trivial"]:
                trivial_rewrites += 1
            elif outcome["materially_better"]:
                materially_better_rewrites += 1

    pair_total = 0
    near_duplicate_pairs = 0
    for i, a in enumerate(comments):
        if not isinstance(a, dict):
            continue
        for b in comments[i + 1 :]:
            if not isinstance(b, dict):
                continue
            pair_total += 1
            if _entries_near_duplicate(a, b):
                near_duplicate_pairs += 1

    overlap_buckets: dict[tuple[int, str], int] = {}
    for entry in comments:
        if not isinstance(entry, dict):
            continue
        pidx = entry.get("paragraph_index")
        anchor = _normalize(str(entry.get("anchor_text", "") or entry.get("span_sentence", "")))
        if isinstance(pidx, int) and anchor:
            key = (pidx, anchor)
            overlap_buckets[key] = overlap_buckets.get(key, 0) + 1
    same_sentence_overlaps = 0
    for size in overlap_buckets.values():
        if size > 1:
            same_sentence_overlaps += size - 1

    mix_counts: dict[str, int] = {k: 0 for k in sorted(MIX_ISSUE_BUCKETS)}
    other_mix = 0
    style_surfaced = 0
    for entry in comments:
        if not isinstance(entry, dict):
            continue
        issue = str(entry.get("issue_type", "")).strip().lower()
        if issue in MIX_ISSUE_BUCKETS:
            mix_counts[issue] = mix_counts.get(issue, 0) + 1
        elif issue:
            other_mix += 1
        if bool(entry.get("from_style_pass")):
            style_surfaced += 1

    style_manifest = manifest.get("style_clarity_pass", {})
    style_summary = style_manifest.get("summary", {}) if isinstance(style_manifest, dict) else {}
    style_candidates = int(style_summary.get("candidate_count", 0) or 0)
    style_rewrites_accepted = int(style_summary.get("rewrites_proposed", 0) or 0)
    style_suppressed = int(style_summary.get("rewrites_suppressed", 0) or 0)

    claim_manifest = manifest.get("sentence_claim_check", {})
    claim_rows = claim_manifest.get("sentences", []) if isinstance(claim_manifest, dict) else []
    claim_summary = claim_manifest.get("summary", {}) if isinstance(claim_manifest, dict) else {}
    claim_projection = claim_manifest.get("comment_projection", {}) if isinstance(claim_manifest, dict) else {}
    claim_projection_summary = claim_projection.get("summary", {}) if isinstance(claim_projection, dict) else {}
    factual_claim_count = 0
    category_counts: dict[str, int] = {}
    safe_count = 0
    blocked_count = 0
    blocked_reason_counts: dict[str, int] = {}
    blocked_examples: dict[str, list[str]] = {}

    for row in claim_rows if isinstance(claim_rows, list) else []:
        if not isinstance(row, dict):
            continue
        category = str(row.get("category", "")).strip()
        if category:
            category_counts[category] = category_counts.get(category, 0) + 1
        if category in FACTUAL_CATEGORIES:
            factual_claim_count += 1
        privacy = row.get("privacy", {})
        if isinstance(privacy, dict):
            safe = bool(privacy.get("safe_for_external_search"))
            reason = str(privacy.get("reason", "")).strip() or "unknown"
            sid = str(row.get("sentence_id", "")).strip() or "unknown_sentence"
            if safe:
                safe_count += 1
            else:
                blocked_count += 1
                blocked_reason_counts[reason] = blocked_reason_counts.get(reason, 0) + 1
                blocked_examples.setdefault(reason, [])
                if len(blocked_examples[reason]) < 3:
                    blocked_examples[reason].append(sid)

    verdict_counts = claim_summary.get("verdict_counts", {}) if isinstance(claim_summary, dict) else {}
    sentence_checked = int(claim_summary.get("sentences_checked", 0) or len(claim_rows))
    surfaced_claim_comments = [
        row for row in comments if isinstance(row, dict) and bool(row.get("from_claim_check"))
    ]
    surfaced_high_value = sum(1 for row in surfaced_claim_comments if _is_high_value_claim_comment(row))
    surfaced_low_value = max(0, len(surfaced_claim_comments) - surfaced_high_value)

    responder = manifest.get("comment_response_manifest", {})
    responder_summary = responder.get("summary", {}) if isinstance(responder, dict) else {}
    responder_rows = responder.get("responses", []) if isinstance(responder, dict) else []
    concrete_count = 0
    needs_clarification = 0
    for row in responder_rows if isinstance(responder_rows, list) else []:
        if not isinstance(row, dict):
            continue
        response_type = str(row.get("response_type", "")).strip()
        proposed = str(row.get("proposed_response", "")).strip()
        if response_type in {"text_fix", "response_strategy", "already_addressed"} and proposed:
            concrete_count += 1
        if response_type == "needs_clarification":
            needs_clarification += 1

    dedupe_quality = {}
    artifact_quality = manifest.get("artifact_quality_checks", {})
    if isinstance(artifact_quality, dict):
        dedupe_quality = artifact_quality.get("deduplication", {})

    surviving_rewrites = max(0, rewrite_candidates - no_op_rewrites - trivial_rewrites)
    no_op_rate = round(no_op_rewrites / rewrite_candidates, 4) if rewrite_candidates > 0 else None
    trivial_rate = round(trivial_rewrites / rewrite_candidates, 4) if rewrite_candidates > 0 else None
    materially_better_rate = (
        round(materially_better_rewrites / surviving_rewrites, 4) if surviving_rewrites > 0 else None
    )
    style_suppressed_rate = round(style_suppressed / style_candidates, 4) if style_candidates > 0 else None

    return {
        "meta": {
            "comment_count": len(comments),
            "verbosity_threshold_words": verbosity_threshold_words,
        },
        "anchor_localization": {
            "avg_anchor_length_words": round(sum(anchor_lengths) / max(1, len(anchor_lengths)), 3),
            "max_anchor_length_words": max(anchor_lengths) if anchor_lengths else 0,
            "sentence_local_comment_count": sentence_local_total,
            "sentence_local_exceed_one_sentence_count": sentence_local_excess,
            "sentence_local_exceed_one_sentence_rate": round(sentence_local_excess / max(1, sentence_local_total), 4),
            "paragraph_wide_local_anchor_count": paragraph_wide_local_count,
            "paragraph_wide_local_anchor_rate": round(paragraph_wide_local_count / max(1, sentence_local_total), 4),
            "clause_local_comment_count": clause_local_total,
            "clause_local_too_broad_count": clause_local_excess,
            "clause_local_too_broad_rate": round(clause_local_excess / max(1, clause_local_total), 4),
        },
        "rewrite_usefulness": {
            "rewrite_candidate_count": rewrite_candidates,
            "no_op_rewrite_count": no_op_rewrites,
            "no_op_rewrite_rate": no_op_rate,
            "trivial_rewrite_count": trivial_rewrites,
            "trivial_rewrite_rate": trivial_rate,
            "surviving_rewrite_count": surviving_rewrites,
            "materially_better_surviving_count": materially_better_rewrites,
            "materially_better_surviving_rate": materially_better_rate,
            "style_candidate_count": style_candidates,
            "style_suppressed_rewrite_count": style_suppressed,
            "style_suppressed_rewrite_rate": style_suppressed_rate,
        },
        "comment_concision": {
            "avg_comment_length_words": round(sum(comment_lengths) / max(1, len(comment_lengths)), 3),
            "verbosity_threshold_words": verbosity_threshold_words,
            "comments_above_threshold_count": verbose_count,
            "comments_above_threshold_rate": round(verbose_count / max(1, len(comment_lengths)), 4),
            "actionable_comment_count": actionable_count,
            "generic_comment_count": generic_count,
            "actionable_to_generic_ratio": round(actionable_count / max(1, generic_count), 4),
        },
        "deduplication_quality": {
            "near_duplicate_pair_count": near_duplicate_pairs,
            "near_duplicate_pair_rate": round(near_duplicate_pairs / max(1, pair_total), 4),
            "same_sentence_overlap_count": same_sentence_overlaps,
            "overlapping_comment_rate": round(same_sentence_overlaps / max(1, len(comments)), 4),
            "merged_total": int(dedupe_quality.get("merged_total", 0) or 0),
            "unmerged_duplicate_pairs_final": int(dedupe_quality.get("unmerged_duplicate_pairs_final", near_duplicate_pairs) or 0),
            "unmerged_same_anchor_overlap_final": int(dedupe_quality.get("unmerged_same_anchor_overlap_final", same_sentence_overlaps) or 0),
        },
        "claim_check_coverage": {
            "sentences_classified": sentence_checked,
            "factual_claim_count": factual_claim_count,
            "factual_claim_rate": round(factual_claim_count / max(1, sentence_checked), 4),
            "category_counts": category_counts,
            "verdict_distribution": verdict_counts if isinstance(verdict_counts, dict) else {},
            "citation_needed_rate": round(float((verdict_counts or {}).get(VERDICT_NEEDS_CITATION, 0)) / max(1, sentence_checked), 4),
            "overclaim_rate": round(
                float((verdict_counts or {}).get(VERDICT_LIKELY_OVERCLAIM, 0) + (verdict_counts or {}).get(VERDICT_WORDING_STRONGER, 0))
                / max(1, sentence_checked),
                4,
            ),
            "unclear_support_rate": round(float((verdict_counts or {}).get(VERDICT_UNCLEAR_SUPPORT, 0)) / max(1, sentence_checked), 4),
            "surfaced_comment_count": len(surfaced_claim_comments),
            "suppressed_comment_count": int(claim_projection_summary.get("suppressed_count", 0) or 0),
            "suppressed_reason_counts": (
                claim_projection_summary.get("suppressed_reason_counts", {})
                if isinstance(claim_projection_summary, dict)
                else {}
            ),
            "surfaced_high_value_count": surfaced_high_value,
            "surfaced_low_value_count": surfaced_low_value,
            "surfaced_high_value_rate": round(surfaced_high_value / max(1, len(surfaced_claim_comments)), 4),
        },
        "privacy_search_safety": {
            "safe_externalization_count": safe_count,
            "blocked_externalization_count": blocked_count,
            "safe_externalization_rate": round(safe_count / max(1, safe_count + blocked_count), 4),
            "blocked_reason_counts": blocked_reason_counts,
            "blocked_reason_examples": blocked_examples,
            "search_layer": claim_manifest.get("search_layer", {}) if isinstance(claim_manifest, dict) else {},
        },
        "existing_comment_responder_coverage": {
            "source_comments_read_count": int(responder_summary.get("existing_comments_detected", 0) or 0),
            "responses_generated_count": int(responder_summary.get("responses_generated", 0) or 0),
            "concrete_response_count": concrete_count,
            "needs_clarification_count": needs_clarification,
            "needs_clarification_rate": round(needs_clarification / max(1, int(responder_summary.get("responses_generated", 0) or 0)), 4),
            "concrete_response_rate": round(concrete_count / max(1, int(responder_summary.get("existing_comments_detected", 0) or 0)), 4),
        },
        "style_pass_outcomes": {
            "style_comments_surfaced_count": style_surfaced,
            "style_rewrites_accepted_count": style_rewrites_accepted,
            "style_rewrites_suppressed_count": style_suppressed,
            "style_rewrites_accepted_rate": round(style_rewrites_accepted / max(1, style_candidates), 4),
            "style_rewrites_suppressed_rate": round(style_suppressed / max(1, style_candidates), 4),
        },
        "overall_comment_mix": {
            "total_comments": len(comments),
            "counts": {**mix_counts, "other": other_mix},
            "rates": {
                **{k: round(v / max(1, len(comments)), 4) for k, v in mix_counts.items()},
                "other": round(other_mix / max(1, len(comments)), 4),
            },
        },
    }


def metric_value(metrics: dict[str, Any], key_path: str) -> float | int | None:
    node: Any = metrics
    for part in key_path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    if isinstance(node, (int, float)):
        return node
    return None


def compare_metric_dicts(before: dict[str, Any], after: dict[str, Any], key_paths: list[str]) -> dict[str, dict[str, float | int | None]]:
    out: dict[str, dict[str, float | int | None]] = {}
    for key in key_paths:
        b = metric_value(before, key)
        a = metric_value(after, key)
        delta = None
        if isinstance(b, (int, float)) and isinstance(a, (int, float)):
            delta = round(a - b, 6)
        out[key] = {"before": b, "after": a, "delta": delta}
    return out
