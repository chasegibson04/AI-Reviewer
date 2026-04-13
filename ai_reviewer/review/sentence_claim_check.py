from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any, Protocol
import json
import re

from ai_reviewer.models.base import ChatRequest, Provider
from ai_reviewer.review.repair import extract_json_candidate


SENTENCE_CATEGORY_PUBLIC = "public/background factual claim"
SENTENCE_CATEGORY_LITERATURE = "literature/citation-supported claim"
SENTENCE_CATEGORY_MANUSCRIPT = "manuscript-specific result or novel assertion"
SENTENCE_CATEGORY_INTERPRETATION = "interpretation/inference"
SENTENCE_CATEGORY_STYLE_ONLY = "style-only / non-factual sentence"
SENTENCE_CATEGORY_AMBIGUOUS = "ambiguous/mixed"

VERDICT_SUPPORTED = "supported"
VERDICT_PARTIALLY_SUPPORTED = "partially supported"
VERDICT_UNCLEAR_SUPPORT = "unclear support"
VERDICT_LIKELY_OVERCLAIM = "likely overclaim"
VERDICT_NEEDS_CITATION = "needs citation"
VERDICT_UNVERIFIABLE_MANUSCRIPT = "unverifiable externally because manuscript-specific"
VERDICT_WORDING_STRONGER = "wording stronger than evidence"

SUPPORTED_VERDICTS = {
    VERDICT_SUPPORTED,
    VERDICT_PARTIALLY_SUPPORTED,
    VERDICT_UNCLEAR_SUPPORT,
    VERDICT_LIKELY_OVERCLAIM,
    VERDICT_NEEDS_CITATION,
    VERDICT_UNVERIFIABLE_MANUSCRIPT,
    VERDICT_WORDING_STRONGER,
}


@dataclass
class ReviewSentence:
    sentence_id: str
    paragraph_index: int
    sentence_index: int
    section: str
    text: str


@dataclass
class PrivacyDecision:
    safe_for_external_search: bool
    reason: str
    minimized_query: str | None


@dataclass
class EvidenceSnippet:
    source: str
    snippet: str
    score: float
    provenance: str


@dataclass
class SentenceCheckResult:
    sentence_id: str
    paragraph_index: int
    sentence_text: str
    section: str
    category: str
    privacy: PrivacyDecision
    verdict: str
    feedback: str
    action: str
    rewrite: str | None
    local_evidence: list[EvidenceSnippet]
    external_evidence: list[EvidenceSnippet]
    used_external_search: bool
    model_used: str | None
    fallback_used: bool


class ExternalSearchProvider(Protocol):
    name: str

    def search(self, query: str, top_k: int = 3) -> list[EvidenceSnippet]:
        ...


class MockExternalSearchProvider:
    name = "mock"

    def __init__(self, responses_by_query: dict[str, list[str]] | None = None):
        self._responses_by_query = responses_by_query or {}
        self.queries: list[str] = []

    def search(self, query: str, top_k: int = 3) -> list[EvidenceSnippet]:
        self.queries.append(query)
        hits = self._responses_by_query.get(query, [])[:top_k]
        return [
            EvidenceSnippet(source="external", snippet=hit, score=0.6, provenance=f"mock:{idx}")
            for idx, hit in enumerate(hits, start=1)
        ]


def _split_sentences(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    protected = raw
    abbreviations = [
        "Fig.",
        "Figs.",
        "Eq.",
        "Eqs.",
        "Ref.",
        "Refs.",
        "Dr.",
        "Prof.",
        "Mr.",
        "Mrs.",
        "Ms.",
        "vs.",
        "e.g.",
        "i.e.",
        "et al.",
    ]
    for token in abbreviations:
        protected = protected.replace(token, token.replace(".", "<prd>"))
    parts = re.split(r"(?<=[.!?])\s+", protected)
    out = [p.replace("<prd>", ".").strip() for p in parts if p.strip()]
    return out


def _normalize(text: str) -> str:
    low = str(text or "").lower()
    low = re.sub(r"[\W_]+", " ", low)
    return re.sub(r"\s+", " ", low).strip()


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9][a-z0-9-]+", _normalize(text)) if len(t) >= 3]


