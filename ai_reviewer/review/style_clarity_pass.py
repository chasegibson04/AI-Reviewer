from __future__ import annotations

from dataclasses import dataclass
import difflib
import json
import re
from typing import Any

from ai_reviewer.models.base import ChatRequest, Provider
from ai_reviewer.review.repair import extract_json_candidate


STYLE_KIND_OVERLOADED = "overloaded_sentence"
STYLE_KIND_DEFINITION = "definition_clarity"
STYLE_KIND_CONCISION = "concision"
STYLE_KIND_REDUNDANCY = "redundancy"
STYLE_KIND_TRANSITION = "transition"
STYLE_KIND_READABILITY = "readability"


@dataclass
class StyleSentence:
    sentence_id: str
    paragraph_index: int
    sentence_index: int
    section: str
    text: str


@dataclass
class StyleIssue:
    kind: str
    critique: str
    action: str
    priority: int


def _split_sentences(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    protected = raw
    for token in ["Fig.", "Figs.", "Eq.", "Eqs.", "Ref.", "Refs.", "e.g.", "i.e.", "et al."]:
        protected = protected.replace(token, token.replace(".", "<prd>"))
    parts = re.split(r"(?<=[.!?])\s+", protected)
    return [p.replace("<prd>", ".").strip() for p in parts if p.strip()]


def _normalize(text: str) -> str:
    low = str(text or "").lower()
    low = re.sub(r"[“”\"'`]", "", low)
    low = re.sub(r"[\W_]+", " ", low)
    return re.sub(r"\s+", " ", low).strip()


def _token_set(text: str) -> set[str]:
    toks = re.findall(r"[a-z0-9][a-z0-9\-]+", _normalize(text))
    return {t for t in toks if len(t) >= 3}


def _token_overlap(a: str, b: str) -> float:
    ta = _token_set(a)
    tb = _token_set(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def _redundancy_score(text: str) -> float:
    toks = [t for t in re.findall(r"[a-z0-9][a-z0-9\-]+", _normalize(text)) if len(t) >= 4]
    if not toks:
        return 0.0
    counts: dict[str, int] = {}
    for tok in toks:
        counts[tok] = counts.get(tok, 0) + 1
    repeated = sum(max(0, c - 1) for c in counts.values())
    return repeated / len(toks)


def _clause_count(text: str) -> int:
    s = str(text or "")
    base = len([x for x in re.split(r"[;:]", s) if x.strip()])
    conj = len(re.findall(r"\b(and|but|while|whereas|although|which|that)\b", s, flags=re.IGNORECASE))
    return max(1, base + conj)


def _sentence_count(text: str) -> int:
    parts = _split_sentences(text)
    return len(parts) if parts else (1 if str(text or "").strip() else 0)


def _looks_artifact_sentence(sentence: str) -> bool:
    s = str(sentence or "").strip()
    low = s.lower()
    if not s:
        return True
    if any(mark in low for mark in ["start of picture text", "end of picture text", "<br>"]):
        return True
    if low.startswith(("fig.", "figure ", "table ", "scheme ", "supplementary")):
        return True
    if re.search(r"\(\d{4}[a-z]?\)\.?$", s) and re.search(r"\b\d{1,4}\s*[,:\u2013-]\s*\d{1,5}\b", s):
        return True
    words = re.findall(r"[a-zA-Z]+", s)
    if not words:
        return True
    symbol_ratio = 1.0 - (sum(len(w) for w in words) / max(1, len(s)))
    if symbol_ratio >= 0.45 and len(words) <= 10:
        return True
    return False


def segment_style_sentences(paragraphs: list[str], section_by_idx: dict[int, str]) -> list[StyleSentence]:
    rows: list[StyleSentence] = []
    for pidx, paragraph in enumerate(paragraphs):
        section = section_by_idx.get(pidx, "body")
        if section in {"front_matter", "references", "header_footer"}:
            continue
        if not str(paragraph or "").strip():
            continue
        for sidx, sentence in enumerate(_split_sentences(paragraph)):
            s = sentence.strip()
            if len(s.split()) < 7:
                continue
            if _looks_artifact_sentence(s):
                continue
            rows.append(
                StyleSentence(
                    sentence_id=f"p{pidx:04d}.s{sidx:03d}",
                    paragraph_index=pidx,
                    sentence_index=sidx,
                    section=section,
                    text=s,
                )
            )
    return rows


def _starts_ambiguous_referent(sentence: str) -> bool:
    return bool(re.match(r"^\s*(this|these|it|they)\b", sentence.strip().lower()))


def classify_style_issue(sentence: str, prev_sentence: str | None = None) -> StyleIssue | None:
    s = sentence.strip()
    low = s.lower()
    words = s.split()
    if len(words) < 10:
        return None
    comma_count = s.count(",")
    if len(words) >= 34 or comma_count >= 3 or ";" in s:
        return StyleIssue(
            kind=STYLE_KIND_OVERLOADED,
            critique="Split this into two sentences to separate setup from outcome.",
            action="split sentence",
            priority=0,
        )
    if re.search(r"\b(is|are)\s+defined\s+as\b|\brefers to\b|\bmeans that\b", low):
        return StyleIssue(
            kind=STYLE_KIND_DEFINITION,
            critique="Tighten this sentence by making the definition direct.",
            action="tighten definition",
            priority=1,
        )
    if any(p in low for p in ["it should be noted that", "in order to", "has the ability to", "a number of"]):
        return StyleIssue(
            kind=STYLE_KIND_CONCISION,
            critique="Tighten this sentence by removing filler phrasing.",
            action="remove filler",
            priority=2,
        )
    if _redundancy_score(s) >= 0.18:
        return StyleIssue(
            kind=STYLE_KIND_REDUNDANCY,
            critique="Tighten this sentence by removing repeated wording.",
            action="reduce redundancy",
            priority=2,
        )
    if _starts_ambiguous_referent(s) and prev_sentence and len(prev_sentence.split()) >= 8:
        return StyleIssue(
            kind=STYLE_KIND_TRANSITION,
            critique="Tighten this sentence by clarifying the transition referent.",
            action="clarify transition",
            priority=3,
        )
    if len(words) >= 24 and comma_count >= 2:
        return StyleIssue(
            kind=STYLE_KIND_READABILITY,
            critique="Tighten this sentence by improving clause order.",
            action="improve flow",
            priority=3,
        )
    return None


def _split_overloaded_sentence(sentence: str) -> str:
    s = sentence.strip()

    def _clean_right_clause(text: str) -> str:
        out = text.strip()
        out = re.sub(r"^(and|or|but)\s+", "", out, flags=re.IGNORECASE)
        out = out.strip()
        if out and out[0].islower():
            out = out[0].upper() + out[1:]
        return out

    cite_break = re.split(r"(?<=\])\s+(?=[A-Z])", s, maxsplit=1)
    if len(cite_break) == 2 and len(cite_break[0].split()) >= 8 and len(cite_break[1].split()) >= 8:
        right = _clean_right_clause(cite_break[1])
        if right and right[-1] not in ".!?":
            right += "."
        left = cite_break[0].strip()
        if left and left[-1] not in ".!?":
            left += "."
        return f"{left} {right}".strip()
    if s.lower().startswith("to ") and "," in s:
        left, right = s.split(",", 1)
        left = left.strip()
        right = right.strip()
        if len(left.split()) >= 6 and len(right.split()) >= 8:
            right_clean = _clean_right_clause(right.rstrip("."))
            if right_clean and right_clean[-1] not in ".!?":
                right_clean += "."
            purpose = left[3:].strip().rstrip(".")
            if purpose:
                subject = "This workflow" if "workflow" in right_clean.lower() else "This approach"
                second = f"{subject} was designed to {purpose}."
                return f"{right_clean} {second}".strip()
    for pattern in [
        r",\s+while\b",
        r",\s+whereas\b",
        r",\s+and\s+(?:therefore|thus|then)\b",
        r";\s+",
        r":\s+",
    ]:
        parts = re.split(pattern, s, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            left = parts[0].strip().rstrip(".")
            right = _clean_right_clause(parts[1])
            if len(left.split()) >= 8 and len(right.split()) >= 8:
                if right and right[-1] not in ".!?":
                    right += "."
                return f"{left}. {right}"
    return s if s.endswith((".", "?", "!")) else f"{s}."


def deterministic_style_rewrite(sentence: str, issue_kind: str) -> str:
    s = sentence.strip()
    s = re.sub(r"\s+", " ", s)
    replacements = {
        r"\bit should be noted that\b": "",
        r"\bin order to\b": "to",
        r"\bhas the ability to\b": "can",
        r"\ba number of\b": "several",
        r"\bdue to the fact that\b": "because",
    }
    for pattern, repl in replacements.items():
        s = re.sub(pattern, repl, s, flags=re.IGNORECASE)
    s = re.sub(r"^\s*(Critically|Notably|Importantly|Interestingly),\s+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    if issue_kind == STYLE_KIND_OVERLOADED:
        return _split_overloaded_sentence(s)
    if issue_kind == STYLE_KIND_DEFINITION:
        m = re.search(r"^(.+?)\s+(?:is|are)\s+defined\s+as\s+(.+)$", s, flags=re.IGNORECASE)
        if m:
            subject = m.group(1).strip()
            rest = m.group(2).strip().rstrip(".")
            return f"{subject} is {rest}."
    if issue_kind == STYLE_KIND_REDUNDANCY:
        clauses = [c.strip() for c in re.split(r",\s*", s) if c.strip()]
        kept: list[str] = []
        seen: set[str] = set()
        for clause in clauses:
            sig = _normalize(clause)
            if sig in seen:
                continue
            seen.add(sig)
            kept.append(clause)
        if kept:
            out = ", ".join(kept)
            return out if out.endswith((".", "?", "!")) else f"{out}."
    if issue_kind == STYLE_KIND_TRANSITION:
        s = re.sub(r"^\s*This\b", "This result", s, flags=re.IGNORECASE)
        s = re.sub(r"^\s*These\b", "These findings", s, flags=re.IGNORECASE)
        s = re.sub(r"^\s*It\b", "This result", s, flags=re.IGNORECASE)
        s = re.sub(r"^\s*They\b", "These results", s, flags=re.IGNORECASE)
        s = re.sub(r"\s{2,}", " ", s).strip()
    if issue_kind == STYLE_KIND_READABILITY:
        s = re.sub(r"\bwhich enables\b", "enabling", s, flags=re.IGNORECASE)
        s = re.sub(r"\bthat can be\b", "that is", s, flags=re.IGNORECASE)
        s = re.sub(r"\s{2,}", " ", s).strip()
    return s if s.endswith((".", "?", "!")) else f"{s}."


def style_rewrite_usefulness_check(original: str, revised: str, issue_kind: str) -> tuple[bool, str | None, dict[str, Any]]:
    o = str(original or "").strip()
    r = str(revised or "").strip()
    metrics: dict[str, Any] = {}
    if not o or not r:
        return False, "empty_revision", metrics
    no = _normalize(o)
    nr = _normalize(r)
    if not nr:
        return False, "empty_revision", metrics
    o_words = len(o.split())
    r_words = len(r.split())
    split_improvement = (
        issue_kind == STYLE_KIND_OVERLOADED
        and _sentence_count(o) == 1
        and _sentence_count(r) == 2
        and max(len(x.split()) for x in _split_sentences(r)) <= max(28, o_words - 3)
    )
    if no == nr:
        if not split_improvement:
            return False, "no_change_normalized", metrics
    ratio = difflib.SequenceMatcher(None, no, nr).ratio()
    metrics["normalized_similarity"] = round(ratio, 4)
    if ratio >= 0.97 and not split_improvement:
        return False, "trivial_change", metrics
    if _sentence_count(r) > 2:
        return False, "too_many_sentences", metrics
    if _sentence_count(r) == 2 and issue_kind != STYLE_KIND_OVERLOADED:
        return False, "unsupported_sentence_split", metrics
    if re.search(r"[,;:]\s*$", r):
        return False, "truncated_fragment", metrics
    if r.count("(") != r.count(")") or r.count("[") != r.count("]"):
        return False, "unbalanced_delimiters", metrics
    overlap = _token_overlap(o, r)
    metrics["token_overlap"] = round(overlap, 4)
    if overlap < 0.42:
        return False, "semantic_drift_risk", metrics
    if "[sentence continues" in r.lower():
        return False, "placeholder_rewrite", metrics

    metrics["word_count_delta"] = r_words - o_words

    o_red = _redundancy_score(o)
    r_red = _redundancy_score(r)
    metrics["redundancy_before"] = round(o_red, 4)
    metrics["redundancy_after"] = round(r_red, 4)

    o_clause = _clause_count(o)
    r_clause = _clause_count(r)
    metrics["clause_count_before"] = o_clause
    metrics["clause_count_after"] = r_clause

    improvements = 0
    if r_red + 0.05 <= o_red:
        improvements += 1
    if r_clause < o_clause:
        improvements += 1
    if issue_kind in {STYLE_KIND_CONCISION, STYLE_KIND_REDUNDANCY, STYLE_KIND_READABILITY} and r_words <= max(7, int(o_words * 0.92)):
        improvements += 1
    if split_improvement:
        improvements += 1
    if issue_kind == STYLE_KIND_TRANSITION and re.match(r"^\s*(however|therefore|specifically|for example|in contrast)\b", r, flags=re.IGNORECASE):
        improvements += 1
    if issue_kind == STYLE_KIND_TRANSITION and _starts_ambiguous_referent(o) and not _starts_ambiguous_referent(r):
        improvements += 1
    if issue_kind == STYLE_KIND_DEFINITION and "defined as" not in r.lower():
        improvements += 1

    metrics["improvement_signals"] = improvements
    if (
        issue_kind == STYLE_KIND_OVERLOADED
        and split_improvement
        and ratio >= 0.995
        and r_words == o_words
        and r_clause >= o_clause
        and r_red >= (o_red - 0.01)
    ):
        return False, "punctuation_only_split", metrics
    if improvements < 1:
        return False, "insufficient_improvement", metrics
    return True, None, metrics


def _llm_style_rewrite(
    provider: Provider,
    model: str,
    sentence: str,
    issue: StyleIssue,
    section: str,
    timeout_seconds: int,
) -> tuple[str, str, str]:
    payload = {
        "sentence": sentence,
        "issue_kind": issue.kind,
        "section": section,
        "constraints": {
            "sentence_local_default": True,
            "allow_two_sentences_only_for_overloaded": True,
            "preserve_scientific_meaning": True,
        },
    }
    system_prompt = (
        "You are a scientific line editor. Rewrite one sentence for style and clarity. "
        "Keep meaning unchanged. Output JSON only with keys: critique, action, rewrite. "
        "Use at most two sentences only when splitting a clearly overloaded sentence."
    )
    resp = provider.chat(
        ChatRequest(
            model=model,
            system_prompt=system_prompt,
            user_prompt=json.dumps(payload, ensure_ascii=False),
            temperature=0.1,
            max_tokens=260,
            timeout_seconds=timeout_seconds,
            metadata={"purpose": "style_clarity_pass"},
        )
    )
    parsed = json.loads(extract_json_candidate(resp.content) or resp.content)
    critique = str(parsed.get("critique", "")).strip() or issue.critique
    action = str(parsed.get("action", "")).strip() or issue.action
    rewrite = str(parsed.get("rewrite", "")).strip()
    return critique, action, rewrite


def _select_style_model(provider: Provider | None, fallback_model: str | None) -> tuple[str | None, bool]:
    if provider is None:
        return None, False
    try:
        models = set(provider.list_models())
    except Exception:
        models = set()
    if "gemma4:31b" in models:
        return "gemma4:31b", True
    return fallback_model, False


def run_style_clarity_pass(
    paragraphs: list[str],
    section_by_idx: dict[int, str],
    provider: Provider | None,
    model: str | None,
    timeout_seconds: int,
    max_candidates: int = 36,
) -> dict[str, Any]:
    rows = segment_style_sentences(paragraphs, section_by_idx)
    selected_model, gemma_used = _select_style_model(provider, model)
    llm_available = provider is not None and selected_model is not None
    llm_enabled = llm_available
    llm_fail_fast_triggered = False
    items: list[dict[str, Any]] = []
    issue_counts: dict[str, int] = {}
    proposed = 0
    suppressed = 0
    fallback_used_any = not llm_available

    by_paragraph: dict[int, list[StyleSentence]] = {}
    for row in rows:
        by_paragraph.setdefault(row.paragraph_index, []).append(row)

    for pidx in sorted(by_paragraph):
        sent_rows = by_paragraph[pidx]
        for idx, row in enumerate(sent_rows):
            if len(items) >= max_candidates:
                break
            prev = sent_rows[idx - 1].text if idx > 0 else None
            issue = classify_style_issue(row.text, prev_sentence=prev)
            if issue is None:
                continue
            used_fallback = not llm_available
            critique = issue.critique
            action = issue.action
            rewrite = deterministic_style_rewrite(row.text, issue.kind)
            if llm_enabled:
                try:
                    critique, action, rewrite_llm = _llm_style_rewrite(
                        provider=provider,  # type: ignore[arg-type]
                        model=selected_model,  # type: ignore[arg-type]
                        sentence=row.text,
                        issue=issue,
                        section=row.section,
                        timeout_seconds=timeout_seconds,
                    )
                    if rewrite_llm:
                        rewrite = rewrite_llm
                    used_fallback = False
                except Exception:
                    used_fallback = True
                    fallback_used_any = True
                    llm_enabled = False
                    llm_fail_fast_triggered = True

            useful, reason, metrics = style_rewrite_usefulness_check(row.text, rewrite, issue.kind)
            if not useful and reason in {
                "no_change_normalized",
                "trivial_change",
                "truncated_fragment",
                "unbalanced_delimiters",
            }:
                # Treat clearly non-actionable rewrite attempts as non-candidates.
                continue
            if not useful and issue.kind in {STYLE_KIND_TRANSITION, STYLE_KIND_READABILITY}:
                # Skip low-signal transition/readability candidates unless rewrite passes the usefulness gate.
                continue
            if useful:
                proposed += 1
            else:
                suppressed += 1
            issue_counts[issue.kind] = issue_counts.get(issue.kind, 0) + 1
            items.append(
                {
                    "sentence_id": row.sentence_id,
                    "paragraph_index": row.paragraph_index,
                    "section": row.section,
                    "sentence_text": row.text,
                    "issue_kind": issue.kind,
                    "critique": critique,
                    "action": action,
                    "rewrite": rewrite,
                    "rewrite_useful": useful,
                    "suppression_reason": reason,
                    "metrics": metrics,
                    "model_used": selected_model if llm_available and not used_fallback else None,
                    "fallback_used": used_fallback,
                    "priority": issue.priority,
                }
            )

    return {
        "model": {
            "selected_model": selected_model,
            "gemma4_31b_used": bool(gemma_used and llm_available),
            "fallback_used": fallback_used_any or any(bool(x.get("fallback_used")) for x in items),
            "fail_fast_fallback_triggered": llm_fail_fast_triggered,
        },
        "summary": {
            "sentences_scanned": len(rows),
            "candidate_count": len(items),
            "rewrites_proposed": proposed,
            "rewrites_suppressed": suppressed,
            "issue_counts": issue_counts,
        },
        "items": items,
    }


def style_results_to_comment_entries(style_manifest: dict[str, Any], max_comments: int = 10) -> list[dict[str, Any]]:
    rows = style_manifest.get("items", [])
    if not isinstance(rows, list):
        return []
    ordered = sorted(
        [r for r in rows if isinstance(r, dict) and bool(r.get("rewrite_useful"))],
        key=lambda r: (
            -int((r.get("metrics") or {}).get("improvement_signals", 0)),
            int(r.get("priority", 9)),
            int(r.get("paragraph_index", 10**6)),
        ),
    )
    out: list[dict[str, Any]] = []
    for row in ordered:
        sentence = str(row.get("sentence_text", "")).strip()
        rewrite = str(row.get("rewrite", "")).strip()
        if not sentence or not rewrite:
            continue
        issue_kind = str(row.get("issue_kind", "")).strip()
        if issue_kind == STYLE_KIND_OVERLOADED:
            critique = "Split this into two sentences to separate setup from outcome."
        elif issue_kind == STYLE_KIND_DEFINITION:
            critique = "Tighten this sentence by making the definition direct."
        elif issue_kind == STYLE_KIND_TRANSITION:
            critique = "Tighten this sentence by clarifying the transition."
        elif issue_kind == STYLE_KIND_REDUNDANCY:
            critique = "Tighten this sentence by removing repeated wording."
        else:
            critique = "Tighten this sentence by improving flow and readability."
        out.append(
            {
                "comment_id": f"style_{str(row.get('sentence_id', 's')).replace('.', '_')}",
                "paragraph_index": int(row.get("paragraph_index", 0)),
                "issue_type": "style/clarity",
                "severity": "medium",
                "critique": critique,
                "suggested_revision": f"Proposed edit: {rewrite}",
                "rationale": f"Style pass issue: {issue_kind}.",
                "anchor_text": sentence[:320],
                "span_sentence": sentence[:320],
                "priority_score": 4,
                "from_style_pass": True,
                "style_issue_kind": issue_kind,
                "style_metrics": row.get("metrics", {}),
            }
        )
        if len(out) >= max_comments:
            break
    return out
