from __future__ import annotations

from difflib import SequenceMatcher

from ai_reviewer.ingest.types import ParsedDocument


def _split_sentences(text: str) -> list[str]:
    candidates = [x.strip() for x in text.replace("\n", " ").split(". ")]
    return [c for c in candidates if len(c) > 20]


def align_sections(old: ParsedDocument, new: ParsedDocument) -> list[tuple[str, str, float]]:
    old_heads = old.headings or ["Full Document"]
    new_heads = new.headings or ["Full Document"]
    pairs: list[tuple[str, str, float]] = []
    for o in old_heads:
        best = ""
        best_score = -1.0
        for n in new_heads:
            score = SequenceMatcher(None, o.lower(), n.lower()).ratio()
            if score > best_score:
                best = n
                best_score = score
        pairs.append((o, best, round(best_score, 3)))
    return pairs


def section_add_remove(old: ParsedDocument, new: ParsedDocument) -> tuple[list[str], list[str]]:
    old_set = {h.lower(): h for h in old.headings}
    new_set = {h.lower(): h for h in new.headings}

    added = [v for k, v in new_set.items() if k not in old_set]
    removed = [v for k, v in old_set.items() if k not in new_set]
    return added, removed


def detect_claim_changes(old: ParsedDocument, new: ParsedDocument) -> tuple[list[str], list[str], list[str]]:
    old_sents = _split_sentences(old.cleaned_text)
    new_sents = _split_sentences(new.cleaned_text)

    added = [s for s in new_sents[:350] if all(SequenceMatcher(None, s, o).ratio() < 0.55 for o in old_sents[:450])]
    removed = [s for s in old_sents[:350] if all(SequenceMatcher(None, s, n).ratio() < 0.55 for n in new_sents[:450])]

    changed: list[str] = []
    for o in old_sents[:220]:
        best = max(new_sents[:260], key=lambda n: SequenceMatcher(None, o, n).ratio(), default="")
        score = SequenceMatcher(None, o, best).ratio()
        if 0.60 <= score <= 0.90:
            changed.append(f"OLD: {o} -> NEW: {best}")

    return added[:30], removed[:30], changed[:30]


def addressed_weaknesses(old_weaknesses: list[str], new_text: str) -> tuple[list[str], list[str]]:
    addressed: list[str] = []
    unresolved: list[str] = []
    lowered = new_text.lower()
    for weakness in old_weaknesses:
        tokens = [t for t in weakness.lower().split() if len(t) > 4][:4]
        if tokens and any(tok in lowered for tok in tokens):
            addressed.append(weakness)
        else:
            unresolved.append(weakness)
    return addressed, unresolved