def _token_overlap(a: str, b: str) -> float:
    ta = set(_tokens(a))
    tb = set(_tokens(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def _word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", str(text or "").strip()) if w])


def _citation_marker_count(text: str) -> int:
    s = str(text or "")
    bracketed = re.findall(r"\[[^\]]+\]", s)
    year_refs = re.findall(r"\([12][0-9]{3}[a-z]?\)", s)
    return len(bracketed) + len(year_refs)


def _content_token_count(text: str) -> int:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "these",
        "those",
        "from",
        "into",
        "were",
        "was",
        "are",
        "is",
        "been",
        "being",
        "have",
        "has",
        "had",
        "also",
        "therefore",
        "thus",
        "however",
        "while",
        "using",
        "used",
        "study",
        "work",
        "results",
        "result",
        "data",
    }
    toks = [t for t in _tokens(text) if t not in stop]
    return len(toks)


def _looks_citation_dense_fragment(sentence: str) -> bool:
    s = str(sentence or "").strip()
    if not s:
        return True
    words = _word_count(s)
    citations = _citation_marker_count(s)
    content = _content_token_count(s)
    if citations >= 3 and words <= 26 and content <= 10:
        return True
    if citations >= 2 and words <= 16 and content <= 7:
        return True
    if citations >= 2 and words > 0 and (citations / words) >= 0.18 and content <= 9:
        return True
    # Fragment-like sentence ending in citation with limited standalone claim content.
    has_claim_verb = bool(
        re.search(
            r"\b(reported?|show(?:s|ed)?|demonstrat(?:e|ed|es)|indicat(?:e|ed|es)|observed?)\b",
            s.lower(),
        )
    )
    if citations >= 1 and re.search(r"\[[^\]]+\]\s*\.?$", s) and content <= 6 and words <= 14 and not has_claim_verb:
        return True
    return False


def _looks_figure_table_reference_sentence(sentence: str) -> bool:
    low = str(sentence or "").strip().lower()
    if not low:
        return True
    if re.fullmatch(r"(see\s+)?(fig\.?|figure|table|scheme)\s*[a-z0-9().\-]+\.?", low):
        return True
    if re.match(r"^(see\s+)?(fig\.?|figure|table|scheme)\s*[a-z0-9().\-]+\b", low) and _word_count(low) <= 8:
        return True
    return False


def _looks_low_information_sentence(sentence: str) -> bool:
    s = str(sentence or "").strip()
    if not s:
        return True
    words = _word_count(s)
    content = _content_token_count(s)
    if words < 4:
        return True
    if words <= 6 and content <= 2:
        return True
    if len(s) < 24 and content <= 2:
        return True
    return False


def _has_first_person_or_local_marker(sentence: str) -> bool:
    low = str(sentence or "").lower()
    patterns = [
        r"\bwe\b",
        r"\bour\b",
        r"\bherein\b",
        r"\bin this (study|work|manuscript|paper)\b",
        r"\bwe (observed|found|show|demonstrate|report|measured)\b",
    ]
    return any(re.search(p, low) for p in patterns)


def _has_manuscript_specific_marker(sentence: str) -> bool:
    low = str(sentence or "").lower()
    markers = [
        r"\byield\b",
        r"\bconversion\b",
        r"\bassay\b",
        r"\breaction array\b",
        r"\bscreen\b",
        r"\bwe observed\b",
        r"\bwe found\b",
        r"\bthis study\b",
        r"\bthis work\b",
        r"\bherein\b",
        r"\bunder condition\b",
        r"\bfirst attempt\b",
        r"\bfigure\s+\d+\b",
        r"\btable\s+\d+\b",
        r"\bn\s*=\s*\d+\b",
    ]
    if any(re.search(p, low) for p in markers):
        return True
    # Numeric performance claims are treated as local by default unless explicitly literature-only.
    if re.search(r"\b\d+(?:\.\d+)?\s*%|\b\d+(?:\.\d+)?\s*(mmol|nmol|mg|ml|µl|uL|h)\b", low):
        return True
    return False


def _has_interpretive_marker(sentence: str) -> bool:
    low = str(sentence or "").lower()
    return any(
        re.search(p, low)
        for p in [
            r"\btherefore\b",
            r"\bthus\b",
            r"\blikely\b",
            r"\bmay\b",
            r"\bmight\b",
            r"\bcould\b",
            r"\bsuggests?\b",
            r"\bindicates?\b",
            r"\bimplies?\b",
        ]
    )


def _looks_caption_or_artifact_sentence(sentence: str) -> bool:
    s = str(sentence or "").strip()
    low = s.lower()
    plain = re.sub(r"[*_`]", "", low).strip()
    if not s:
        return True
    if any(mark in plain for mark in ["start of picture text", "end of picture text", "<br>"]):
        return True
    if plain.startswith(("fig.", "figure ", "table ", "scheme ", "supplementary", "extended data ")):
        return True
    if re.match(r"^\(?[a-h]\)?\s*[\|:]", plain):
        return True
    if re.match(r"^\(?[a-h]\)?\s*,", plain):
        return True
    if re.match(r"^\(?[a-h]\)?\s*,\s*(heatmap|relative conversion|yield|conversion)\b", plain):
        return True
    if re.search(r"\brelative conversion\b|\bheatmap\b|\bup lc\b|\buplc\b", plain) and len(plain.split()) <= 18:
        return True
    word_tokens = re.findall(r"[a-zA-Z]+", s)
    if not word_tokens:
        return True
    symbol_ratio = 1.0 - (sum(len(tok) for tok in word_tokens) / max(1, len(s)))
    if symbol_ratio >= 0.46 and len(word_tokens) <= 8:
        return True
    return False


def _looks_reference_entry_sentence(sentence: str) -> bool:
    s = str(sentence or "").strip()
    low = s.lower()
    if not s:
        return True
    if "doi.org" in low or re.search(r"\bdoi\s*[:/]", low):
        return True
    if re.match(r"^\s*\d+\.\s+[A-Z][^.!?]{5,}", s):
        return True
    if re.match(r"^[A-Z][a-zA-Z\-]+,\s*[A-Z]\.", s) and re.search(r"\(\d{4}[a-z]?\)", s):
        return True
    if re.search(r"\bet al\.\b", low) and re.search(r"\(\d{4}[a-z]?\)", s):
        return True
    if re.search(r"\(\d{4}[a-z]?\)\.?$", s) and re.search(r"\b\d{1,4}\s*[,:\u2013-]\s*\d{1,5}\b", s):
        return True
    if re.search(r"\(\d{4}[a-z]?\)\.?$", s):
        verb_like = re.search(
            r"\b(is|are|was|were|show|shows|showed|demonstrate|demonstrated|suggest|suggests|indicate|reported|observed)\b",
            low,
        )
        if not verb_like and len(s.split()) <= 16:
            return True
    if re.search(r"\b(chem\.|science|nature|proceedings|j\.|journal)\b", low) and re.search(r"\(\d{4}[a-z]?\)", low):
        if len(s.split()) <= 18:
            return True
    return False


def _looks_back_matter_sentence(sentence: str) -> bool:
    low = str(sentence or "").strip().lower()
    if not low:
        return True
    blocked = [
        "author contributions",
        "manuscript was written through contributions of all authors",
        "all authors have given approval",
        "competing interests",
        "conflict of interest",
        "corresponding author",
        "supplementary information",
        "acknowledg",
        "funding",
        "received:",
        "accepted:",
        "published:",
    ]
    return any(token in low for token in blocked)


def _is_reviewable_sentence(sentence: str, section: str) -> bool:
    s = str(sentence or "").strip()
    if not s:
        return False
    if section in {"front_matter", "references", "header_footer"}:
        return False
    if _looks_caption_or_artifact_sentence(s):
        return False
    if _looks_figure_table_reference_sentence(s):
        return False
    if _looks_reference_entry_sentence(s):
        return False
    if _looks_back_matter_sentence(s):
        return False
    if len(s.split()) < 4:
        return False
    return True


def segment_reviewable_sentences(paragraphs: list[str], section_by_idx: dict[int, str]) -> list[ReviewSentence]:
    out: list[ReviewSentence] = []
    for pidx, paragraph in enumerate(paragraphs):
        section = section_by_idx.get(pidx, "body")
        if not paragraph.strip():
            continue
        if section in {"front_matter", "references", "header_footer"}:
            continue
        sentences = _split_sentences(paragraph)
        for sidx, sentence in enumerate(sentences):
            if not _is_reviewable_sentence(sentence, section):
                continue
            sid = f"p{pidx:04d}.s{sidx:03d}"
            out.append(
                ReviewSentence(
                    sentence_id=sid,
                    paragraph_index=pidx,
                    sentence_index=sidx,
                    section=section,
                    text=sentence,
                )
            )
    return out


def classify_sentence(sentence: str, section: str) -> str:
    s = sentence.strip()
    low = s.lower()
    if not s:
        return SENTENCE_CATEGORY_STYLE_ONLY
    if _looks_caption_or_artifact_sentence(s):
        return SENTENCE_CATEGORY_STYLE_ONLY
    if _looks_figure_table_reference_sentence(s):
        return SENTENCE_CATEGORY_STYLE_ONLY
    if _looks_reference_entry_sentence(s):
        return SENTENCE_CATEGORY_STYLE_ONLY
    if _looks_back_matter_sentence(s):
        return SENTENCE_CATEGORY_STYLE_ONLY
    if _looks_citation_dense_fragment(s):
        return SENTENCE_CATEGORY_STYLE_ONLY
    if _word_count(s) <= 3:
        return SENTENCE_CATEGORY_STYLE_ONLY
    if low.startswith(("figure ", "fig. ", "table ", "supplementary")):
        return SENTENCE_CATEGORY_STYLE_ONLY
    has_citation = bool(re.search(r"\[[0-9,\-\u2013 ]+\]|\([12][0-9]{3}\)", s))
    has_first_person = _has_first_person_or_local_marker(s)
    has_local_marker = _has_manuscript_specific_marker(s)
    has_interpretive = _has_interpretive_marker(s)
    if has_local_marker or has_first_person:
        if has_interpretive and not any(k in low for k in ["yield", "conversion", "assay", "screen"]):
            return SENTENCE_CATEGORY_INTERPRETATION
        return SENTENCE_CATEGORY_MANUSCRIPT
    if has_citation and any(k in low for k in ["reported", "shown", "demonstrated", "according to", "previously", "prior", "literature"]):
        return SENTENCE_CATEGORY_LITERATURE
    if has_citation and not has_first_person:
        return SENTENCE_CATEGORY_LITERATURE
    if has_interpretive:
        return SENTENCE_CATEGORY_INTERPRETATION
    if any(k in low for k in ["is", "are", "has", "have"]) and section in {"introduction", "discussion", "conclusions"}:
        return SENTENCE_CATEGORY_PUBLIC
    if any(k in low for k in ["could", "might", "should", "would"]) and section in {"discussion", "conclusions"}:
        return SENTENCE_CATEGORY_INTERPRETATION
    if _word_count(s) < 8:
        return SENTENCE_CATEGORY_STYLE_ONLY
    return SENTENCE_CATEGORY_AMBIGUOUS


def _minimized_query(sentence: str) -> str:
    toks = _tokens(sentence)
    filtered = []
    blocked = {
        "this",
        "that",
        "these",
        "those",
        "with",
        "from",
        "into",
        "results",
        "result",
        "study",
        "work",
        "manuscript",
        "our",
        "we",
        "herein",
        "yield",
        "conversion",
        "assay",
        "dataset",
        "reaction",
        "array",
    }
    for tok in toks:
        if tok in blocked:
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", tok):
            continue
        if re.fullmatch(r"[a-z]?\d+[a-z]?", tok):
            continue
        filtered.append(tok)
    if not filtered:
        filtered = [t for t in toks if not re.fullmatch(r"\d+(?:\.\d+)?", t)]
    return " ".join(filtered[:6]).strip()


def privacy_gate(sentence: str, category: str) -> PrivacyDecision:
    low = str(sentence or "").lower()
    has_sensitive_local = _has_manuscript_specific_marker(sentence) or _has_first_person_or_local_marker(sentence)
    if has_sensitive_local and category not in {SENTENCE_CATEGORY_PUBLIC, SENTENCE_CATEGORY_LITERATURE}:
        return PrivacyDecision(False, "manuscript_specific_or_novel", None)
    if has_sensitive_local and category == SENTENCE_CATEGORY_LITERATURE:
        return PrivacyDecision(False, "literature_sentence_contains_local_markers", None)
    if category == SENTENCE_CATEGORY_PUBLIC:
        if has_sensitive_local:
            return PrivacyDecision(False, "public_sentence_contains_local_markers", None)
        return PrivacyDecision(True, "public_background_claim", _minimized_query(sentence))
    if category == SENTENCE_CATEGORY_LITERATURE:
        if _looks_citation_dense_fragment(sentence) or _looks_reference_entry_sentence(sentence):
            return PrivacyDecision(False, "citation_fragment_or_reference_line", None)
        return PrivacyDecision(True, "public_literature_claim", _minimized_query(sentence))
    if category == SENTENCE_CATEGORY_MANUSCRIPT:
        return PrivacyDecision(False, "manuscript_specific_or_novel", None)
    if category == SENTENCE_CATEGORY_INTERPRETATION:
        return PrivacyDecision(False, "interpretation_tied_to_local_results", None)
    if category == SENTENCE_CATEGORY_STYLE_ONLY:
        return PrivacyDecision(False, "non_factual_sentence", None)
    if category == SENTENCE_CATEGORY_AMBIGUOUS:
        has_citation = bool(re.search(r"\[[0-9,\-\u2013 ]+\]|\([12][0-9]{3}\)", sentence))
        manuscript_markers = [
            "we ",
            "our ",
            "in this study",
            "in this work",
            "herein",
            "yield",
            "conversion",
            "assay",
            "dataset",
            "reaction array",
        ]
        if has_citation and not any(marker in low for marker in manuscript_markers):
            if _looks_citation_dense_fragment(sentence) or _looks_reference_entry_sentence(sentence):
                return PrivacyDecision(False, "ambiguous_citation_fragment", None)
            return PrivacyDecision(True, "ambiguous_but_public_cited_claim", _minimized_query(sentence))
    return PrivacyDecision(False, "ambiguous_or_mixed_claim", None)


class LocalEvidenceRetriever:
    def __init__(self, corpora: list[tuple[str, str]]):
        self.corpora = corpora

    def retrieve(self, sentence: str, top_k: int = 3) -> list[EvidenceSnippet]:
        scored: list[tuple[float, str, str]] = []
        for source_name, chunk in self.corpora:
            overlap = _token_overlap(sentence, chunk)
            if overlap <= 0:
                continue
            scored.append((overlap, source_name, chunk.strip()))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            EvidenceSnippet(source="local", snippet=snippet[:320], score=round(score, 4), provenance=src)
            for score, src, snippet in scored[:top_k]
        ]


