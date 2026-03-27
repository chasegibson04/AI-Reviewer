from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ai_reviewer.config import ReviewerConfig
from ai_reviewer.ingest.chunking import chunk_document
from ai_reviewer.ingest.retrieval import retrieve_top_k
from ai_reviewer.ingest.types import ParsedDocument
from ai_reviewer.models.base import ChatRequest, Provider
from ai_reviewer.orchestrator.controller import OrchestratorController, OrchestratorRuntimeState
from ai_reviewer.review.profiles import ReviewProfile
from ai_reviewer.review.repair import ParseOutcome, parse_and_repair
from ai_reviewer.review.render import write_review_bundle
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
    return (
        f"Profile: {profile.display_name}\n"
        f"Review focus: {profile.rubric_focus}\n"
        f"Max words: {profile.max_review_words}\n"
        "Return strict JSON only. No commentary outside JSON.\n"
        "Grounding requirements:\n"
        "- Be specific to this manuscript, not generic.\n"
        "- Reference concrete sections/headings or experiment types from the provided context.\n"
        "- If support context is present, use it to check whether assertions appear backed.\n"
        "- Avoid repeating the same sentence across fields.\n"
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
    return summary_len < 80 or populated_items < 4


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
            generated.append(ActionItem(action=f"Address: {w}", priority="high", owner="author"))
        if not generated:
            for c in review.detailed_reviewer_comments[:5]:
                if isinstance(c, str) and c.strip():
                    generated.append(ActionItem(action=f"Revise section for: {c}", priority="medium", owner="author"))
        review.extracted_action_items = generated


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
    if profile_key in {"balanced", "adversarial"} and not review.citation_reference_concerns:
        review.citation_reference_concerns = [
            "Offline check only: verify key factual assertions are matched to explicit citations and that references are complete."
        ]


def _review_quality_signals(review: ReviewSchema, profile_key: str) -> dict[str, float | int | bool]:
    return {
        "summary_len": len((review.summary or "").strip()),
        "details_count": len(review.detailed_reviewer_comments),
        "actions_count": len(review.extracted_action_items),
        "methods_count": len(review.methodological_concerns),
        "stats_count": len(review.statistical_concerns),
        "writing_count": len(review.writing_organization_concerns),
        "profile_is_methods": profile_key == "methods",
        "profile_is_writing": profile_key in {"writing", "editor"},
    }


def _review_artifact_text(review: ReviewSchema) -> str:
    parts: list[str] = [review.summary]
    parts.extend(review.major_weaknesses[:6])
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
    sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
    long_sentences = [s for s in sentences if len(s.split()) > 38][:6]
    passive_hits = [s for s in sentences if len(s.split()) > 10 and (" was " in f" {s.lower()} " or " were " in f" {s.lower()} ")][:5]
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
    support_docs = supporting_docs or []
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
    guidance_categories = guidance_categories or []

    if profile_key in {"writing", "editor"}:
        if not review.major_strengths:
            review.major_strengths = [
                "The manuscript has a clear high-level motivation around reaction-array design automation.",
                "Core sections (Introduction, Experimental, Results, Discussion, Conclusions) are present and can be tightened effectively.",
            ]
        if not review.writing_organization_concerns:
            review.writing_organization_concerns = [
                "Simplify long sentences in introduction/results to reduce cognitive load.",
                "Use active voice for key method/result statements.",
                "Standardize section/figure/citation formatting and remove extraction artifacts.",
            ]
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
                review.section_specific_comments.append(
                    SectionComment(
                        section=str(heading)[:120],
                        comment="Tighten flow and improve sentence-level clarity in this section.",
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
        if profile_key == "adversarial" and not review.novelty_concerns:
            review.novelty_concerns = [
                "Differentiate clearly from nearest prior workflow baselines to avoid perceived incremental framing.",
            ]
        if support_docs and not review.citation_reference_concerns:
            review.citation_reference_concerns = [
                f"Cross-check manuscript framing against the {len(support_docs)} supporting project papers for missing context contrasts.",
            ]


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
        excerpt = sdoc.cleaned_text[:1200]
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
        try:
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
            top = retrieve_top_k(
                query="core claims, evidence quality, weaknesses, methods, statistics, reproducibility",
                chunks=doc.chunks + support_chunks,
                provider=provider,
                embedding_model=embedding_model,
                timeout_seconds=config.timeouts.embed_seconds,
                top_k=config.retrieval.top_k,
                max_chunk_embed_chars=config.retrieval.max_chunk_embed_chars,
            )
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
        for m in [*repair_models, model]:
            if m and m not in candidate_models:
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
    _ensure_profile_specific_detail(review, profile.key)

    orchestrator_decisions: list[dict] = []
    orchestrator_retry_log: list[dict] = []
    stage_key = stage_name or profile.key
    runtime = orchestrator_state or OrchestratorRuntimeState(max_stage_retries=0, max_total_retries=0)
    if orchestrator is not None and orchestrator.enabled:
        stage_retries_used = 0
        try:
            qa = orchestrator.evaluate_stage_output(
                stage_name=profile.key,
                artifact_text=_review_artifact_text(review),
                quality_signals=_review_quality_signals(review, profile.key),
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
                        quality_signals=_review_quality_signals(retry_review, profile.key),
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
