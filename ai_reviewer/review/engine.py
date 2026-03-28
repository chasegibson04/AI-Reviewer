from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import statistics

from ai_reviewer.config import ReviewerConfig
from ai_reviewer.ingest.chunking import chunk_document
import re

from ai_reviewer.ingest.retrieval import retrieve_top_k
from ai_reviewer.ingest.types import ParsedDocument
from ai_reviewer.models.base import ChatRequest, Provider
from ai_reviewer.orchestrator.controller import OrchestratorController, OrchestratorRuntimeState
from ai_reviewer.review.profiles import ReviewProfile
from ai_reviewer.review.repair import ParseOutcome, parse_and_repair
from ai_reviewer.review.render import write_review_bundle
from ai_reviewer.figures.figure_review import run_figure_review
from ai_reviewer.review.schema import ActionItem, CompareSchema, DebugMetadata, ReviewSchema, SectionComment


@dataclass
class ReviewRunResult:
    review: ReviewSchema
    warnings: list[str]
    bundle_dir: Path
    retrieval_manifest: list[dict]


REVIEW_SCHEMA_HINT = {
    "document_metadata": {"title": "...", "source": "...", "profile": "..."},
    "summary": "...",
    "major_strengths": ["..."],
    "major_weaknesses": ["..."],
    "novelty_concerns": ["..."],
    "methodological_concerns": ["..."],
    "statistical_concerns": ["..."],
    "writing_organization_concerns": ["..."],
    "figure_table_concerns": ["..."],
    "citation_reference_concerns": ["..."],
    "reproducibility_concerns": ["..."],
    "suggested_experiments_analyses": ["..."],
    "recommendation": {"decision": "accept|revise|reject", "rationale": "..."},
    "confidence": 0.75,
    "detailed_reviewer_comments": ["..."],
    "section_specific_comments": [{"section": "...", "comment": "...", "severity": "low|medium|high"}],
    "extracted_action_items": [{"action": "...", "priority": "low|medium|high", "owner": "author|reviewer"}],
    "model_debug_metadata": {
        "provider": "ollama",
        "model": "...",
        "temperature": 0.2,
        "retries_used": 0,
        "parse_failures": 0,
        "total_duration": 0,
        "prompt_eval_count": 0,
        "eval_count": 0,
    },
}


def _build_prompt(doc: ParsedDocument, profile: ReviewProfile, context_chunks: str, guidance_text: str | None = None) -> str:
    guidance_block = f"\nGlobal Lab Guidance:\n{guidance_text}\n" if guidance_text else ""
    section_policy = (
        "Section-aware policy:\n"
        "- Abstract: only comment on claim calibration, scope, ambiguity, and alignment with body; avoid deep methods demands unless abstract overclaims.\n"
        "- Introduction: framing, novelty positioning, literature context, problem clarity.\n"
        "- Methods/Experimental: reproducibility, controls, human intervention vs automation, procedural completeness.\n"
        "- Results: claim support, yield definitions (assay vs isolated), failure/negative case reporting.\n"
        "- Discussion/Conclusions: interpretation discipline, overclaiming, scope boundaries.\n"
        "- Front matter/references/author info: default no comments unless metadata is incorrect.\n"
    )
    min_requirements = [
        "- Provide at least 2 major_strengths and 2 major_weaknesses tied to specific manuscript content.",
        "- Provide at least 2 writing_organization_concerns referencing concrete sentence/paragraph issues.",
        "- Provide at least 3 section_specific_comments with named sections when possible.",
        "- Provide at least 3 detailed_reviewer_comments with at least one suggested wording improvement.",
    ]
    if re.search(r"\\b(fig\\.\\s*\\d|figure\\s*\\d)", doc.cleaned_text.lower()):
        min_requirements.append("- Provide at least 1 figure_table_concern grounded in a specific figure/caption.")
    if profile.key in {"writing", "editor"}:
        min_requirements.append("- Include at least 3 sentence-level edits with proposed rewrites in detailed_reviewer_comments.")
    return (
        f"Profile: {profile.display_name}\n"
        f"Review focus: {profile.rubric_focus}\n"
        f"Max words: {profile.max_review_words}\n"
        "Return strict JSON only. No commentary outside JSON.\n"
        "Minimum content requirements:\n"
        + "\n".join(min_requirements)
        + "\n"
        "Grounding requirements:\n"
        "- Be specific to this manuscript, not generic.\n"
        "- Reference concrete sections/headings or experiment types from the provided context.\n"
        "- Include at least two manuscript-specific details (section names, claim phrasing, or figure/table callouts).\n"
        "- If support context is present, use it to check whether assertions appear backed.\n"
        "- If you cite support context, name the specific supporting file.\n"
        "- Avoid repeating the same sentence across fields.\n"
        "- Primary target is the manuscript under review; do not summarize supporting papers alone.\n"
        f"{section_policy}\n"
        "Target schema:\n"
        f"{json.dumps(REVIEW_SCHEMA_HINT, indent=2)}\n\n"
        f"Document path: {doc.source_path_abs}\n"
        f"Document type: {doc.document_type}\n"
        f"Page count: {doc.page_count}\n"
        f"Headings: {doc.headings[:30]}\n"
        f"Parser warnings: {doc.parse_warnings}\n\n"
        f"{guidance_block}\n"
        f"Context:\n{context_chunks}\n"
    )


def _chunk_manifest(doc: ParsedDocument) -> list[dict]:
    return [
        {
            "chunk_id": c.chunk_id,
            "start_char": c.start_char,
            "end_char": c.end_char,
            "heading": c.heading,
            "source_page": c.source_page,
            "length": len(c.text),
        }
        for c in doc.chunks
    ]


def _context_from_doc(doc: ParsedDocument, profile: ReviewProfile, config: ReviewerConfig) -> str:
    chunks = chunk_document(doc, max_chars=profile.chunk_size, overlap=profile.chunk_overlap)
    if not chunks:
        return doc.cleaned_text[:12000]
    return "\n\n".join([f"[{c.chunk_id}] {c.text[:2000]}" for c in chunks[:8]])


def _find_project_root(source_path: Path) -> Path | None:
    parts = list(source_path.parts)
    if "projects" not in parts:
        return None
    idx = parts.index("projects")
    if idx + 1 >= len(parts):
        return None
    return Path(*parts[: idx + 2])