def _fallback_verdict(sentence: str, category: str, local_hits: list[EvidenceSnippet]) -> tuple[str, str, str, str | None]:
    low = sentence.lower()
    has_strong_quantifier = any(k in low for k in [" always ", " never ", " all ", " every ", " unequivocally ", " proves "])
    has_citation = bool(re.search(r"\[[0-9,\-\u2013 ]+\]|\([12][0-9]{3}\)", sentence))
    if category == SENTENCE_CATEGORY_STYLE_ONLY:
        return VERDICT_SUPPORTED, "No factual claim detected; no evidence check needed.", "none", None
    if category == SENTENCE_CATEGORY_LITERATURE and not re.search(r"\[[0-9,\-\u2013 ]+\]", sentence):
        return VERDICT_NEEDS_CITATION, "Literature-style claim lacks explicit citation in sentence.", "add citation", None
    if category == SENTENCE_CATEGORY_LITERATURE and has_citation:
        if local_hits:
            return VERDICT_PARTIALLY_SUPPORTED, "Claim has citation-style support; ensure citation directly matches the sentence.", "verify citation match", None
        return VERDICT_UNCLEAR_SUPPORT, "Citation marker present but local support remains unclear.", "verify citation match", None
    if category == SENTENCE_CATEGORY_MANUSCRIPT:
        return VERDICT_UNVERIFIABLE_MANUSCRIPT, "Claim appears manuscript-specific; verify against local figures/tables.", "verify locally", None
    if category == SENTENCE_CATEGORY_INTERPRETATION and has_strong_quantifier:
        return VERDICT_WORDING_STRONGER, "Interpretive wording is stronger than directly shown evidence.", "qualify claim", None
    if has_strong_quantifier:
        return VERDICT_LIKELY_OVERCLAIM, "High-certainty wording appears broader than available support.", "narrow claim", None
    if category == SENTENCE_CATEGORY_PUBLIC and has_citation and local_hits:
        return VERDICT_PARTIALLY_SUPPORTED, "Sentence has citation cue and some local support; keep wording matched to source scope.", "verify citation match", None
    if category == SENTENCE_CATEGORY_AMBIGUOUS and local_hits and local_hits[0].score >= 0.18:
        return VERDICT_PARTIALLY_SUPPORTED, "Some local support found for mixed claim; tighten wording and add direct source.", "add citation", None
    if local_hits and local_hits[0].score >= 0.26:
        return VERDICT_PARTIALLY_SUPPORTED, "Some local support found; tighten wording or add explicit citation.", "add citation", None
    return VERDICT_UNCLEAR_SUPPORT, "Support remains unclear from available local evidence.", "add citation", None


def _parse_verdict(value: str) -> str:
    low = str(value or "").strip().lower()
    mapping = {
        "supported": VERDICT_SUPPORTED,
        "partially supported": VERDICT_PARTIALLY_SUPPORTED,
        "unclear support": VERDICT_UNCLEAR_SUPPORT,
        "likely overclaim": VERDICT_LIKELY_OVERCLAIM,
        "needs citation": VERDICT_NEEDS_CITATION,
        "unverifiable externally because manuscript-specific": VERDICT_UNVERIFIABLE_MANUSCRIPT,
        "wording stronger than evidence": VERDICT_WORDING_STRONGER,
    }
    return mapping.get(low, VERDICT_UNCLEAR_SUPPORT)


def _llm_claim_check(
    provider: Provider,
    model: str,
    sentence: str,
    category: str,
    privacy: PrivacyDecision,
    local_hits: list[EvidenceSnippet],
    external_hits: list[EvidenceSnippet],
    timeout_seconds: int,
) -> tuple[str, str, str, str | None]:
    payload = {
        "sentence": sentence,
        "category": category,
        "privacy": {
            "safe_for_external_search": privacy.safe_for_external_search,
            "reason": privacy.reason,
        },
        "local_evidence": [{"snippet": x.snippet, "score": x.score, "provenance": x.provenance} for x in local_hits],
        "external_evidence": [{"snippet": x.snippet, "score": x.score, "provenance": x.provenance} for x in external_hits],
    }
    system_prompt = (
        "You are a sentence-level factual accuracy checker for scientific manuscripts. "
        "Process one sentence at a time. Return ONLY JSON with keys: "
        "atomic_claim, verdict, feedback, action, rewrite. "
        "Verdict must be one of: supported, partially supported, unclear support, likely overclaim, "
        "needs citation, unverifiable externally because manuscript-specific, wording stronger than evidence. "
        "Keep feedback concise and actionable."
    )
    user_prompt = json.dumps(payload, ensure_ascii=False)
    resp = provider.chat(
        ChatRequest(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=350,
            timeout_seconds=timeout_seconds,
            metadata={"purpose": "sentence_claim_check"},
        )
    )
    parsed = json.loads(extract_json_candidate(resp.content) or resp.content)
    verdict = _parse_verdict(str(parsed.get("verdict", "")))
    feedback = str(parsed.get("feedback", "")).strip() or "Sentence needs a clearer evidence boundary."
    action = str(parsed.get("action", "")).strip() or "qualify claim"
    rewrite = str(parsed.get("rewrite", "")).strip() or None
    return verdict, feedback, action, rewrite