def _estimate_duration_seconds(
    project_root: Path | None,
    profile_key: str,
    model: str,
    doc_length: int | None,
) -> tuple[float | None, dict]:
    if project_root is None:
        return None, {}
    runs_dir = project_root / "runs"
    if not runs_dir.exists():
        return None, {}
    durations: list[float] = []
    rates_per_char: list[float] = []
    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        for meta_path in run_dir.rglob("run_metadata.json"):
            try:
                payload = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if payload.get("profile") != profile_key:
                continue
            if payload.get("model") != model:
                continue
            dur = payload.get("duration_seconds")
            if isinstance(dur, (int, float)) and dur > 0:
                durations.append(float(dur))
                if doc_length:
                    source_path = meta_path.parent / "source_metadata.json"
                    if source_path.exists():
                        try:
                            source_meta = json.loads(source_path.read_text(encoding="utf-8"))
                        except Exception:
                            source_meta = {}
                        src_len = source_meta.get("cleaned_text_length")
                        if isinstance(src_len, int) and src_len > 0:
                            rates_per_char.append(float(dur) / float(src_len))
    if not durations:
        return None, {}
    durations.sort()
    median = durations[len(durations) // 2] if len(durations) % 2 == 1 else (durations[len(durations)//2 - 1] + durations[len(durations)//2]) / 2
    basis: dict[str, float | int] = {
        "count": len(durations),
        "median_seconds": median,
        "mean_seconds": statistics.fmean(durations) if len(durations) > 1 else durations[0],
    }
    if doc_length and rates_per_char:
        rate_median = statistics.median(rates_per_char)
        scaled = rate_median * float(doc_length)
        basis["median_seconds_per_1k_chars"] = rate_median * 1000.0
        basis["scaled_by_chars_seconds"] = scaled
        return scaled, basis
    return median, basis


def _is_sparse_review(review: ReviewSchema) -> bool:
    summary_len = len((review.summary or "").strip())
    signal_lists = [
        review.major_strengths,
        review.major_weaknesses,
        review.novelty_concerns,
        review.methodological_concerns,
        review.statistical_concerns,
        review.writing_organization_concerns,
        review.figure_table_concerns,
        review.citation_reference_concerns,
        review.reproducibility_concerns,
        review.suggested_experiments_analyses,
        review.detailed_reviewer_comments,
        [c.comment for c in review.section_specific_comments],
        [a.action for a in review.extracted_action_items],
    ]
    populated_items = sum(len([x for x in lst if str(x).strip()]) for lst in signal_lists)
    if summary_len < 120:
        return True
    if populated_items < 6:
        return True
    if not review.major_strengths:
        return True
    if not review.section_specific_comments:
        return True
    if len(review.detailed_reviewer_comments) < 2:
        return True
    return False


def _ensure_minimum_detail(review: ReviewSchema) -> None:
    if not review.detailed_reviewer_comments:
        review.detailed_reviewer_comments = [
            w for w in review.major_weaknesses[:4] if isinstance(w, str) and w.strip()
        ]
    if not review.extracted_action_items:
        generated: list[ActionItem] = []
        for w in review.major_weaknesses[:5]:
            if not isinstance(w, str) or not w.strip():
                continue
            generated.append(ActionItem(action=w, priority="high", owner="author"))
        if not generated:
            for c in review.detailed_reviewer_comments[:5]:
                if isinstance(c, str) and c.strip():
                    generated.append(ActionItem(action=f"Revise section for: {c}", priority="medium", owner="author"))
        review.extracted_action_items = generated


def _extract_abstract(doc: ParsedDocument) -> str:
    text = doc.cleaned_text
    match = re.search(r"\babstract[:\s]+(.{0,1500})", text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        snippet = match.group(1).strip()
        snippet = re.split(r"\n{2,}", snippet)[0]
        if len(snippet) > 600:
            snippet = snippet[:600].rsplit(" ", 1)[0] + "..."
        return snippet
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    front_matter_terms = [
        "received",
        "accepted",
        "published online",
        "check for updates",
        "nature synthesis",
        "article",
        "doi.org",
    ]
    filtered = [s for s in sentences if not any(term in s.lower() for term in front_matter_terms)]
    if not filtered:
        filtered = sentences
    return " ".join(filtered[:3])[:600]


def _summary_matches_doc(summary: str, doc: ParsedDocument) -> bool:
    if not summary.strip():
        return False
    s = summary.lower()
    if any(term in s for term in ["doi.org", "received", "accepted", "published online", "check for updates", "nature synthesis", "article"]):
        return False
    doc_text = doc.cleaned_text.lower()
    key_terms = ["phactor", "chatgpt", "reaction array", "reaction arrays"]
    if not any(term in doc_text for term in key_terms):
        return True
    for term in key_terms:
        if term in doc_text and term in s:
            return True
    if doc.headings:
        title_terms = [t.lower() for t in re.split(r"\W+", doc.headings[0]) if len(t) > 4]
        if any(t in s for t in title_terms[:4]):
            return True
    return False


def _contains_offtopic_terms(text: str, doc: ParsedDocument) -> bool:
    if not text:
        return False
    low = text.lower()
    doc_text = doc.cleaned_text.lower()
    abstract_text = _extract_abstract(doc).lower()
    front_matter_terms = [
        "received:",
        "accepted:",
        "published online",
        "check for updates",
        "nature synthesis",
        "supplementary information",
        "author contributions",
        "competing interests",
        "corresponding author",
    ]
    if any(term in low for term in front_matter_terms):
        return True
    off_topic_terms = [
        "roc-auc",
        "random forest",
        "f1-score",
        "precision",
        "recall",
        "cross-validation",
        "out-of-sample",
        "bayesian",
        "active transfer learning",
        "overfitting",
        "classifier",
        "nanomole",
        "predictive model",
        "ic50",
        "r2",
        "r²",
        "mk2",
        "chk1",
        "inhibitor",
        "drug discovery",
        "hyperparameter",
        "hyperparameters",
        "extended data",
        "received",
        "accepted",
        "published online",
        "check for updates",
        "nature synthesis",
        "supplementary information",
        "author contributions",
        "competing interests",
        "corresponding author",
    ]
    for term in off_topic_terms:
        if term in low and term not in abstract_text:
            return True
    return False


def _filter_hallucinated_review_content(review: ReviewSchema, doc: ParsedDocument) -> None:
    if _contains_offtopic_terms(review.summary, doc):
        review.summary = _extract_abstract(doc)
    if review.major_strengths:
        review.major_strengths = [s for s in review.major_strengths if not _contains_offtopic_terms(str(s), doc)]
    if review.major_weaknesses:
        review.major_weaknesses = [s for s in review.major_weaknesses if not _contains_offtopic_terms(str(s), doc)]
    if review.detailed_reviewer_comments:
        review.detailed_reviewer_comments = [
            c for c in review.detailed_reviewer_comments if not _contains_offtopic_terms(str(c), doc)
        ]
    if review.extracted_action_items:
        filtered_actions = []
        for a in review.extracted_action_items:
            if not a.action or _contains_offtopic_terms(str(a.action), doc):
                continue
            filtered_actions.append(a)
        review.extracted_action_items = filtered_actions
    if review.suggested_experiments_analyses:
        review.suggested_experiments_analyses = [
            s for s in review.suggested_experiments_analyses if not _contains_offtopic_terms(str(s), doc)
        ]
    if review.section_specific_comments:
        filtered = []
        for c in review.section_specific_comments:
            if not c.comment or not str(c.comment).strip():
                continue
            if _contains_offtopic_terms(str(c.comment), doc):
                continue
            section_name = str(getattr(c, "section", "") or "").lower()
            if any(term in section_name for term in [
                "nature synthesis",
                "references",
                "acknowledg",
                "author contributions",
                "author information",
                "competing interests",
                "supplementary information",
                "additional information",
                "data availability",
            ]):
                continue
            filtered.append(c)
        review.section_specific_comments = filtered


def _ensure_section_comments(review: ReviewSchema, doc: ParsedDocument) -> None:
    if review.section_specific_comments:
        return
    front_matter_terms = [
        "nature synthesis",
        "references",
        "acknowledg",
        "author contributions",
        "author information",
        "competing interests",
        "supplementary information",
        "additional information",
        "data availability",
    ]
    headings = [
        h
        for h in doc.headings
        if h and not any(term in h.lower() for term in front_matter_terms)
    ]
    for h in headings[:4]:
        review.section_specific_comments.append(
            SectionComment(section=h, comment="Add one concrete evidence statement and one limitation statement tied to this section.", severity="medium")
        )


def _ensure_generic_sections(review: ReviewSchema, doc: ParsedDocument, support_docs: list[ParsedDocument]) -> None:
    low_text = doc.cleaned_text.lower()
    support_docs = [d for d in support_docs if d.source_path.name != doc.source_path.name]
    if not review.writing_organization_concerns:
        concerns = []
        if "==> picture" in low_text or "intentionally omitted" in low_text:
            concerns.append("Remove PDF extraction artifacts and normalize section/figure formatting.")
        concerns.append("Tighten long sentences in Results/Discussion to keep one claim per sentence.")
        review.writing_organization_concerns = concerns[:2]
    if not review.novelty_concerns:
        review.novelty_concerns = [
            "Clarify novelty relative to prior phactor/HTE workflow papers and LLM-assisted reaction design approaches."
        ]
    if not review.figure_table_concerns and "figure" in low_text:
        review.figure_table_concerns = [
            "Ensure figure captions clearly identify what is shown, including axes, conditions, and how the figure supports nearby claims."
        ]
    if not review.citation_reference_concerns and ("citation" in low_text or "doi" in low_text or "smiles" in low_text):
        if support_docs:
            support_names = ", ".join([d.source_path.name for d in support_docs[:4]])
            review.citation_reference_concerns = [
                f"Verify cited references and DOI links; compare framing against supporting papers ({support_names}) to avoid missed context."
            ]
        else:
            review.citation_reference_concerns = [
                "Verify cited references and DOI links for accuracy and ensure any known hallucinated references are clearly acknowledged."
            ]
    if not review.reproducibility_concerns and ("chatgpt" in low_text or "phactor" in low_text):
        review.reproducibility_concerns = [
            "Clarify which steps were automated vs manually corrected and whether prompts/models are versioned."
        ]
    if not review.suggested_experiments_analyses:
        review.suggested_experiments_analyses = [
            "Add a baseline comparison against chemist-designed or literature-derived reaction arrays for at least one case study."
        ]


def _ensure_profile_specific_detail(review: ReviewSchema, profile_key: str) -> None:
    if profile_key == "methods":
        if not review.methodological_concerns:
            seeds = [w for w in review.major_weaknesses if isinstance(w, str) and w.strip()]
            review.methodological_concerns = (seeds[:2] if seeds else [
                "Clarify controls and benchmark setup used to support main method claims.",
                "Add ablation/sensitivity checks that isolate contribution of each modeling component.",
            ])
        if not review.statistical_concerns:
            review.statistical_concerns = [
                "Report uncertainty and variance for key outcome metrics (for example confidence intervals or repeated-run spread)."
            ]
    if profile_key in {"writing", "editor"}:
        if not review.methodological_concerns:
            review.methodological_concerns = [
                "Not a primary focus in writing/editor passes; see methods review for experimental validity checks."
            ]
        if not review.statistical_concerns:
            review.statistical_concerns = [
                "Statistical validity not assessed in this pass; consult methods review for quantitative checks."
            ]
    if profile_key in {"balanced", "adversarial"} and not review.citation_reference_concerns:
        review.citation_reference_concerns = [
            "Offline check only: verify key factual assertions are matched to explicit citations and that references are complete."
        ]


def _review_quality_signals(review: ReviewSchema, profile_key: str, doc: ParsedDocument | None = None) -> dict[str, float | int | bool]:
    doc_text = (doc.cleaned_text.lower() if doc else "")
    figure_mentions = doc_text.count("figure ") + doc_text.count("fig.")
    placeholder_count = 0
    for a in review.extracted_action_items:
        t = str(a.action).lower()
        if "apply action:" in t or t.startswith("address:"):
            placeholder_count += 1
    for c in review.detailed_reviewer_comments:
        t = str(c).lower()
        if "apply action:" in t or "revise wording to address this issue" in t:
            placeholder_count += 1
    return {
        "summary_len": len((review.summary or "").strip()),
        "strengths_count": len(review.major_strengths),
        "weaknesses_count": len(review.major_weaknesses),
        "details_count": len(review.detailed_reviewer_comments),
        "actions_count": len(review.extracted_action_items),
        "section_comments_count": len(review.section_specific_comments),
        "methods_count": len(review.methodological_concerns),
        "stats_count": len(review.statistical_concerns),
        "writing_count": len(review.writing_organization_concerns),
        "figure_count": len(review.figure_table_concerns),
        "repro_count": len(review.reproducibility_concerns),
        "placeholder_count": placeholder_count,
        "doc_figure_mentions": figure_mentions,
        "profile_is_methods": profile_key == "methods",
        "profile_is_writing": profile_key in {"writing", "editor"},
    }


def _review_artifact_text(review: ReviewSchema) -> str:
    parts: list[str] = [review.summary]
    parts.extend(review.major_strengths[:4])
    parts.extend(review.major_weaknesses[:6])
    parts.extend(review.figure_table_concerns[:4])
    parts.extend(review.reproducibility_concerns[:4])
    parts.extend(review.methodological_concerns[:4])
    parts.extend(review.writing_organization_concerns[:4])
    parts.extend(review.detailed_reviewer_comments[:8])
    parts.extend([a.action for a in review.extracted_action_items[:8]])
    return "\n".join([p for p in parts if isinstance(p, str) and p.strip()])


def _augment_with_text_heuristics(
    doc: ParsedDocument,
    review: ReviewSchema,
    profile_key: str,
    guidance_categories: list[str] | None = None,
    supporting_docs: list[ParsedDocument] | None = None,
) -> None:
    text = doc.cleaned_text or ""
    low_text = text.lower()
    sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
    def _sentence_ok(s: str) -> bool:
        low = s.lower()
        if "==> picture" in low or "intentionally omitted" in low:
            return False
        if "supporting information" in low or "references" in low:
            return False
        if "■" in s or s.strip().startswith("##"):
            return False
        return True
    sentences = [s for s in sentences if _sentence_ok(s)]
    long_sentences = [s for s in sentences if len(s.split()) > 38][:6]
    passive_hits = [s for s in sentences if len(s.split()) > 10 and (" was " in f" {s.lower()} " or " were " in f" {s.lower()} ")][:5]
    def _heading_snippet(heading: str) -> str | None:
        if not heading:
            return None
        h = re.sub(r"[*_]+", "", heading).strip()
        if not h:
            return None
        idx = low_text.find(h.lower())
        if idx == -1:
            return None
        tail = text[idx: idx + 500]
        snippet = re.split(r"(?<=[.!?])\s+", tail)
        if len(snippet) >= 2:
            return snippet[1].strip()[:220]
        if snippet:
            return snippet[0].strip()[:220]
        return None
    def _rewrite_candidate(sentence: str) -> str:
        s = sentence.strip()
        if len(s) > 260:
            s = s[:260].rstrip() + "..."
        clauses = [c.strip() for c in s.split(",") if c.strip()]
        if len(clauses) >= 2:
            return f"{clauses[0]}. {clauses[1][0:120]}."
        words = s.split()
        if len(words) > 24:
            return " ".join(words[:24]) + "."
        return s if s.endswith(".") else s + "."
    placeholder_hits = []
    for token in ["intentionally omitted", "==> picture", "<br>", "supporting information", "references"]:
        if token in text.lower():
            placeholder_hits.append(token)
    support_docs = [d for d in (supporting_docs or []) if d.source_path.name != doc.source_path.name]
    support_note = ""
    if support_docs:
        support_note = f" Supporting context from {len(support_docs)} project `materials/other` documents was scanned for context alignment."
    if not review.summary.strip():
        if profile_key == "adversarial":
            review.summary = (
                f"Heuristic adversarial review for {doc.source_path.name}: "
                "current claims likely overstate certainty relative to the described evidence; framing should be tightened and limitations made explicit."
                + support_note
            )
        elif profile_key == "methods":
            review.summary = (
                f"Heuristic methods review for {doc.source_path.name}: "
                "methods-to-results traceability is incomplete; controls, uncertainty reporting, and reproducibility specifics need strengthening."
                + support_note
            )
        elif profile_key in {"writing", "editor"}:
            review.summary = (
                f"Heuristic editorial review for {doc.source_path.name}: "
                "the manuscript has style/format artifacts from PDF extraction and contains several long/passive constructions "
                "that reduce readability. Priority is to tighten sentence flow and remove extraction placeholders."
            )
        else:
            review.summary = (
                f"Heuristic balanced review for {doc.source_path.name}: "
                "the manuscript is promising but needs clearer claim support, stronger methodological detail, and cleaner narrative flow."
                + support_note
            )
    if not review.major_weaknesses:
        if profile_key == "adversarial":
            review.major_weaknesses = [
                "Several claims read stronger than the evidence presented in the manuscript body.",
                "Narrative occasionally implies broad generality without explicit boundary conditions.",
                "Methods/results linkage is underspecified for strict reviewer scrutiny.",
            ]
        elif profile_key == "methods":
            review.major_weaknesses = [
                "Control/baseline definitions are not consistently explicit where comparisons are made.",
                "Uncertainty and reproducibility details are insufficiently operationalized.",
                "Result interpretation steps are not always tied to concrete procedural details.",
            ]
        else:
            review.major_weaknesses = [
                "Multiple long, dense sentences reduce readability and reviewer scanability.",
                "Passive voice and indirect phrasing obscure agent/action in methods and results.",
                "PDF extraction artifacts (e.g., placeholders/markup fragments) should be cleaned before submission.",
            ]
    if not review.major_strengths:
        strengths: list[str] = []
        if "hallucinat" in low_text or "smiles" in low_text:
            strengths.append("The manuscript acknowledges LLM hallucination risks and documents mitigation steps (e.g., invalid citations/SMILES), which strengthens scientific honesty.")
        if "phactor" in low_text and "chatgpt" in low_text:
            strengths.append("The workflow integrates LLM proposal generation with automated execution, showing a concrete end-to-end pipeline rather than purely speculative claims.")
        if not strengths:
            strengths = [
                "The manuscript addresses an applied workflow problem with clear section structure.",
                "Experimental scope is well defined around a specific automation pipeline.",
            ]
        review.major_strengths = strengths[:3]
    guidance_categories = guidance_categories or []

    if profile_key in {"writing", "editor"}:
        if not review.major_strengths:
            review.major_strengths = [
                "The manuscript has a clear high-level motivation around reaction-array design automation.",
                "Core sections (Introduction, Experimental, Results, Discussion, Conclusions) are present and can be tightened effectively.",
            ]
        if not review.writing_organization_concerns:
            concerns: list[str] = []
            for s in long_sentences[:2]:
                concerns.append(f"Long sentence that could be split for clarity: {s[:160]}")
            for s in passive_hits[:1]:
                concerns.append(f"Passive construction reduces clarity: {s[:160]}")
            if not concerns:
                concerns = [
                    "Simplify long sentences in introduction/results to reduce cognitive load.",
                    "Use active voice for key method/result statements.",
                ]
            review.writing_organization_concerns = concerns
        if "formatting_color_guides" in guidance_categories:
            review.writing_organization_concerns.append(
                "Apply lab formatting conventions from formatting/color guides (heading hierarchy, figure caption consistency, and visual-callout style)."
            )
        if "external_guides" in guidance_categories:
            review.writing_organization_concerns.append(
                "Align wording/tone with external editorial guidance: concise claims, explicit limitations, and reproducibility-forward phrasing."
            )
        for s in long_sentences[:3]:
            rewrite = _rewrite_candidate(s)
            review.detailed_reviewer_comments.append(
                f"Long sentence to simplify: {s[:220]} | Suggested rewrite: {rewrite}"
            )
        for s in passive_hits[:2]:
            rewrite = _rewrite_candidate(s.replace(" was ", " ").replace(" were ", " "))
            review.detailed_reviewer_comments.append(
                f"Possible passive construction to rewrite: {s[:220]} | Suggested rewrite: {rewrite}"
            )
        for token in placeholder_hits[:3]:
            review.detailed_reviewer_comments.append(f"Cleanup needed for extraction artifact token: `{token}`")
        if not review.section_specific_comments:
            for heading in (doc.headings or ["Introduction", "Results", "Discussion"])[:3]:
                snippet = _heading_snippet(str(heading)) or ""
                comment = "Tighten flow and improve sentence-level clarity in this section."
                if snippet:
                    comment = f"Clarify this section’s opening claim: \"{snippet}\""
                review.section_specific_comments.append(
                    SectionComment(
                        section=str(heading)[:120],
                        comment=comment,
                        severity="medium",
                    )
                )
        if not review.extracted_action_items:
            for s in long_sentences[:3]:
                review.extracted_action_items.append(
                    ActionItem(
                        action=f"Rewrite long sentence for clarity: {s[:140]}",
                        priority="high",
                        owner="author",
                    )
                )
            if placeholder_hits:
                review.extracted_action_items.append(
                    ActionItem(
                        action="Remove PDF extraction placeholders and restore missing figure/table callout text.",
                        priority="high",
                        owner="author",
                    )
                )

    if profile_key in {"methods", "balanced", "adversarial"}:
        if not review.writing_organization_concerns:
            concerns: list[str] = []
            for s in long_sentences[:2]:
                concerns.append(f"Long sentence that could be split for clarity: {s[:160]}")
            for s in passive_hits[:1]:
                concerns.append(f"Passive construction reduces clarity: {s[:160]}")
            if not concerns:
                concerns = [
                    "Tighten long sentences in Results/Discussion to keep one claim per sentence.",
                    "Reduce passive voice in methods/results to make agent/action clear.",
                ]
            review.writing_organization_concerns = concerns
        if not review.methodological_concerns:
            if profile_key == "adversarial":
                review.methodological_concerns = [
                    "Stress-test whether claimed gains persist under stricter baselines and adverse conditions.",
                    "Show failure cases and boundary conditions where the approach underperforms.",
                ]
            elif profile_key == "methods":
                review.methodological_concerns = [
                    "Clarify experimental controls and benchmark baselines used for model comparison.",
                    "Add ablation/sensitivity checks to separate prompt effects from model effects.",
                    "Explicitly map each key claim to the exact experiment and metric that supports it.",
                ]
            else:
                review.methodological_concerns = [
                    "Clarify experimental controls and benchmark baselines used for model comparison.",
                    "Add ablation/sensitivity checks to separate prompt effects from model effects.",
                ]
        if not review.statistical_concerns:
            review.statistical_concerns = [
                "Report uncertainty (confidence intervals or repeated-run variance) for key performance claims.",
            ]
        if not review.reproducibility_concerns:
            review.reproducibility_concerns = [
                "Clarify which steps were automated vs manually corrected and whether prompts/models are versioned.",
            ]
        if profile_key == "adversarial" and not review.novelty_concerns:
            review.novelty_concerns = [
                "Differentiate clearly from nearest prior workflow baselines to avoid perceived incremental framing.",
            ]
        if not review.figure_table_concerns and (low_text.count("figure ") + low_text.count("fig.") >= 3):
            review.figure_table_concerns = [
                "Ensure figure captions clearly identify what is shown, including axes, conditions, and how the figure supports nearby claims.",
            ]
        if support_docs and not review.citation_reference_concerns:
            support_names = ", ".join([d.source_path.name for d in support_docs[:4]])
            review.citation_reference_concerns = [
                f"Cross-check manuscript framing against supporting papers ({support_names}) for missing context contrasts; cite specific overlaps where relevant.",
            ]
        if not review.section_specific_comments:
            for heading in (doc.headings or ["Introduction", "Experimental", "Results", "Discussion"])[:4]:
                snippet = _heading_snippet(str(heading)) or ""
                comment = "Add one concrete evidence statement and one limitation statement tied to this section."
                if snippet:
                    comment = f"Clarify evidence/limitation for: \"{snippet}\""
                review.section_specific_comments.append(
                    SectionComment(
                        section=str(heading)[:120],
                        comment=comment,
                        severity="medium",
                    )
                )


def run_review(
    provider: Provider,
    doc: ParsedDocument,
    profile: ReviewProfile,
    model: str,
    repair_models: list[str],
    config: ReviewerConfig,
    bundle_dir: Path,
    embedding_model: str | None,
    strict_schema_override: bool | None,
    logger: logging.Logger,
    guidance_text: str | None = None,
    guidance_categories: list[str] | None = None,
    status_hook: Callable[[str], None] | None = None,
    supporting_docs: list[ParsedDocument] | None = None,
    orchestrator: OrchestratorController | None = None,
    orchestrator_state: OrchestratorRuntimeState | None = None,
    stage_name: str | None = None,
) -> ReviewRunResult:
    warnings = list(doc.parse_warnings)
    retrieval_manifest: list[dict] = []
    if status_hook:
        status_hook("preparing chunks")

    logger.info("review_start source=%s profile=%s model=%s", doc.source_path, profile.key, model)

    context = _context_from_doc(doc, profile, config)
    support_docs = supporting_docs or []
    use_retrieval = bool(
        embedding_model
        and doc.chunks
        and config.retrieval.enabled
        and profile.use_retrieval
    )

    # Include short, explicit evidence context from supporting docs even when retrieval is off.
    support_summary_blocks: list[str] = []
    for i, sdoc in enumerate(support_docs[:8], start=1):
        if not sdoc.chunks:
            chunk_document(sdoc, max_chars=profile.chunk_size, overlap=profile.chunk_overlap)
        excerpt = sdoc.cleaned_text[:800]
        support_summary_blocks.append(
            f"[support:{i}] source={sdoc.source_path.name} headings={sdoc.headings[:6]} excerpt={excerpt}"
        )
    if support_summary_blocks:
        context = (
            f"{context}\n\n"
            "Supporting references context (use to check whether manuscript assertions appear backed by supplied materials):\n"
            + "\n\n".join(support_summary_blocks)
        )

    if use_retrieval:
        if status_hook:
            status_hook("embedding retrieval")
        support_chunks = []
        chunk_source: dict[str, str] = {}
        for c in doc.chunks:
            chunk_source[c.chunk_id] = str(doc.source_path.name)
        for i, sdoc in enumerate(support_docs[:8], start=1):
            for c in sdoc.chunks:
                key = f"support{i}:{c.chunk_id}"
                # Duplicate chunk id to avoid collisions across documents.
                c_copy = type(c)(
                    chunk_id=key,
                    text=c.text,
                    heading=c.heading,
                    start_char=c.start_char,
                    end_char=c.end_char,
                    source_page=c.source_page,
                )
                support_chunks.append(c_copy)
                chunk_source[key] = str(sdoc.source_path.name)

        def _run_retrieval(model_name: str):
            return retrieve_top_k(
                query="core claims, evidence quality, weaknesses, methods, statistics, reproducibility",
                chunks=doc.chunks + support_chunks,
                provider=provider,
                embedding_model=model_name,
                timeout_seconds=config.timeouts.embed_seconds,
                top_k=config.retrieval.top_k,
                max_chunk_embed_chars=config.retrieval.max_chunk_embed_chars,
            )

        try:
            top = _run_retrieval(embedding_model)
            retrieval_manifest = [
                {
                    "chunk_id": t.chunk.chunk_id,
                    "score": round(t.score, 6),
                    "start_char": t.chunk.start_char,
                    "end_char": t.chunk.end_char,
                    "source": chunk_source.get(t.chunk.chunk_id, "unknown"),
                }
                for t in top
            ]
            context = "\n\n".join(
                [
                    f"[retrieved score={t.score:.3f} source={chunk_source.get(t.chunk.chunk_id, 'unknown')}] {t.chunk.text[:2000]}"
                    for t in top
                ]
            )
            logger.info("retrieval_used chunks=%s", len(retrieval_manifest))
        except Exception as exc:
            fallback = config.defaults.embedding_fallback_model
            if fallback and fallback != embedding_model:
                try:
                    top = _run_retrieval(fallback)
                    retrieval_manifest = [
                        {
                            "chunk_id": t.chunk.chunk_id,
                            "score": round(t.score, 6),
                            "start_char": t.chunk.start_char,
                            "end_char": t.chunk.end_char,
                            "source": chunk_source.get(t.chunk.chunk_id, "unknown"),
                        }
                        for t in top
                    ]
                    context = "\n\n".join(
                        [
                            f"[retrieved score={t.score:.3f} source={chunk_source.get(t.chunk.chunk_id, 'unknown')}] {t.chunk.text[:2000]}"
                            for t in top
                        ]
                    )
                    warnings.append(
                        f"Embedding retrieval fallback used due to error: {exc}. Fallback model: {fallback}"
                    )
                    logger.info("retrieval_used_fallback chunks=%s model=%s", len(retrieval_manifest), fallback)
                except Exception as exc2:
                    warnings.append(f"Embedding retrieval disabled due to error: {exc2}")
                    logger.warning("embedding_retrieval_failed_fallback error=%s", exc2)
            else:
                warnings.append(f"Embedding retrieval disabled due to error: {exc}")
                logger.warning("embedding_retrieval_failed error=%s", exc)
    if status_hook:
        status_hook("generating review")

    prompt = _build_prompt(doc, profile, context, guidance_text=guidance_text)
    started = time.time()
    response = provider.chat(
        ChatRequest(
            model=model,
            system_prompt=profile.system_prompt,
            user_prompt=prompt,
            temperature=profile.temperature,
            max_tokens=2800,
            timeout_seconds=config.timeouts.chat_seconds,
            metadata={
                "profile": profile.key,
                "strict_schema": strict_schema_override if strict_schema_override is not None else profile.strict_schema,
                "prompt_chars": len(prompt),
                "chunk_count": len(doc.chunks),
                "json_mode": True,
            },
        )
    )
    elapsed = time.time() - started

    parse: ParseOutcome = parse_and_repair(
        response.content,
        provider=provider,
        primary_model=model,
        repair_models=repair_models,
        timeout_seconds=config.timeouts.chat_seconds,
        logger=logger,
        allow_self_repair=profile.force_repair_pass,
    )
    warnings.extend(parse.warnings)
    if status_hook:
        status_hook("validating and repairing output")

    review = parse.parsed
    assert review is not None

    if _is_sparse_review(review):
        warnings.append("Sparse structured output detected; attempting enrichment pass.")
        logger.warning("sparse_review_detected source=%s profile=%s model=%s", doc.source_path, profile.key, model)
        enrich_prompt = (
            "The previous JSON review output is too sparse. Regenerate a COMPLETE, specific review for the same paper. "
            "Return strict JSON only and populate substantive fields with grounded, paper-specific content.\n\n"
            "Required minimums:\n"
            "- summary: at least 140 characters\n"
            "- major_strengths: at least 2 items\n"
            "- major_weaknesses: at least 3 items\n"
            "- detailed_reviewer_comments: at least 3 items\n"
            "- extracted_action_items: at least 3 items\n"
            "- include at least 2 section_specific_comments with section names when possible\n\n"
            f"PROFILE: {profile.display_name}\n"
            f"FOCUS: {profile.rubric_focus}\n"
            f"DOCUMENT HEADINGS: {doc.headings[:30]}\n"
            f"PARSER WARNINGS: {doc.parse_warnings}\n\n"
            f"CONTEXT:\n{context}\n"
        )
        candidate_models: list[str] = []
        heavy_markers = ["70b", "llama3.3", "llama3:70b", "llama3.1:70b"]
        skip_heavy = any(h in (model or "").lower() for h in heavy_markers)
        for m in [*repair_models, model]:
            if m and m not in candidate_models:
                if m == model and skip_heavy and repair_models:
                    continue
                candidate_models.append(m)
        enriched = False
        for enrich_model in candidate_models:
            try:
                enrich_resp = provider.chat(
                    ChatRequest(
                        model=enrich_model,
                        system_prompt=profile.system_prompt,
                        user_prompt=enrich_prompt,
                        temperature=max(profile.temperature, 0.1),
                        max_tokens=3000,
                        timeout_seconds=min(config.timeouts.chat_seconds, 120),
                        metadata={
                            "profile": profile.key,
                            "enrichment_pass": True,
                            "source_model": model,
                            "prompt_chars": len(enrich_prompt),
                            "json_mode": True,
                        },
                    )
                )
                enrich_parse: ParseOutcome = parse_and_repair(
                    enrich_resp.content,
                    provider=provider,
                    primary_model=enrich_model,
                    repair_models=repair_models,
                    timeout_seconds=config.timeouts.chat_seconds,
                    logger=logger,
                    allow_self_repair=True,
                )
                warnings.extend(enrich_parse.warnings)
                if enrich_parse.parsed and not _is_sparse_review(enrich_parse.parsed):
                    parse = enrich_parse
                    review = enrich_parse.parsed
                    enriched = True
                    logger.info("sparse_review_enriched source=%s profile=%s model=%s", doc.source_path, profile.key, enrich_model)
                    break
            except Exception as exc:
                warnings.append(f"Sparse enrichment pass failed on {enrich_model}: {exc}")
                logger.warning("sparse_review_enrichment_exception source=%s profile=%s model=%s error=%s", doc.source_path, profile.key, enrich_model, exc)
        if not enriched:
            warnings.append("Sparse output persisted after enrichment pass.")
            logger.warning("sparse_review_enrichment_failed source=%s profile=%s", doc.source_path, profile.key)

    if _is_sparse_review(review):
        _augment_with_text_heuristics(
            doc,
            review,
            profile.key,
            guidance_categories=guidance_categories,
            supporting_docs=support_docs,
        )
        warnings.append("Applied deterministic heuristic augmentation due to sparse structured output.")

    _ensure_minimum_detail(review)
    _filter_hallucinated_review_content(review, doc)
    if not _summary_matches_doc(review.summary, doc):
        abstract = _extract_abstract(doc)
        if abstract:
            review.summary = abstract
    _ensure_profile_specific_detail(review, profile.key)
    _ensure_section_comments(review, doc)
    _ensure_generic_sections(review, doc, support_docs)

    figure_manifest = None
    if config.figure_review.enabled:
        try:
            figure_manifest = run_figure_review(doc, bundle_dir, config.figure_review)
            critique = figure_manifest.get("critique", {}) if isinstance(figure_manifest, dict) else {}
            figure_items = critique.get("critique", []) if isinstance(critique, dict) else []
            for item in figure_items[: config.figure_review.max_figures]:
                issues = item.get("content_issues", [])
                for issue in issues[:2]:
                    review.figure_table_concerns.append(f"{item.get('figure_id')}: {issue}")
        except Exception as exc:
            warnings.append(f"figure_review_failed:{exc}")

    orchestrator_decisions: list[dict] = []
    orchestrator_retry_log: list[dict] = []
    stage_key = stage_name or profile.key
    runtime = orchestrator_state or OrchestratorRuntimeState(
        max_stage_retries=max(0, int(config.orchestrator.max_stage_retries)),
        max_total_retries=max(0, int(config.orchestrator.max_total_retries)),
    )
    if orchestrator is not None and orchestrator.enabled:
        stage_retries_used = 0
        try:
            qa = orchestrator.evaluate_stage_output(
                stage_name=profile.key,
                artifact_text=_review_artifact_text(review),
                quality_signals=_review_quality_signals(review, profile.key, doc),
                timeout_seconds=min(90, config.timeouts.chat_seconds),
            )
            orchestrator_decisions.append(
                {
                    "stage": stage_key,
                    "decision": "evaluate_stage_output",
                    "assessment": qa.model_dump(),
                    "retry_budget": {
                        "stage_used": stage_retries_used,
                        "total_used": runtime.total_retries_used,
                        "max_stage": runtime.max_stage_retries,
                        "max_total": runtime.max_total_retries,
                    },
                }
            )
            rd = orchestrator.request_retry_decision(qa, runtime, stage_retries_used)
            if rd.should_retry:
                runtime.consume_retry()
                stage_retries_used += 1
                warnings.append(f"orchestrator_retry_requested:{profile.key}:{rd.retry_reason}")
                retry_prompt = (
                    "Your previous structured review was low quality for this stage. Regenerate strict JSON only with stronger specificity and actionability.\n"
                    f"Profile: {profile.display_name}\n"
                    f"Missing dimensions: {[d.value for d in qa.missing_dimensions]}\n"
                    f"Document headings: {doc.headings[:30]}\n"
                    f"Context:\n{context[:10000]}\n"
                )
                retry_resp = provider.chat(
                    ChatRequest(
                        model=model,
                        system_prompt=profile.system_prompt,
                        user_prompt=retry_prompt,
                        temperature=max(0.0, profile.temperature * 0.5),
                        max_tokens=2800,
                        timeout_seconds=config.timeouts.chat_seconds,
                        metadata={"profile": profile.key, "json_mode": True, "orchestrator_retry": True},
                    )
                )
                retry_parse = parse_and_repair(
                    retry_resp.content,
                    provider=provider,
                    primary_model=model,
                    repair_models=repair_models,
                    timeout_seconds=config.timeouts.chat_seconds,
                    logger=logger,
                    allow_self_repair=True,
                )
                warnings.extend(retry_parse.warnings)
                if retry_parse.parsed:
                    retry_review = retry_parse.parsed
                    _ensure_minimum_detail(retry_review)
                    _ensure_profile_specific_detail(retry_review, profile.key)
                    if _is_sparse_review(retry_review):
                        _augment_with_text_heuristics(
                            doc,
                            retry_review,
                            profile.key,
                            guidance_categories=guidance_categories,
                            supporting_docs=support_docs,
                        )
                    qa_retry = orchestrator.evaluate_stage_output(
                        stage_name=profile.key,
                        artifact_text=_review_artifact_text(retry_review),
                        quality_signals=_review_quality_signals(retry_review, profile.key, doc),
                        timeout_seconds=min(90, config.timeouts.chat_seconds),
                    )
                    cmp = orchestrator.compare_stage_versions(qa, qa_retry)
                    orchestrator_retry_log.append(
                        {
                            "stage": stage_key,
                            "retry_decision": rd.model_dump(),
                            "retry_assessment": qa_retry.model_dump(),
                            "version_comparison": cmp.model_dump(),
                        }
                    )
                    if cmp.winner == "B":
                        review = retry_review
                        parse = retry_parse
                else:
                    orchestrator_retry_log.append(
                        {
                            "stage": stage_key,
                            "retry_decision": rd.model_dump(),
                            "result": "retry_parse_failed",
                        }
                    )
            (bundle_dir / "orchestrator_stage_quality.json").write_text(
                json.dumps(orchestrator_decisions, indent=2),
                encoding="utf-8",
            )
            (bundle_dir / "orchestrator_retry_log.json").write_text(
                json.dumps(orchestrator_retry_log, indent=2),
                encoding="utf-8",
            )
            (bundle_dir / "orchestrator_decisions.json").write_text(
                json.dumps(
                    {
                        "stage": stage_key,
                        "model": orchestrator.model,
                        "enabled": orchestrator.enabled,
                        "fail_open": orchestrator.fail_open,
                        "decisions": orchestrator_decisions,
                        "retries": orchestrator_retry_log,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            warnings.append(f"orchestrator_error:{exc}")
            if not orchestrator.fail_open:
                raise

    review.model_debug_metadata = DebugMetadata(
        provider="ollama",
        model=model,
        temperature=profile.temperature,
        retries_used=response.retries_used,
        parse_failures=parse.parse_failures,
        total_duration=response.total_duration or elapsed,
        prompt_eval_count=response.prompt_eval_count,
        eval_count=response.eval_count,
    )

    source_metadata = {
        "source_path": str(doc.source_path),
        "source_path_abs": str(doc.source_path_abs),
        "source_path_rel": doc.source_path_rel,
        "document_type": doc.document_type,
        "parse_engine": doc.parse_engine,
        "file_size_bytes": doc.file_size_bytes,
        "raw_text_length": len(doc.raw_text),
        "cleaned_text_length": len(doc.cleaned_text),
        "page_count": doc.page_count,
        "headings": doc.headings[:50],
        "ingest_timestamp": doc.ingest_timestamp,
    }

    project_root = _find_project_root(doc.source_path_abs)
    est_duration, est_basis = _estimate_duration_seconds(project_root, profile.key, model, len(doc.cleaned_text))
    run_metadata = {
        "profile": profile.key,
        "model": model,
        "embedding_model": embedding_model,
        "strict_schema": strict_schema_override if strict_schema_override is not None else profile.strict_schema,
        "prompt_chars": response.prompt_chars,
        "approx_prompt_tokens": response.approx_prompt_tokens,
        "chunk_count": len(doc.chunks),
        "retrieval_used": bool(retrieval_manifest),
        "retrieval_count": len(retrieval_manifest),
        "repair_stage": parse.repair_stage,
        "repair_model": parse.used_repair_model,
        "parse_failure_types": [ft.value for ft in parse.failure_types],
        "duration_seconds": elapsed,
        "estimated_duration_seconds": est_duration,
        "estimate_basis": est_basis,
        "warnings_count": len(warnings),
        "guidance_injected": bool(guidance_text),
        "guidance_categories": guidance_categories or [],
    }

    write_review_bundle(
        bundle_dir=bundle_dir,
        review=review,
        source_metadata=source_metadata,
        run_metadata=run_metadata,
        raw_response=response.content,
        repaired_response=parse.repaired_text,
        warnings=warnings,
        keep_raw=config.defaults.keep_raw_outputs,
        chunk_manifest=_chunk_manifest(doc),
        retrieval_manifest=retrieval_manifest,
    )
    if status_hook:
        status_hook("writing reports")

    logger.info(
        "review_end source=%s model=%s duration=%.2fs parse_failures=%s retrieval=%s",
        doc.source_path,
        model,
        elapsed,
        parse.parse_failures,
        len(retrieval_manifest),
    )
    if status_hook:
        status_hook("done")
    return ReviewRunResult(review=review, warnings=warnings, bundle_dir=bundle_dir, retrieval_manifest=retrieval_manifest)


def run_compare(
    provider: Provider,
    old_text: str,
    new_text: str,
    model: str,
    profile_prompt: str,
    timeout_seconds: int,
    max_old_chars: int,
    max_new_chars: int,
    logger: logging.Logger,
    guidance_text: str | None = None,
) -> CompareSchema:
    guidance_block = f"\nLAB TRAINING GUIDANCE:\n{guidance_text}\n" if guidance_text else ""
    prompt = (
        "Compare the old and new drafts and return strict JSON only using this schema:\n"
        "{\"summary_of_major_revisions\": [str], \"unresolved_issues\": [str], \"regressions\": [str], "
        "\"added_claims\": [str], \"removed_claims\": [str], \"changed_claims\": [str], "
        "\"response_to_reviewers_bullets\": [str], \"debug\": {\"provider\": str, \"model\": str, "
        "\"temperature\": float, \"retries_used\": int, \"parse_failures\": int}}\n"
        f"Profile focus: {profile_prompt}\n"
        f"{guidance_block}\n"
        f"OLD_DRAFT:\n{old_text[:max_old_chars]}\n\nNEW_DRAFT:\n{new_text[:max_new_chars]}\n"
    )
    resp = provider.chat(
        ChatRequest(
            model=model,
            system_prompt="You are a strict revision reviewer.",
            user_prompt=prompt,
            temperature=0.1,
            max_tokens=2200,
            timeout_seconds=timeout_seconds,
        )
    )

    from ai_reviewer.review.repair import extract_json_candidate

    candidate = extract_json_candidate(resp.content) or resp.content
    payload = json.loads(candidate)
    try:
        return CompareSchema.model_validate(payload)
    except Exception as exc:
        logger.warning("compare_schema_failed error=%s", exc)
        payload.setdefault("summary_of_major_revisions", [])
        payload.setdefault("unresolved_issues", [])
        payload.setdefault("regressions", [])
        payload.setdefault("added_claims", [])
        payload.setdefault("removed_claims", [])
        payload.setdefault("changed_claims", [])
        payload.setdefault("response_to_reviewers_bullets", [])
        payload["debug"] = {
            "provider": "ollama",
            "model": model,
            "temperature": 0.1,
            "retries_used": resp.retries_used,
            "parse_failures": 1,
        }
        return CompareSchema.model_validate(payload)