def _select_claim_check_model(provider: Provider | None, fallback_model: str | None) -> tuple[str | None, bool]:
    if provider is None:
        return None, False
    try:
        installed = set(provider.list_models())
    except Exception:
        installed = set()
    if "gemma4:31b" in installed:
        return "gemma4:31b", True
    return fallback_model, False


def _local_corpora_for_claim_check(paragraphs: list[str], supporting_cards: list[dict[str, Any]] | None) -> list[tuple[str, str]]:
    corpora: list[tuple[str, str]] = []
    for idx, paragraph in enumerate(paragraphs):
        if paragraph.strip():
            corpora.append((f"paragraph:{idx}", paragraph.strip()))
    for idx, card in enumerate(supporting_cards or []):
        parts = []
        for key in ("title", "snippet", "content", "text", "summary"):
            value = card.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
        merged = " ".join(parts).strip()
        if merged:
            corpora.append((f"supporting_card:{idx}", merged))
    return corpora


def run_sentence_claim_check(
    paragraphs: list[str],
    section_by_idx: dict[int, str],
    provider: Provider | None,
    model: str | None,
    timeout_seconds: int,
    supporting_cards: list[dict[str, Any]] | None = None,
    external_search_enabled: bool = False,
    external_provider: ExternalSearchProvider | None = None,
) -> dict[str, Any]:
    sentences = segment_reviewable_sentences(paragraphs, section_by_idx)
    local_retriever = LocalEvidenceRetriever(_local_corpora_for_claim_check(paragraphs, supporting_cards))
    selected_model, gemma_used = _select_claim_check_model(provider, model)
    llm_available = provider is not None and selected_model is not None
    llm_enabled = llm_available
    llm_fail_fast_triggered = False
    llm_timeout_seconds = max(8, min(int(timeout_seconds), 35))
    llm_attempted_count = 0
    llm_success_count = 0
    llm_failure_count = 0
    results: list[SentenceCheckResult] = []
    verdict_counts: dict[str, int] = {k: 0 for k in SUPPORTED_VERDICTS}
    category_counts: dict[str, int] = {}
    local_only_count = 0
    external_eligible_count = 0
    external_used_count = 0
    search_layer_status = "disabled"
    if external_search_enabled and external_provider is not None:
        search_layer_status = "mocked" if getattr(external_provider, "name", "") == "mock" else "active"
    for sent in sentences:
        category = classify_sentence(sent.text, sent.section)
        category_counts[category] = category_counts.get(category, 0) + 1
        privacy = privacy_gate(sent.text, category)
        local_hits = local_retriever.retrieve(sent.text, top_k=3)
        external_hits: list[EvidenceSnippet] = []
        used_external = False
        if privacy.safe_for_external_search:
            external_eligible_count += 1
            if external_search_enabled and external_provider is not None and privacy.minimized_query:
                external_hits = external_provider.search(privacy.minimized_query, top_k=3)
                used_external = True
                external_used_count += 1
        if not used_external:
            local_only_count += 1
        if llm_enabled:
            try:
                llm_attempted_count += 1
                verdict, feedback, action, rewrite = _llm_claim_check(
                    provider=provider,  # type: ignore[arg-type]
                    model=selected_model,  # type: ignore[arg-type]
                    sentence=sent.text,
                    category=category,
                    privacy=privacy,
                    local_hits=local_hits,
                    external_hits=external_hits,
                    timeout_seconds=llm_timeout_seconds,
                )
                llm_success_count += 1
                fallback_used = False
            except Exception:
                llm_failure_count += 1
                verdict, feedback, action, rewrite = _fallback_verdict(sent.text, category, local_hits)
                fallback_used = True
                llm_enabled = False
                llm_fail_fast_triggered = True
        else:
            verdict, feedback, action, rewrite = _fallback_verdict(sent.text, category, local_hits)
            fallback_used = True
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        results.append(
            SentenceCheckResult(
                sentence_id=sent.sentence_id,
                paragraph_index=sent.paragraph_index,
                sentence_text=sent.text,
                section=sent.section,
                category=category,
                privacy=privacy,
                verdict=verdict,
                feedback=feedback,
                action=action,
                rewrite=rewrite,
                local_evidence=local_hits,
                external_evidence=external_hits,
                used_external_search=used_external,
                model_used=selected_model if llm_available else None,
                fallback_used=fallback_used,
            )
        )
    return {
        "search_layer": {
            "enabled": external_search_enabled,
            "status": search_layer_status,
            "provider": getattr(external_provider, "name", None),
        },
        "model": {
            "selected_model": selected_model,
            "gemma4_31b_used": gemma_used and llm_available,
            "fallback_used": not llm_available or any(item.fallback_used for item in results),
            "fail_fast_fallback_triggered": llm_fail_fast_triggered,
            "llm_timeout_seconds": llm_timeout_seconds,
            "llm_attempted_count": llm_attempted_count,
            "llm_success_count": llm_success_count,
            "llm_failure_count": llm_failure_count,
        },
        "summary": {
            "sentences_checked": len(results),
            "category_counts": category_counts,
            "local_only_count": local_only_count,
            "external_eligible_count": external_eligible_count,
            "external_used_count": external_used_count,
            "verdict_counts": verdict_counts,
        },
        "sentences": [
            {
                "sentence_id": item.sentence_id,
                "paragraph_index": item.paragraph_index,
                "section": item.section,
                "sentence_text": item.sentence_text,
                "category": item.category,
                "privacy": {
                    "safe_for_external_search": item.privacy.safe_for_external_search,
                    "reason": item.privacy.reason,
                    "minimized_query": item.privacy.minimized_query,
                },
                "verdict": item.verdict,
                "feedback": item.feedback,
                "action": item.action,
                "rewrite": item.rewrite,
                "local_evidence": [
                    {"snippet": ev.snippet, "score": ev.score, "provenance": ev.provenance}
                    for ev in item.local_evidence
                ],
                "external_evidence": [
                    {"snippet": ev.snippet, "score": ev.score, "provenance": ev.provenance}
                    for ev in item.external_evidence
                ],
                "used_external_search": item.used_external_search,
                "model_used": item.model_used,
                "fallback_used": item.fallback_used,
            }
            for item in results
        ],
    }


def _rewrite_materially_useful(original: str, rewrite: str | None) -> bool:
    if not rewrite:
        return False
    src = _normalize(original)
    dst = _normalize(rewrite)
    if not src or not dst or src == dst:
        return False
    if len(src.split()) >= 5 and len(dst.split()) < 4:
        return False
    ratio = difflib.SequenceMatcher(None, src, dst).ratio()
    if ratio >= 0.93:
        return False
    return True


def _suggestion_from_action(action: str, verdict: str, category: str) -> str:
    low = str(action or "").strip().lower()
    if "citation" in low or verdict == VERDICT_NEEDS_CITATION:
        return "Add a citation directly after this sentence."
    if "narrow" in low:
        return "Narrow this claim to the tested scope."
    if "qualify" in low:
        return "Qualify this sentence to match the evidence."
    if "verify locally" in low or verdict == VERDICT_UNVERIFIABLE_MANUSCRIPT:
        return "Anchor this sentence to a local figure/table value."
    if verdict == VERDICT_UNCLEAR_SUPPORT and category in {
        SENTENCE_CATEGORY_PUBLIC,
        SENTENCE_CATEGORY_LITERATURE,
    }:
        return "Cite the source that directly supports this sentence."
    if "none" in low:
        return ""
    return "Add direct support or soften the claim."


def _claim_signal_score(row: dict[str, Any]) -> int:
    sentence = str(row.get("sentence_text", "")).strip()
    verdict = str(row.get("verdict", "")).strip()
    category = str(row.get("category", "")).strip()
    low = sentence.lower()
    score = 0
    if verdict in {VERDICT_LIKELY_OVERCLAIM, VERDICT_WORDING_STRONGER}:
        score += 6
    elif verdict == VERDICT_NEEDS_CITATION:
        score += 4
    elif verdict == VERDICT_UNVERIFIABLE_MANUSCRIPT:
        score += 3
    elif verdict == VERDICT_UNCLEAR_SUPPORT:
        score += 2
    if re.search(r"\b(always|never|all|every|perfect|fully)\b", low):
        score += 2
    if re.search(r"\b\d+%|\byield\b|\bconversion\b|\bimprov(ed|e|es)\b|\bdecreas(ed|e|es)\b", low):
        score += 1
    if category in {SENTENCE_CATEGORY_PUBLIC, SENTENCE_CATEGORY_LITERATURE, SENTENCE_CATEGORY_INTERPRETATION}:
        score += 1
    if _word_count(sentence) >= 12:
        score += 1
    return score


def _claim_row_suppression_reason(row: dict[str, Any]) -> str | None:
    sentence = str(row.get("sentence_text", "")).strip()
    verdict = str(row.get("verdict", "")).strip()
    category = str(row.get("category", "")).strip()
    section = str(row.get("section", "")).strip().lower()
    low = sentence.lower()
    if not sentence:
        return "empty_sentence"
    if verdict in {VERDICT_SUPPORTED, VERDICT_PARTIALLY_SUPPORTED}:
        return "verdict_not_actionable"
    if _looks_reference_entry_sentence(sentence):
        return "reference_like_sentence"
    if _looks_caption_or_artifact_sentence(sentence) or _looks_figure_table_reference_sentence(sentence):
        return "figure_table_or_artifact_line"
    if _looks_back_matter_sentence(sentence):
        return "back_matter_sentence"
    if category == SENTENCE_CATEGORY_STYLE_ONLY:
        return "non_factual_category"
    if _looks_citation_dense_fragment(sentence):
        return "citation_dense_fragment"
    if _looks_low_information_sentence(sentence):
        return "low_information_sentence"
    if verdict == VERDICT_NEEDS_CITATION and _citation_marker_count(sentence) >= 1:
        return "already_citation_context"
    if verdict in {VERDICT_UNCLEAR_SUPPORT, VERDICT_NEEDS_CITATION} and category in {
        SENTENCE_CATEGORY_MANUSCRIPT,
        SENTENCE_CATEGORY_AMBIGUOUS,
    }:
        return "low_signal_for_local_or_ambiguous_claim"
    if verdict in {VERDICT_LIKELY_OVERCLAIM, VERDICT_WORDING_STRONGER}:
        if sentence.endswith("?") and " we " not in f" {low} " and " our " not in f" {low} ":
            return "question_like_or_title_fragment"
    if verdict == VERDICT_UNVERIFIABLE_MANUSCRIPT:
        if section in {"methods", "introduction"}:
            return "manuscript_specific_methods_or_background"
        if not re.search(
            r"\b\d+%|\byield\b|\bconversion\b|\bimprove[sd]?\b|\bdecrease[sd]?\b|\bfirst attempt\b|\btable\b|\bfigure\b",
            low,
        ):
            return "manuscript_specific_not_actionable"
    return None


def _claim_check_entry_from_row(row: dict[str, Any]) -> dict[str, Any]:
    verdict = str(row.get("verdict", ""))
    category = str(row.get("category", ""))
    sentence = str(row.get("sentence_text", "")).strip()
    if verdict in {VERDICT_LIKELY_OVERCLAIM, VERDICT_WORDING_STRONGER}:
        issue_type = "evidence/overclaim"
        severity = "high"
    else:
        issue_type = "wording/precision"
        severity = "medium"

    feedback = re.sub(r"\s+", " ", str(row.get("feedback", "")).strip())
    if feedback and feedback[-1] not in ".!?":
        feedback += "."
    suggestion = _suggestion_from_action(str(row.get("action", "")), verdict, category)
    rewrite = str(row.get("rewrite", "")).strip() or None
    if _rewrite_materially_useful(sentence, rewrite):
        suggestion = f"Proposed edit: {rewrite}"
    return {
        "comment_id": f"claim_{str(row.get('sentence_id', 's')).replace('.', '_')}",
        "paragraph_index": int(row.get("paragraph_index", 0)),
        "issue_type": issue_type,
        "severity": severity,
        "critique": (feedback or "Evidence support is unclear for this sentence.")[:180],
        "suggested_revision": suggestion[:180],
        "rationale": f"Sentence-level factual check verdict: {verdict}.",
        "anchor_text": sentence[:300],
        "span_sentence": sentence[:300],
        "priority_score": (
            7
            if verdict in {VERDICT_LIKELY_OVERCLAIM, VERDICT_WORDING_STRONGER}
            else 6 if verdict == VERDICT_NEEDS_CITATION else 5 if verdict == VERDICT_UNVERIFIABLE_MANUSCRIPT else 4
        ),
        "claim_check_verdict": verdict,
        "privacy_check": row.get("privacy", {}),
        "from_claim_check": True,
    }


def project_claim_check_comments(claim_check_manifest: dict[str, Any], max_comments: int = 12) -> dict[str, Any]:
    sentence_rows = claim_check_manifest.get("sentences", [])
    if not isinstance(sentence_rows, list):
        return {
            "entries": [],
            "summary": {
                "row_count": 0,
                "candidate_count": 0,
                "surfaced_count": 0,
                "suppressed_count": 0,
                "suppressed_reason_counts": {},
                "high_value_surfaced_count": 0,
                "low_value_surfaced_count": 0,
            },
            "suppressed_examples": {},
        }

    candidates: list[dict[str, Any]] = []
    suppressed_reason_counts: dict[str, int] = {}
    suppressed_examples: dict[str, list[str]] = {}
    for raw in sentence_rows:
        if not isinstance(raw, dict):
            continue
        reason = _claim_row_suppression_reason(raw)
        if reason:
            suppressed_reason_counts[reason] = suppressed_reason_counts.get(reason, 0) + 1
            sid = str(raw.get("sentence_id", "")).strip() or "unknown_sentence"
            suppressed_examples.setdefault(reason, [])
            if len(suppressed_examples[reason]) < 5:
                suppressed_examples[reason].append(sid)
            continue
        score = _claim_signal_score(raw)
        row = dict(raw)
        row["_claim_signal_score"] = score
        candidates.append(row)

    verdict_rank = {
        VERDICT_LIKELY_OVERCLAIM: 0,
        VERDICT_WORDING_STRONGER: 1,
        VERDICT_NEEDS_CITATION: 2,
        VERDICT_UNVERIFIABLE_MANUSCRIPT: 3,
        VERDICT_UNCLEAR_SUPPORT: 4,
    }
    candidates_sorted = sorted(
        candidates,
        key=lambda row: (
            verdict_rank.get(str(row.get("verdict", "")), 9),
            -int(row.get("_claim_signal_score", 0)),
            int(row.get("paragraph_index", 10**6)),
        ),
    )
    # Keep a balanced mix across verdict families and paragraphs.
    verdict_caps = {
        VERDICT_LIKELY_OVERCLAIM: 4,
        VERDICT_WORDING_STRONGER: 4,
        VERDICT_NEEDS_CITATION: 3,
        VERDICT_UNVERIFIABLE_MANUSCRIPT: 3,
        VERDICT_UNCLEAR_SUPPORT: 2,
    }
    verdict_used: dict[str, int] = {}
    paragraph_used: dict[int, int] = {}
    paragraph_verdicts: dict[int, set[str]] = {}
    surfaced: list[dict[str, Any]] = []
    for row in candidates_sorted:
        if len(surfaced) >= max_comments:
            break
        verdict = str(row.get("verdict", ""))
        pidx = int(row.get("paragraph_index", 0))
        if verdict_used.get(verdict, 0) >= verdict_caps.get(verdict, 2):
            suppressed_reason_counts["verdict_cap_reached"] = suppressed_reason_counts.get("verdict_cap_reached", 0) + 1
            continue
        seen_verdicts = paragraph_verdicts.get(pidx, set())
        if verdict in seen_verdicts:
            suppressed_reason_counts["paragraph_duplicate_verdict"] = (
                suppressed_reason_counts.get("paragraph_duplicate_verdict", 0) + 1
            )
            continue
        if paragraph_used.get(pidx, 0) >= 2:
            suppressed_reason_counts["paragraph_claim_comment_cap_reached"] = (
                suppressed_reason_counts.get("paragraph_claim_comment_cap_reached", 0) + 1
            )
            continue
        entry = _claim_check_entry_from_row(row)
        surfaced.append(entry)
        verdict_used[verdict] = verdict_used.get(verdict, 0) + 1
        paragraph_used[pidx] = paragraph_used.get(pidx, 0) + 1
        paragraph_verdicts.setdefault(pidx, set()).add(verdict)

    high_value_surfaced = 0
    for entry in surfaced:
        verdict = str(entry.get("claim_check_verdict", "")).strip()
        if verdict in {VERDICT_LIKELY_OVERCLAIM, VERDICT_WORDING_STRONGER, VERDICT_NEEDS_CITATION}:
            high_value_surfaced += 1

    return {
        "entries": surfaced,
        "summary": {
            "row_count": len(sentence_rows),
            "candidate_count": len(candidates),
            "surfaced_count": len(surfaced),
            "suppressed_count": sum(suppressed_reason_counts.values()),
            "suppressed_reason_counts": suppressed_reason_counts,
            "high_value_surfaced_count": high_value_surfaced,
            "low_value_surfaced_count": max(0, len(surfaced) - high_value_surfaced),
        },
        "suppressed_examples": suppressed_examples,
    }


def claim_check_results_to_comment_entries(claim_check_manifest: dict[str, Any], max_comments: int = 12) -> list[dict[str, Any]]:
    projection = project_claim_check_comments(claim_check_manifest, max_comments=max_comments)
    return list(projection.get("entries", []))


def render_sentence_claim_check_summary_markdown(claim_check_manifest: dict[str, Any]) -> str:
    summary = claim_check_manifest.get("summary", {}) if isinstance(claim_check_manifest, dict) else {}
    model_meta = claim_check_manifest.get("model", {}) if isinstance(claim_check_manifest, dict) else {}
    search_layer = claim_check_manifest.get("search_layer", {}) if isinstance(claim_check_manifest, dict) else {}
    projection = claim_check_manifest.get("comment_projection", {}) if isinstance(claim_check_manifest, dict) else {}
    projection_summary = projection.get("summary", {}) if isinstance(projection, dict) else {}
    suppressed_examples = projection.get("suppressed_examples", {}) if isinstance(projection, dict) else {}

    lines = [
        "# Sentence Claim-Check Summary",
        "",
        f"- Sentences checked: {int(summary.get('sentences_checked', 0) or 0)}",
        f"- Local-only count: {int(summary.get('local_only_count', 0) or 0)}",
        f"- External-eligible count: {int(summary.get('external_eligible_count', 0) or 0)}",
        f"- External-used count: {int(summary.get('external_used_count', 0) or 0)}",
        f"- Search layer status: {search_layer.get('status', 'unknown')}",
        f"- Model selected: {model_meta.get('selected_model')}",
        f"- Gemma4 used: {bool(model_meta.get('gemma4_31b_used', False))}",
        f"- Fallback used: {bool(model_meta.get('fallback_used', False))}",
        f"- Fail-fast fallback triggered: {bool(model_meta.get('fail_fast_fallback_triggered', False))}",
        "",
        "## Category Counts",
    ]
    category_counts = summary.get("category_counts", {}) if isinstance(summary, dict) else {}
    if isinstance(category_counts, dict) and category_counts:
        for key, value in sorted(category_counts.items(), key=lambda kv: str(kv[0])):
            lines.append(f"- {key}: {int(value)}")
    else:
        lines.append("- none")

    lines.extend(["", "## Verdict Counts"])
    verdict_counts = summary.get("verdict_counts", {}) if isinstance(summary, dict) else {}
    if isinstance(verdict_counts, dict) and verdict_counts:
        for key, value in sorted(verdict_counts.items(), key=lambda kv: str(kv[0])):
            lines.append(f"- {key}: {int(value)}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Comment Projection",
            f"- Candidate claim-check rows: {int(projection_summary.get('candidate_count', 0) or 0)}",
            f"- Surfaced comments: {int(projection_summary.get('surfaced_count', 0) or 0)}",
            f"- Suppressed rows: {int(projection_summary.get('suppressed_count', 0) or 0)}",
            f"- High-value surfaced: {int(projection_summary.get('high_value_surfaced_count', 0) or 0)}",
            f"- Low-value surfaced: {int(projection_summary.get('low_value_surfaced_count', 0) or 0)}",
        ]
    )
    reasons = projection_summary.get("suppressed_reason_counts", {}) if isinstance(projection_summary, dict) else {}
    lines.append("")
    lines.append("### Suppression Reasons")
    if isinstance(reasons, dict) and reasons:
        for key, value in sorted(reasons.items(), key=lambda kv: str(kv[0])):
            lines.append(f"- {key}: {int(value)}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("### Suppressed Examples")
    if isinstance(suppressed_examples, dict) and suppressed_examples:
        for key, values in sorted(suppressed_examples.items(), key=lambda kv: str(kv[0])):
            if not isinstance(values, list) or not values:
                continue
            lines.append(f"- {key}: {', '.join(str(v) for v in values[:5])}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)
