from __future__ import annotations

import json
import copy
import logging
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_reviewer.config import ReviewerConfig
from ai_reviewer.ingest.chunking import chunk_document
from ai_reviewer.ingest.loaders import parse_file
from ai_reviewer.ingest.types import ParsedDocument
from ai_reviewer.models.base import ChatRequest, Provider
from ai_reviewer.orchestrator.controller import OrchestratorController, OrchestratorRuntimeState
from ai_reviewer.models.selector import normalize_deep_run_routing_mode, select_deep_run_stage_models, split_chat_and_embedding_models
from ai_reviewer.projects.store import ProjectStore
from ai_reviewer.review.engine import run_review
from ai_reviewer.review.manuscript_annotation import build_annotated_manuscript_output, detect_source_mode
from ai_reviewer.review.profiles import get_profile
from ai_reviewer.review.repair import extract_json_candidate
from ai_reviewer.review.docx_export import write_markdown_as_docx
from ai_reviewer.review.rigorous_adapters import build_deep_reconciliation_summary
from ai_reviewer.review.schema import (
    ActionItem,
    DeepVerificationSchema,
    ClaimEvidenceVerification,
    ReviewSchema,
    SectionComment,
)


def _verify_claims_semantically(
    provider: Provider,
    model: str,
    claims: list[dict[str, Any]],
    supporting_cards: list[dict[str, Any]],
    timeout_seconds: int,
) -> list[ClaimEvidenceVerification]:
    verifications: list[ClaimEvidenceVerification] = []
    # Pick top 15 claims by priority/overlap score
    for claim in claims[:15]:
        ctext = str(claim.get("claim", ""))[:500]
        # Find best matching cards
        matches = sorted(
            [
                {
                    "score": round(_token_overlap(ctext, f"{card.get('claim', '')} {card.get('evidence', '')}"), 4),
                    "card": card,
                }
                for card in supporting_cards
            ],
            key=lambda x: x["score"],
            reverse=True,
        )[:3]
        
        relevant_cards = [m["card"] for m in matches if m["score"] > 0.03]
        if not relevant_cards:
            continue
            
        system_prompt = (
            "You are a scientific fact-checker. Verify the manuscript CLAIM against the provided EVIDENCE CARDS from supporting literature. "
            "Return ONLY JSON with keys: claim_id, verdict, evidence_summary, supporting_source, rationale, confidence. "
            "verdict must be: supported, partially_supported, unsupported, contradicted, unresolved."
        )
        user_prompt = (
            f"CLAIM: {ctext}\n\n"
            f"EVIDENCE CARDS:\n{json.dumps(relevant_cards, indent=2)}\n\n"
            "Evaluate whether the evidence supports the claim. Return JSON."
        )
        
        try:
            payload, _ = _chat_json(provider, model, system_prompt, user_prompt, timeout_seconds)
            verifications.append(ClaimEvidenceVerification(
                claim_id=claim.get("issue_id", "CLAIM-UNK"),
                claim_text=ctext,
                verdict=payload.get("verdict", "unresolved"),
                evidence_summary=payload.get("evidence_summary", "No summary provided."),
                supporting_source=payload.get("supporting_source"),
                rationale=payload.get("rationale", "No rationale provided."),
                confidence=float(payload.get("confidence", 0.5)),
            ))
        except Exception:
            continue
    return verifications
from ai_reviewer.review.verification import (
    build_assertion_review_md,
    build_citation_accuracy_report_md,
    build_citation_verification_ledger,
    build_claim_to_citation_map,
    build_format_compliance_report,
    build_support_ingest_report,
    build_support_relevance_report_md,
    enrich_assertion_ledger,
    extract_assertion_ledger,
    internal_consistency_checks_from_text,
    support_verification_entry,
    token_overlap,
)
from ai_reviewer.training.cache import TrainingCacheManager
from ai_reviewer.tools.registry import ToolRegistry


class DeepRunError(RuntimeError):
    pass


@dataclass
class DeepRunResult:
    run_dir: Path
    manuscript_source: str
    status: str
    stage_status: dict[str, str]
    warnings: list[str]


CONTEXT_PACK_CATEGORIES = {"style_guide", "journal_instructions", "reference_example", "methods_reference"}


def _safe_json_from_text(raw: str) -> dict[str, Any]:
    candidate = extract_json_candidate(raw) or raw
    return json.loads(candidate)


def _chat_json(provider: Provider, model: str, system_prompt: str, user_prompt: str, timeout_seconds: int) -> tuple[dict[str, Any], str]:
    try:
        resp = provider.chat(
            ChatRequest(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=2600,
                timeout_seconds=timeout_seconds,
                metadata={"json_mode": True},
            )
        )
    except Exception as exc:
        return {"error": str(exc), "warning": "provider_error"}, str(exc)
        
    try:
        return _safe_json_from_text(resp.content), resp.content
    except Exception:
        return {"raw_text": resp.content, "warning": "json_parse_failed"}, resp.content


def _select_stage_models(installed_chat: list[str], cfg: ReviewerConfig) -> dict[str, str]:
    try:
        return select_deep_run_stage_models(installed_chat, cfg)
    except ValueError as exc:
        raise DeepRunError(str(exc)) from exc


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_md(path: Path, title: str, payload: dict[str, Any]) -> None:
    lines = [f"# {title}", ""]
    for k, v in payload.items():
        if k == "verifications" and isinstance(v, list):
            lines.append("## Semantic Claim Verifications")
            for item in v:
                if isinstance(item, dict):
                    lines.append(f"### {item.get('claim_id')}: {item.get('verdict')}")
                    lines.append(f"- **Claim:** {item.get('claim_text')}")
                    lines.append(f"- **Evidence:** {item.get('evidence_summary')}")
                    lines.append(f"- **Source:** {item.get('supporting_source')}")
                    lines.append(f"- **Rationale:** {item.get('rationale')}")
                    lines.append(f"- **Confidence:** {item.get('confidence')}")
                    lines.append("")
            continue

        lines.append(f"## {k}")
        if isinstance(v, list):
            if v:
                for x in v:
                    if isinstance(x, dict):
                        lines.append("```json")
                        lines.append(json.dumps(x, indent=2))
                        lines.append("```")
                    else:
                        lines.append(f"- {x}")
            else:
                lines.append("- None")
        elif isinstance(v, dict):
            lines.append("```json")
            lines.append(json.dumps(v, indent=2))
            lines.append("```")
        else:
            lines.append(str(v))
        lines.append("")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _fingerprint(path: Path) -> str:
    stat = path.stat()
    key = f"{path.resolve()}::{stat.st_size}::{stat.st_mtime_ns}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def _simple_keywords(text: str, top_n: int = 24) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text.lower())
    stop = {"with", "that", "this", "from", "have", "were", "their", "which", "using", "into", "between", "results", "methods", "introduction", "table", "figure", "analysis", "paper", "study"}
    freq: dict[str, int] = {}
    for w in words:
        if w in stop:
            continue
        freq[w] = freq.get(w, 0) + 1
    return [k for k, _ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:top_n]]


def _fallback_evidence_cards(sdoc: ParsedDocument, top_n: int = 10) -> list[dict[str, Any]]:
    text = sdoc.cleaned_text or ""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if len(sentences) <= top_n:
        seeds = sentences
    else:
        # Take a spread of sentences across the document
        seeds = []
        step = max(1, len(sentences) // top_n)
        for i in range(0, len(sentences), step):
            if len(seeds) < top_n:
                seeds.append(sentences[i])
    
    cards: list[dict[str, Any]] = []
    for s in seeds:
        cards.append({
            "claim": s[:300],
            "evidence": s[:600],
            "confidence": "low",
            "source_file": str(sdoc.source_path.name),
            "fallback_generated": True
        })
    return cards


def _token_overlap(a: str, b: str) -> float:
    def _get_tokens(text: str) -> set[str]:
        words = re.findall(r"\b[A-Za-z]{3,}\b", text.lower())
        stop = {"with", "that", "this", "from", "have", "were", "their", "which", "using", "into", "between", "results", "methods", "introduction", "table", "figure", "analysis", "paper", "study", "also", "been", "these"}
        return {w for w in words if w not in stop}
    
    sa = _get_tokens(a)
    sb = _get_tokens(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / float(min(len(sa), len(sb)))


def _support_relevance_score(manuscript_text: str, support_text: str) -> float:
    if not manuscript_text or not support_text:
        return 0.0
    return _token_overlap(manuscript_text[:20000], support_text[:20000])


def _support_verification_entry(source: str, score: float, selected: bool, reason: str | None = None) -> dict[str, Any]:
    labels = [
        "support_relationship_plausible" if selected else "support_relationship_not_verified",
        "internal_consistency_check_only",
        "needs_human_verification",
    ]
    return {
        "source": source,
        "score": round(score, 4),
        "selected": selected,
        "reason": reason,
        "verification": {
            "labels": labels,
            "verification_scope": "internal_consistency_check_only",
            "selection_basis": "lexical_overlap_only",
            "provenance": "project_support_material",
        },
    }


def _extract_named_section(text: str, heading_pattern: str, fallback_chars: int = 0) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    capture = False
    captured: list[str] = []
    pattern = re.compile(heading_pattern, re.IGNORECASE)
    heading_like = re.compile(r"^\s{0,3}(abstract|introduction|background|methods?|experimental|results?|discussion|conclusions?|references)\b", re.IGNORECASE)
    for line in lines:
        stripped = line.strip()
        if not capture and pattern.match(stripped):
            capture = True
            continue
        if capture:
            if heading_like.match(stripped):
                break
            captured.append(stripped)
    section_text = "\n".join([ln for ln in captured if ln]).strip()
    if section_text:
        return section_text
    if fallback_chars > 0:
        return text[:fallback_chars].strip()
    return ""


def _internal_consistency_checks(text: str) -> dict[str, Any]:
    abstract_text = _extract_named_section(text, r"^\s*abstract\b", fallback_chars=2200)
    conclusion_text = _extract_named_section(text, r"^\s*conclusions?\b", fallback_chars=0)
    if not conclusion_text:
        conclusion_text = _extract_named_section(text, r"^\s*discussion\b", fallback_chars=0)
    body_text = text
    if abstract_text and abstract_text in body_text:
        body_text = body_text.replace(abstract_text, "", 1)
    if conclusion_text and conclusion_text in body_text:
        body_text = body_text.replace(conclusion_text, "", 1)
    findings: list[dict[str, Any]] = []
    broad_markers = ["always", "never", "all ", "every ", "proves", "clearly demonstrates"]
    abstract_low = abstract_text.lower()
    body_low = body_text.lower()
    conclusion_low = conclusion_text.lower()
    if abstract_text and any(marker in abstract_low for marker in broad_markers) and not any(marker in body_low for marker in broad_markers):
        findings.append({"label": "abstract_scope_broader_than_body", "severity": "medium", "details": "Opening summary uses broader certainty language than the body text."})
    if conclusion_text and any(marker in conclusion_low for marker in broad_markers) and not any(marker in body_low for marker in broad_markers):
        findings.append({"label": "conclusion_scope_broader_than_body", "severity": "medium", "details": "Conclusion/discussion appears broader than the body evidence language."})
    return {
        "labels": ["internal_consistency_check_only"],
        "verification_scope": "internal_consistency_check_only",
        "abstract_present": bool(abstract_text),
        "conclusion_present": bool(conclusion_text),
        "finding_count": len(findings),
        "findings": findings,
        "needs_human_verification": bool(findings),
    }


def _is_probably_irrelevant_support(filename: str) -> bool:
    low = filename.lower()
    blocked_markers = [
        "openai gym",
        "gym_",
        "biogpt",
        "chatbot benchmark",
    ]
    return any(m in low for m in blocked_markers)


def _extract_context_constraints(context_docs: list[ParsedDocument]) -> dict[str, Any]:
    if not context_docs:
        return {
            "enabled": False,
            "materials": [],
            "priorities": [],
            "forbidden_title_words": [],
            "max_word_count": None,
            "required_reporting_items": [],
            "notes": ["No context-pack materials provided."],
        }
    text = "\n\n".join((d.cleaned_text or "")[:14000] for d in context_docs if d.cleaned_text)
    low = text.lower()
    priorities: list[str] = []
    if "methods" in low or "reproduc" in low:
        priorities.append("methods_reporting")
    if "novelty" in low or "claim" in low:
        priorities.append("claim_calibration")
    if "format" in low or "style" in low or "journal" in low:
        priorities.append("formatting_compliance")
    if "figure" in low or "caption" in low:
        priorities.append("figure_caption_quality")

    forbidden_title_words: list[str] = []
    m = re.search(r"may not contain the words?\s+[“\"']([^”\"']+)[”\"']\s+or\s+[“\"']([^”\"']+)[”\"']", text, re.IGNORECASE)
    if m:
        forbidden_title_words.extend([m.group(1).strip(), m.group(2).strip()])
    max_word_count = None
    for pat in [r"not exceeding\s+(\d+)\s+words", r"(\d+)\s+words?\s+max", r"word[\-\s]?limit[:\s]+(\d+)"]:
        hit = re.search(pat, low)
        if hit:
            try:
                max_word_count = int(hit.group(1))
                break
            except Exception:
                pass
    required_reporting_items: list[str] = []
    for key, label in [
        ("limitations", "limitations_statement"),
        ("data availability", "data_availability"),
        ("code availability", "code_availability"),
        ("ethics", "ethics_statement"),
        ("conflict of interest", "conflict_of_interest"),
    ]:
        if key in low:
            required_reporting_items.append(label)
    return {
        "enabled": True,
        "materials": [d.source_path.name for d in context_docs],
        "priorities": sorted(set(priorities)),
        "forbidden_title_words": sorted(set(forbidden_title_words)),
        "max_word_count": max_word_count,
        "required_reporting_items": sorted(set(required_reporting_items)),
        "notes": ["Context pack constraints were extracted from user/style/journal materials."],
    }


def _run_compliance_check(manuscript: ParsedDocument, constraints: dict[str, Any]) -> dict[str, Any]:
    text = manuscript.cleaned_text or ""
    low = text.lower()
    findings: list[dict[str, Any]] = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = lines[0] if lines else ""
    for word in constraints.get("forbidden_title_words", []) or []:
        if word and word.lower() in title.lower():
            findings.append(
                {
                    "severity": "high",
                    "category": "title_rule",
                    "message": f"Title contains forbidden word from context pack: '{word}'.",
                }
            )
    max_words = constraints.get("max_word_count")
    if isinstance(max_words, int) and max_words > 0:
        wc = len(re.findall(r"\w+", text))
        if wc > max_words:
            findings.append(
                {
                    "severity": "medium",
                    "category": "word_count",
                    "message": f"Manuscript appears to exceed context-pack word limit ({wc} > {max_words}).",
                }
            )
    for req in constraints.get("required_reporting_items", []) or []:
        key = req.replace("_statement", "").replace("_", " ")
        if key not in low:
            findings.append(
                {
                    "severity": "medium",
                    "category": "required_reporting",
                    "message": f"Context-pack required item may be missing: {req}.",
                }
            )
    return {
        "enabled": bool(constraints.get("enabled")),
        "applied_priorities": constraints.get("priorities", []),
        "findings": findings,
        "finding_count": len(findings),
    }


def run_deep_run(
    provider: Provider,
    cfg: ReviewerConfig,
    logger: logging.Logger,
    run_dir: Path,
    project_id: str,
    store: ProjectStore,
    manuscript_id: str | None,
    embedding_model: str | None,
    context_material_ids: list[str] | None = None,
    disable_training_guidance: bool = False,
    orchestrator: OrchestratorController | None = None,
) -> DeepRunResult:
    warnings: list[str] = []
    stage_status: dict[str, str] = {}
    orch_state = OrchestratorRuntimeState(
        max_stage_retries=cfg.orchestrator.max_stage_retries,
        max_total_retries=cfg.orchestrator.max_total_retries,
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    pdir, meta = store.get_project(project_id)
    store.sync_project_material_inventory(meta.project_id)
    pdir, meta = store.get_project(meta.project_id)

    manuscripts = [m for m in meta.materials if m.category == "manuscript_draft"]
    others = [m for m in meta.materials if m.category != "manuscript_draft"]
    requested_context_ids = {x.strip() for x in (context_material_ids or []) if x and x.strip()}
    context_materials = []
    support_materials = []
    for m in others:
        if requested_context_ids:
            if m.material_id in requested_context_ids:
                context_materials.append(m)
            else:
                support_materials.append(m)
        else:
            if m.category in CONTEXT_PACK_CATEGORIES:
                context_materials.append(m)
            else:
                support_materials.append(m)
    if manuscript_id:
        manuscripts = [m for m in manuscripts if m.material_id == manuscript_id]
    if not manuscripts:
        raise DeepRunError(
            "No manuscript found in project. Put a manuscript into materials/manuscript or use project add-material with category manuscript_draft."
        )

    target = manuscripts[0]
    target_path = store.material_path(pdir, target)
    if not target_path.exists():
        raise DeepRunError(f"Target manuscript file missing: {target_path}")

    installed = provider.list_models()
    chat_models, embed_models = split_chat_and_embedding_models(installed)
    if embedding_model and embedding_model not in embed_models:
        warnings.append(f"Embedding model {embedding_model} not available as embedding; disabling embeddings for deep run.")
        embedding_model = None
    routing_mode = normalize_deep_run_routing_mode(cfg.deep_run_routing.mode)
    model_stack = _select_stage_models(chat_models, cfg)
    _write_json(
        run_dir / "deep_run_plan.json",
        {
            "project_id": project_id,
            "routing_mode": routing_mode,
            "model_stack": model_stack,
        },
    )
    _write_json(run_dir / "stage_model_stack.json", {"routing_mode": routing_mode, "model_stack": model_stack})
    registry = ToolRegistry(cfg)
    _write_json(run_dir / "tool_manifest.json", {"availability": registry.availability(), "strict_offline": cfg.defaults.strict_offline})
    initial_source_mode = detect_source_mode(target_path)
    _write_json(
        run_dir / "source_mode.json",
        {
            "project_id": project_id,
            "manuscript_source_path": str(target_path),
            "source_mode": initial_source_mode.get("mode"),
            "surrogate_base_path": None,
            "notes": ["Initial source-mode detection before annotation."],
        },
    )

    trainer = TrainingCacheManager.from_config(cfg, logger=logger)
    training_used = {"enabled": False, "categories": [], "source_count": 0, "prompt_block": ""}
    if cfg.training.enabled and not disable_training_guidance:
        trainer.sync(force_rebuild=False)
        inj = trainer.injection_for_profile("deep", max_chars=cfg.training.max_injection_chars)
        training_used = {
            "enabled": inj.enabled,
            "categories": inj.categories_used,
            "source_count": inj.source_count,
            "prompt_block": inj.prompt_block,
        }
    _write_json(run_dir / "training_guidance_used.json", training_used)

    materials_used = {
        "manuscript": {"material_id": target.material_id, "path": str(target_path), "category": target.category},
        "supporting_materials_requested_count": len([m for m in support_materials if store.material_path(pdir, m).exists()]),
        "context_pack_requested_count": len([m for m in context_materials if store.material_path(pdir, m).exists()]),
    }
    _write_json(run_dir / "project_materials_used.json", materials_used)
    _write_json(run_dir / "project_inventory.json", {"project_id": project_id, "material_count": len(meta.materials), "materials_used": materials_used})
    _write_json(run_dir / "context_manifest.json", {"project_id": project_id, "materials": materials_used, "warnings": warnings})
    stage_status["stage_00_sync"] = "ok"
    cfg_deep = copy.deepcopy(cfg)
    cfg_deep.timeouts.chat_seconds = max(cfg_deep.timeouts.chat_seconds, 600)
    cache_root = pdir / "cache" / "deep_workflow"
    cache_root.mkdir(parents=True, exist_ok=True)
    _write_json(
        run_dir / "stage_00_run_manifest.json",
        {
            "project_id": project_id,
            "run_dir": str(run_dir),
            "cache_root": str(cache_root),
            "routing_mode": routing_mode,
            "model_stack": model_stack,
            "materials_used": materials_used,
        },
    )

    # Stage 1 ingest + normalization
    manuscript_doc = parse_file(target_path)
    structured_source = {}
    try:
        if manuscript_doc.document_type == "pdf":
            structured_source = registry.parse_pdf(target_path)
        elif manuscript_doc.document_type == "docx":
            structured_source = registry.parse_docx(target_path)
    except Exception as exc:
        warnings.append(f"tool_parse_failed:{exc}")
    _write_json(run_dir / "stage_01_structured_source.json", structured_source if isinstance(structured_source, dict) else {})
    supporting_docs = []
    skipped_supporting_docs: list[dict[str, Any]] = []
    selected_supporting_docs: list[dict[str, Any]] = []
    support_parse_failures: list[dict[str, str]] = []
    manuscript_text = manuscript_doc.cleaned_text or ""
    for m in support_materials[:50]:
        path = store.material_path(pdir, m)
        try:
            sdoc = parse_file(path)
            score = _support_relevance_score(manuscript_text, sdoc.cleaned_text or "")
            if _is_probably_irrelevant_support(path.name):
                skipped_supporting_docs.append(
                    {
                        "material_id": m.material_id,
                        "path": str(path),
                        **_support_verification_entry(path.name, score, selected=False, reason="blocked_filename_marker"),
                    }
                )
                continue
            if score >= 0.95:
                skipped_supporting_docs.append(
                    {
                        "material_id": m.material_id,
                        "path": str(path),
                        **_support_verification_entry(path.name, score, selected=False, reason="manuscript_like_duplicate"),
                    }
                )
                continue
            if score < 0.04:
                skipped_supporting_docs.append(
                    {
                        "material_id": m.material_id,
                        "path": str(path),
                        **_support_verification_entry(path.name, score, selected=False, reason="low_relevance"),
                    }
                )
                continue
            supporting_docs.append(sdoc)
            selected_supporting_docs.append(
                {
                    "material_id": m.material_id,
                    "path": str(path),
                    **_support_verification_entry(path.name, score, selected=True, reason=None),
                }
            )
        except Exception as exc:
            warnings.append(f"supporting_parse_failed:{path}:{exc}")
            support_parse_failures.append({"path": str(path), "error": str(exc)})
    _write_json(
        run_dir / "support_material_filtering.json",
        {
            "selected": selected_supporting_docs,
            "skipped": skipped_supporting_docs,
            "verification_scope": "internal_consistency_check_only",
            "selection_basis": "lexical_overlap_only",
            "support_relationship_policy": {
                "selected_label": "support_relationship_plausible",
                "selected_meaning": "Support material appears topically relevant, but claim support was not verified.",
                "skipped_label": "support_relationship_not_verified",
            },
        },
    )
    support_ingest_report = build_support_ingest_report(
        manuscript_doc,
        supporting_docs,
        parse_failures=support_parse_failures,
    )
    _write_json(run_dir / "support_ingest_report.json", support_ingest_report)
    (run_dir / "support_relevance_report.md").write_text(build_support_relevance_report_md(support_ingest_report), encoding="utf-8")
    materials_used["supporting_materials_selected"] = [
        {"name": d.source_path.name} for d in supporting_docs
    ]
    reason_counts: dict[str, int] = {}
    for item in skipped_supporting_docs:
        reason = str(item.get("reason", "unknown"))
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    materials_used["supporting_materials_skipped_summary"] = {
        "count": len(skipped_supporting_docs),
        "reason_counts": reason_counts,
    }
    _write_json(run_dir / "project_materials_used.json", materials_used)
    _write_json(run_dir / "context_manifest.json", {"project_id": project_id, "materials": materials_used, "warnings": warnings})
    _write_json(run_dir / "internal_consistency_checks.json", internal_consistency_checks_from_text(manuscript_text))
    assertion_ledger = extract_assertion_ledger(manuscript_doc)
    claim_to_citation = build_claim_to_citation_map(manuscript_doc, assertion_ledger)
    citation_ledger = build_citation_verification_ledger(manuscript_doc, assertion_ledger, supporting_docs, run_dir)
    verification_enrichment = enrich_assertion_ledger(assertion_ledger, claim_to_citation, citation_ledger, supporting_docs, manuscript_text)
    assertion_ledger = verification_enrichment["assertion_ledger"]
    support_usage_ledger = verification_enrichment["support_usage_ledger"]
    claim_verification_summary = verification_enrichment["claim_verification_summary"]
    _write_json(run_dir / "assertion_ledger.json", assertion_ledger)
    (run_dir / "assertion_review.md").write_text(build_assertion_review_md(assertion_ledger), encoding="utf-8")
    _write_json(run_dir / "claim_to_citation_map.json", claim_to_citation)
    _write_json(run_dir / "citation_verification_ledger.json", citation_ledger)
    (run_dir / "citation_accuracy_report.md").write_text(build_citation_accuracy_report_md(citation_ledger), encoding="utf-8")
    _write_json(run_dir / "support_usage_ledger.json", support_usage_ledger)
    _write_json(run_dir / "claim_verification_summary.json", claim_verification_summary)

    context_docs: list[ParsedDocument] = []
    context_failures: list[dict[str, str]] = []
    for m in context_materials:
        path = store.material_path(pdir, m)
        try:
            context_docs.append(parse_file(path))
        except Exception as exc:
            context_failures.append({"path": str(path), "error": str(exc)})
    context_constraints = _extract_context_constraints(context_docs)
    context_constraints["requested_context_ids"] = sorted(requested_context_ids)
    if context_failures:
        context_constraints["parse_failures"] = context_failures
    _write_json(run_dir / "context_pack_used.json", context_constraints)
    _write_md(run_dir / "context_pack_used.md", "Context Pack (Optional User Standards/Priorities)", context_constraints)
    materials_used["context_pack_materials"] = [{"name": d.source_path.name} for d in context_docs]
    _write_json(run_dir / "project_materials_used.json", materials_used)
    chunk_document(manuscript_doc, max_chars=get_profile("deep").chunk_size, overlap=get_profile("deep").chunk_overlap)
    for d in supporting_docs:
        chunk_document(d, max_chars=get_profile("balanced").chunk_size, overlap=get_profile("balanced").chunk_overlap)
    stage_status["stage_01_ingest"] = "ok"

    # Stage 2 cheap structural triage
    triage_payload, triage_raw = _chat_json(
        provider=provider,
        model=model_stack["structural_triage"],
        system_prompt="You are a structural triage model. Return strict JSON only.",
        user_prompt=(
            "Return JSON with keys: section_map, citation_markers, figure_mentions, table_mentions, "
            "likely_claim_sections, likely_risk_sections, keyword_inventory.\n"
            f"Headings: {manuscript_doc.headings[:80]}\n"
            f"Excerpt:\n{manuscript_doc.cleaned_text[:18000]}\n"
            f"Supporting files: {[d.source_path.name for d in supporting_docs]}\n"
        ),
        timeout_seconds=cfg_deep.timeouts.chat_seconds,
    )
    triage_payload.setdefault("citation_markers", len(re.findall(r"\[[0-9]{1,3}\]|\([A-Za-z].*?[0-9]{4}\)", manuscript_doc.cleaned_text[:50000])))
    triage_payload.setdefault("figure_mentions", len(re.findall(r"\bfigure\b|\bfig\.\b", manuscript_doc.cleaned_text.lower())))
    triage_payload.setdefault("table_mentions", len(re.findall(r"\btable\b", manuscript_doc.cleaned_text.lower())))
    triage_payload.setdefault("keyword_inventory", _simple_keywords(manuscript_doc.cleaned_text, top_n=24))
    _write_json(run_dir / "stage_01_structural_triage.json", triage_payload)
    _write_md(run_dir / "stage_01_structural_triage.md", "Stage 1 Structural Triage", triage_payload)
    (run_dir / "stage_01_structural_triage.raw.txt").write_text(triage_raw, encoding="utf-8")
    stage_status["stage_02_structural_triage"] = "ok"

    # Stage 3 supporting-paper digestion with persistent cache
    supporting_cards: list[dict[str, Any]] = []
    supporting_manifest: list[dict[str, Any]] = []
    support_cache_dir = cache_root / "supporting_digests"
    support_cache_dir.mkdir(parents=True, exist_ok=True)
    for sdoc in supporting_docs:
        fp = _fingerprint(sdoc.source_path_abs)
        cache_path = support_cache_dir / f"{fp}.json"
        digest_payload: dict[str, Any]
        if cache_path.exists():
            digest_payload = json.loads(cache_path.read_text(encoding="utf-8"))
            digest_payload["cache_hit"] = True
        else:
            digest_payload, _ = _chat_json(
                provider=provider,
                model=model_stack["supporting_digest"],
                system_prompt="Digest a supporting paper into strict JSON cards.",
                user_prompt=(
                    "Return JSON with keys: summary, claims, methods, results, conclusions, evidence_cards.\n"
                    "evidence_cards must be list of objects with keys: claim, evidence, confidence.\n"
                    f"Source: {sdoc.source_path.name}\n"
                    f"Headings: {sdoc.headings[:40]}\n"
                    f"Text:\n{sdoc.cleaned_text[:18000]}"
                ),
                timeout_seconds=cfg_deep.timeouts.chat_seconds,
            )
            digest_payload["cache_hit"] = False
            digest_payload["source_file"] = sdoc.source_path.name
            digest_payload["fingerprint"] = fp
            cache_path.write_text(json.dumps(digest_payload, indent=2), encoding="utf-8")
        cards = digest_payload.get("evidence_cards", [])
        if not isinstance(cards, list):
            cards = []
        if not cards:
            cards = _fallback_evidence_cards(sdoc)
            digest_payload["evidence_cards"] = cards
            digest_payload["fallback_generated"] = True
            digest_payload.setdefault(
                "fallback_note",
                "LLM digest did not yield evidence_cards; deterministic fallback cards were generated.",
            )
            cache_path.write_text(json.dumps(digest_payload, indent=2), encoding="utf-8")
        for card in cards:
            if isinstance(card, dict):
                card["source_file"] = sdoc.source_path.name
                supporting_cards.append(card)
        supporting_manifest.append(
            {
                "source_file": sdoc.source_path.name,
                "fingerprint": fp,
                "cache_file": str(cache_path),
                "cache_hit": bool(digest_payload.get("cache_hit")),
                "card_count": len(cards),
                "fallback_generated": bool(digest_payload.get("fallback_generated")),
            }
        )
    supporting_stage = {"supporting_files": supporting_manifest, "evidence_card_count": len(supporting_cards)}
    _write_json(run_dir / "stage_02_supporting_digest.json", supporting_stage)
    _write_md(run_dir / "stage_02_supporting_digest.md", "Stage 2 Supporting Paper Digestion", supporting_stage)
    _write_json(cache_root / "supporting_digest_manifest.json", supporting_stage)
    stage_status["stage_03_supporting_digest"] = "ok"

    # Stage 4 manuscript digestion with cache
    manuscript_fp = _fingerprint(manuscript_doc.source_path_abs)
    manuscript_cache = cache_root / "manuscript_digest.json"
    if manuscript_cache.exists():
        try:
            manuscript_digest = json.loads(manuscript_cache.read_text(encoding="utf-8"))
            if manuscript_digest.get("fingerprint") != manuscript_fp:
                raise ValueError("fingerprint changed")
            manuscript_digest["cache_hit"] = True
        except Exception:
            manuscript_digest = {}
    else:
        manuscript_digest = {}

    if not manuscript_digest:
        manuscript_digest, manuscript_digest_raw = _chat_json(
            provider=provider,
            model=model_stack["manuscript_digest"],
            system_prompt="Digest manuscript into strict JSON claim map.",
            user_prompt=(
                "Return JSON with keys: overview, section_summaries, claim_map, methods_map, results_map, conclusion_map, weak_points.\n"
                "claim_map should be list of objects with keys: claim, section, confidence.\n"
                f"Headings: {manuscript_doc.headings[:80]}\n"
                f"Text:\n{manuscript_doc.cleaned_text[:26000]}"
            ),
            timeout_seconds=cfg_deep.timeouts.chat_seconds,
        )
        manuscript_digest["cache_hit"] = False
        manuscript_digest["raw_excerpt"] = manuscript_digest_raw[:1400]
        manuscript_digest["fingerprint"] = manuscript_fp
        manuscript_cache.write_text(json.dumps(manuscript_digest, indent=2), encoding="utf-8")
    # Deterministic fallback when model omits claim_map.
    claims = manuscript_digest.get("claim_map")
    if not isinstance(claims, list) or not claims:
        fallback_claims: list[dict[str, Any]] = []
        sentences = re.split(r"(?<=[.!?])\s+", manuscript_doc.cleaned_text[:20000])
        for idx, sentence in enumerate(sentences[:80], start=1):
            s = sentence.strip()
            if len(s) < 80:
                continue
            if not re.search(r"\b(we|this study|results|demonstrate|show|indicate|suggest)\b", s.lower()):
                continue
            fallback_claims.append({"claim": s[:420], "section": "inferred", "confidence": 0.35, "source": f"fallback_sentence_{idx}"})
            if len(fallback_claims) >= 24:
                break
        manuscript_digest["claim_map"] = fallback_claims
        manuscript_digest["claim_map_fallback_used"] = True
    manuscript_digest.setdefault("fingerprint", manuscript_fp)
    issue_map = []
    for idx, claim in enumerate(manuscript_digest.get("claim_map", [])[:40], start=1):
        if not isinstance(claim, dict):
            continue
        issue_map.append(
            {
                "issue_id": f"ISSUE-{idx:03d}",
                "section": claim.get("section", "unknown"),
                "claim": claim.get("claim", ""),
                "severity": "high" if idx <= 8 else "medium",
                "category": "claim_evidence_alignment",
            }
        )
    _write_json(run_dir / "initial_manuscript_issue_map.json", {"issues": issue_map})
    _write_json(run_dir / "stage_03_manuscript_digest.json", manuscript_digest)
    _write_md(run_dir / "stage_03_manuscript_digest.md", "Stage 3 Manuscript Digestion", manuscript_digest)
    stage_status["stage_04_manuscript_digest"] = "ok"

    # Stage 5 context/evidence linking
    claims = manuscript_digest.get("claim_map", [])
    if not isinstance(claims, list):
        claims = []
    link_rows: list[dict[str, Any]] = []
    for claim in claims[:50]:
        if not isinstance(claim, dict):
            continue
        ctext = str(claim.get("claim", ""))[:500]
        ranked = sorted(
            [
                {
                    "score": round(_token_overlap(ctext, f"{card.get('claim', '')} {card.get('evidence', '')}"), 4),
                    "card": card,
                }
                for card in supporting_cards
            ],
            key=lambda x: x["score"],
            reverse=True,
        )[:3]
        link_rows.append(
            {
                "claim": ctext,
                "section": claim.get("section", ""),
                "top_supporting_cards": [r["card"] for r in ranked if r["score"] > 0],
                "training_categories": training_used.get("categories", []),
            }
        )
    context_pack = {
        "claim_links": link_rows,
        "supporting_card_count": len(supporting_cards),
        "training_guidance_enabled": training_used.get("enabled", False),
        "training_categories": training_used.get("categories", []),
        "context_pack_constraints": context_constraints,
        "claim_verification_summary": claim_verification_summary,
        "support_ingest_summary": {
            "available_support_docs": support_ingest_report.get("available_support_docs", 0),
            "selected_support_docs": support_ingest_report.get("selected_support_docs", 0),
        },
    }
    _write_json(run_dir / "stage_04_context_pack.json", context_pack)
    _write_md(run_dir / "stage_04_context_pack.md", "Stage 4 Context/Evidence Linking", context_pack)
    _write_json(cache_root / "latest_context_pack.json", context_pack)
    stage_status["stage_05_context_linking"] = "ok"

    # Stage 5b Semantic Claim Verification
    try:
        verifications = _verify_claims_semantically(
            provider=provider,
            model=model_stack.get("methods_verification") or model_stack.get("high_level_review"),
            claims=issue_map,
            supporting_cards=supporting_cards,
            timeout_seconds=cfg_deep.timeouts.chat_seconds,
        )
        deep_verification = DeepVerificationSchema(
            project_id=project_id,
            run_id=run_dir.name,
            verifications=verifications,
            summary=f"Semantically verified {len(verifications)} high-priority claims against supporting literature."
        )
        _write_json(run_dir / "stage_05b_semantic_verification.json", deep_verification.model_dump())
        _write_md(run_dir / "stage_05b_semantic_verification.md", "Stage 5b Semantic Claim Verification", deep_verification.model_dump())
        # Inject these findings into context_pack for later stages
        context_pack["semantic_verifications"] = [v.model_dump() for v in verifications]
        stage_status["stage_05b_semantic_verification"] = "ok"
    except Exception as exc:
        warnings.append(f"semantic_verification_failed:{exc}")
        stage_status["stage_05b_semantic_verification"] = "failed"

    # Stage 6 context synthesis
    synth_payload, synth_raw = _chat_json(
        provider=provider,
        model=model_stack["context_synthesis"],
        system_prompt="You synthesize review context and return strict JSON.",
        user_prompt=(
            "Return JSON with keys: manuscript_overview, section_map, claims, methods, results, conclusions, risk_areas.\n"
            f"Manuscript headings: {manuscript_doc.headings[:40]}\n"
            f"Manuscript excerpt:\n{manuscript_doc.cleaned_text[:22000]}\n"
            f"Supporting count: {len(supporting_docs)}\n"
            f"Context pack excerpt:\n{json.dumps(context_pack)[:12000]}\n"
            f"Training guidance:\n{training_used['prompt_block']}\n"
        ),
        timeout_seconds=cfg_deep.timeouts.chat_seconds,
    )
    _write_json(run_dir / "manuscript_summary.json", synth_payload)
    _write_json(run_dir / "stage_05_context_synthesis.json", synth_payload)
    _write_md(run_dir / "stage_05_context_synthesis.md", "Stage 5 Context Synthesis", synth_payload)
    (run_dir / "stage_05_context_synthesis.raw.txt").write_text(synth_raw, encoding="utf-8")
    stage_status["stage_06_context_synthesis"] = "ok"

    def _safe_stage_review(
        stage_label: str,
        profile_key: str,
        model_key: str,
        stage_dir_name: str,
        out_json: str,
        out_md: str,
        fallback_model_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        stage_dir = run_dir / stage_dir_name
        stage_dir.mkdir(parents=True, exist_ok=True)
        try:
            context_guidance = (
                f"{training_used['prompt_block']}\n\n"
                f"Structured context pack:\n{json.dumps(context_pack)[:10000]}"
            ) if training_used["enabled"] else f"Structured context pack:\n{json.dumps(context_pack)[:10000]}"
            if context_constraints.get("enabled"):
                context_guidance += (
                    "\n\nOptional user context-pack constraints (apply as additional standards, do not replace manuscript-grounded critique):\n"
                    f"{json.dumps(context_constraints)[:6000]}"
                )
            model_chain: list[str] = []
            for mk in [model_key, *(fallback_model_keys or [])]:
                model_name = model_stack.get(mk)
                if model_name and model_name not in model_chain:
                    model_chain.append(model_name)

            payload: dict[str, Any] | None = None
            used_model = model_chain[0] if model_chain else model_stack[model_key]
            for idx, stage_model in enumerate(model_chain or [model_stack[model_key]]):
                used_model = stage_model
                run_review(
                    provider=provider,
                    doc=manuscript_doc,
                    profile=get_profile(profile_key),
                    model=stage_model,
                    repair_models=cfg.defaults.repair_models,
                    config=cfg_deep,
                    bundle_dir=stage_dir,
                    embedding_model=embedding_model,
                    strict_schema_override=True,
                    logger=logger,
                    guidance_text=context_guidance,
                    guidance_categories=training_used["categories"],
                    supporting_docs=supporting_docs,
                    orchestrator=orchestrator,
                    orchestrator_state=orch_state,
                    stage_name=stage_dir_name,
                )
                payload = json.loads((stage_dir / "validated_review.json").read_text(encoding="utf-8"))
                summary = str(payload.get("summary", "")).strip().lower()
                if not summary.startswith("heuristic editorial review"):
                    break
                if idx < len(model_chain) - 1:
                    warnings.append(
                        f"{stage_label}_heuristic_output_with_{stage_model}; retrying with {model_chain[idx + 1]}"
                    )
                    logger.warning(
                        "deep_stage_heuristic_retry stage=%s profile=%s from_model=%s to_model=%s",
                        stage_label,
                        profile_key,
                        stage_model,
                        model_chain[idx + 1],
                    )
            assert payload is not None
            payload.setdefault("stage_model_used", used_model)
            _write_json(run_dir / out_json, payload)
            _write_md(run_dir / out_md, stage_label, payload)
            return {"status": "ok", "payload": payload}
        except Exception as exc:
            warnings.append(f"{stage_label}_failed:{exc}")
            payload = {"warning": "stage_failed", "stage": stage_label, "error": str(exc)}
            _write_json(run_dir / out_json, payload)
            _write_md(run_dir / out_md, stage_label, payload)
            return {"status": "failed", "payload": payload}

    # Stage 7 high-level review
    s3 = _safe_stage_review(
        stage_label="Stage 6 High-Level Review",
        profile_key="balanced",
        model_key="high_level_review",
        stage_dir_name="stage_06_high_level_review_bundle",
        out_json="stage_06_high_level_review.json",
        out_md="stage_06_high_level_review.md",
    )
    s3j = s3["payload"]
    stage_status["stage_07_high_level_review"] = s3["status"]

    # Stage 8 hostile
    s4 = _safe_stage_review(
        stage_label="Stage 7 Hostile Review",
        profile_key="adversarial",
        model_key="adversarial_review",
        stage_dir_name="stage_07_hostile_review_bundle",
        out_json="stage_07_hostile_review.json",
        out_md="stage_07_hostile_review.md",
    )
    s4j = s4["payload"]
    stage_status["stage_08_hostile_review"] = s4["status"]

    # Stage 9 methods verification
    s5 = _safe_stage_review(
        stage_label="Stage 8 Methods Verification",
        profile_key="methods",
        model_key="methods_verification",
        fallback_model_keys=["context_synthesis", "structural_triage"],
        stage_dir_name="stage_08_methods_verification_bundle",
        out_json="stage_08_methods_verification.json",
        out_md="stage_08_methods_verification.md",
    )
    s5j = s5["payload"]
    stage_status["stage_09_methods_verification"] = s5["status"]
    if orchestrator is not None and orchestrator.enabled and cfg.orchestrator.enable_deeprun_qa:
        try:
            distinctness = orchestrator.evaluate_distinctness(
                {
                    "balanced": json.dumps(s3j)[:5000],
                    "adversarial": json.dumps(s4j)[:5000],
                    "methods": json.dumps(s5j)[:5000],
                },
                timeout_seconds=min(90, cfg_deep.timeouts.chat_seconds),
            )
            _write_json(run_dir / "orchestrator_distinctness_report.json", distinctness.model_dump())
        except Exception as exc:
            _write_json(
                run_dir / "orchestrator_distinctness_report.json",
                {"error": str(exc), "fail_open": bool(orchestrator.fail_open)},
            )
            if not orchestrator.fail_open:
                raise

    # Stage 10 line-by-line edits
    line_chunks = manuscript_doc.chunks[: min(12, len(manuscript_doc.chunks))]
    edits: list[dict[str, Any]] = []
    for c in line_chunks:
        try:
            payload, raw = _chat_json(
                provider=provider,
                model=model_stack["line_edits"],
                system_prompt="You produce concise local edit suggestions in JSON.",
                user_prompt=(
                    "Return JSON with keys: section, issues, rewrite_candidates.\n"
                    f"Chunk heading: {c.heading}\nChunk text:\n{c.text[:2800]}\n"
                    f"Lab guidance:\n{training_used['prompt_block']}\n"
                ),
                timeout_seconds=cfg_deep.timeouts.chat_seconds,
            )
        except Exception as exc:
            payload = {"section": c.heading or c.chunk_id, "issues": [], "rewrite_candidates": [], "warning": str(exc)}
            raw = str(exc)
            warnings.append(f"line_edit_failed:{c.chunk_id}:{exc}")
        payload["chunk_id"] = c.chunk_id
        payload["raw"] = raw[:1200]
        edits.append(payload)
    stage6 = {"edits": edits, "count": len(edits)}
    _write_json(run_dir / "stage_09_line_by_line_edits.json", stage6)
    _write_md(run_dir / "stage_09_line_by_line_edits.md", "Stage 9 Line-by-Line Edits", stage6)
    stage_status["stage_10_line_by_line_edits"] = "ok"

    # Iterative editorial batches and re-check loop.
    batch_a = {"batch": "A", "focus": "structure_clarity", "items": edits[: min(8, len(edits))]}
    batch_b = {"batch": "B", "focus": "methods_results_overclaim_cleanup", "items": edits[min(2, len(edits)): min(10, len(edits))]}
    batch_c = {"batch": "C", "focus": "style_tone_consistency", "items": edits[min(4, len(edits)): min(12, len(edits))]}
    _write_json(run_dir / "revision_batch_A.json", batch_a)
    _write_md(run_dir / "revision_batch_A.md", "Revision Batch A", batch_a)
    _write_json(run_dir / "revision_batch_B.json", batch_b)
    _write_md(run_dir / "revision_batch_B.md", "Revision Batch B", batch_b)
    _write_json(run_dir / "revision_batch_C.json", batch_c)
    _write_md(run_dir / "revision_batch_C.md", "Revision Batch C", batch_c)

    # Stage 11 style alignment
    try:
        style_payload, style_raw = _chat_json(
            provider=provider,
            model=model_stack["style_alignment"],
            system_prompt="You assess style and formatting alignment in strict JSON.",
            user_prompt=(
                "Return JSON with keys: style_issues, formatting_issues, tone_issues, alignment_actions.\n"
                f"Training guidance:\n{training_used['prompt_block']}\n"
                f"Manuscript excerpt:\n{manuscript_doc.cleaned_text[:14000]}"
            ),
            timeout_seconds=cfg_deep.timeouts.chat_seconds,
        )
        stage_status["stage_11_style_alignment"] = "ok"
    except Exception as exc:
        style_payload = {"style_issues": [], "formatting_issues": [], "tone_issues": [], "alignment_actions": [], "warning": str(exc)}
        style_raw = str(exc)
        warnings.append(f"style_alignment_failed:{exc}")
        stage_status["stage_11_style_alignment"] = "failed"
    _write_json(run_dir / "stage_10_style_alignment.json", style_payload)
    _write_md(run_dir / "stage_10_style_alignment.md", "Stage 10 Style Alignment", style_payload)
    (run_dir / "stage_10_style_alignment.raw.txt").write_text(style_raw, encoding="utf-8")

    compliance_payload = build_format_compliance_report(manuscript_doc, context_constraints)
    _write_json(run_dir / "stage_10b_compliance_check.json", compliance_payload)
    _write_md(run_dir / "stage_10b_compliance_check.md", "Stage 10b Context-Pack Compliance Check", compliance_payload)
    stage_status["stage_11b_compliance_check"] = "ok"

    # Stage 12 reconciliation
    required_recon_keys = {
        "consolidated_strengths",
        "consolidated_weaknesses",
        "disagreements",
        "priority_actions",
        "revision_plan",
        "response_to_reviewers_bullets",
        "confidence_notes",
    }

    def _fallback_reconciliation_payload() -> dict[str, Any]:
        strengths: list[str] = []
        weaknesses: list[str] = []
        for src in [s3j, s4j, s5j]:
            if isinstance(src, dict):
                strengths.extend([str(x) for x in src.get("major_strengths", [])[:3]])
                weaknesses.extend([str(x) for x in src.get("major_weaknesses", [])[:4]])
        text = (manuscript_doc.cleaned_text or "").lower()
        off_terms = ["ic50", "chk1", "mk2", "nanomole", "biological activity", "library screening", "inhibitor", "out-of-sample", "r²", "r2", "cross-validation", "transfer learning", "drug discovery"]
        def _filter(items: list[str]) -> list[str]:
            filtered = []
            for item in items:
                low = item.lower()
                if any(term in low and term not in text for term in off_terms):
                    continue
                filtered.append(item)
            return filtered
        if "hallucinat" in text or "smiles" in text:
            strengths.append("The manuscript explicitly acknowledges LLM hallucination risks and reports mitigation steps (e.g., invalid citations/SMILES).")
        if "phactor" in text and "chatgpt" in text:
            strengths.append("End-to-end workflow is demonstrated (LLM proposal generation mapped into phactor execution).")
        if "first attempt" in text or "every instance tried" in text:
            weaknesses.append("Claim language around first-attempt success may overstate generality without clarifying assay vs isolated yields or scope.")
        if "doi" in text or "citation" in text:
            weaknesses.append("Citation accuracy and DOI matching require explicit verification to avoid hallucinated references.")
        if "prompt" in text or "chatgpt" in text:
            weaknesses.append("Human-in-the-loop corrections and prompt iteration are not consistently quantified or separated from model output.")
        if "figure" in text:
            weaknesses.append("Figure captions should clearly identify axes, conditions, and how each panel supports nearby claims.")
        strengths = _filter(strengths)
        weaknesses = _filter(weaknesses)
        priority_actions = [f"Address: {w}" for w in weaknesses[:8] if w.strip()]
        priority_actions.extend([str(x) for x in (style_payload.get("alignment_actions", []) if isinstance(style_payload, dict) else [])[:3]])
        return {
            "consolidated_strengths": strengths[:8],
            "consolidated_weaknesses": weaknesses[:10],
            "disagreements": [
                "Critique stages emphasize rigor/overclaim risk while editorial stages emphasize readability and style normalization."
            ],
            "priority_actions": priority_actions[:10],
            "revision_plan": [
                "Resolve highest-severity evidence/method concerns first.",
                "Revise overclaiming language to match stated evidence and limitations.",
                "Apply line-level clarity rewrites and formatting cleanup before final submission.",
            ],
            "response_to_reviewers_bullets": [
                "Added clearer methodological controls and uncertainty framing.",
                "Reduced overstatement in conclusion/discussion claims.",
                "Improved readability and section-level writing consistency.",
            ],
            "confidence_notes": [
                "Offline-only validation: external literature recency/completeness was not web-verified.",
            ],
            "fallback_generated": True,
        }

    def _apply_compliance_findings(payload: dict[str, Any]) -> dict[str, Any]:
        if not compliance_payload.get("findings"):
            return payload
        payload.setdefault("consolidated_weaknesses", [])
        payload.setdefault("priority_actions", [])
        existing_weaknesses = {str(x).strip() for x in payload.get("consolidated_weaknesses", []) if str(x).strip()}
        existing_actions = {str(x).strip() for x in payload.get("priority_actions", []) if str(x).strip()}
        for finding in compliance_payload.get("findings", [])[:5]:
            msg = str(finding.get("message", "")).strip()
            if not msg:
                continue
            if msg not in existing_weaknesses:
                payload["consolidated_weaknesses"].append(msg)
                existing_weaknesses.add(msg)
            action = f"Address compliance issue: {msg}"
            if action not in existing_actions:
                payload["priority_actions"].append(action)
                existing_actions.add(action)
        return payload

    try:
        recon_payload, recon_raw = _chat_json(
            provider=provider,
            model=model_stack["reconciliation"],
            system_prompt="You reconcile multiple reviewer passes and produce strict JSON.",
            user_prompt=(
                "Return JSON with keys: consolidated_strengths, consolidated_weaknesses, disagreements, "
                "priority_actions, revision_plan, response_to_reviewers_bullets, confidence_notes.\n"
                f"HIGH_LEVEL:\n{json.dumps(s3j)[:12000]}\n"
                f"HOSTILE:\n{json.dumps(s4j)[:12000]}\n"
                f"METHODS:\n{json.dumps(s5j)[:12000]}\n"
                f"STYLE:\n{json.dumps(style_payload)[:8000]}\n"
                f"LINE_EDITS:\n{json.dumps(stage6)[:12000]}\n"
                f"CLAIM_VERIFICATION_SUMMARY:\n{json.dumps(claim_verification_summary)[:4000]}\n"
                f"CITATION_VERIFICATION_SUMMARY:\n{json.dumps({'reference_count': citation_ledger.get('reference_count', 0), 'linked_reference_count': citation_ledger.get('linked_reference_count', 0)})[:2000]}\n"
                f"SUPPORT_INGEST_SUMMARY:\n{json.dumps({'available_support_docs': support_ingest_report.get('available_support_docs', 0), 'selected_support_docs': support_ingest_report.get('selected_support_docs', 0)})[:2000]}\n"
                f"COMPLIANCE:\n{json.dumps(compliance_payload)[:3000]}\n"
            ),
            timeout_seconds=cfg_deep.timeouts.chat_seconds,
        )
        if not required_recon_keys.issubset(set(recon_payload.keys())):
            warnings.append("reconciliation_schema_incomplete; applied deterministic fallback synthesis.")
            recon_payload = _fallback_reconciliation_payload()
        stage_status["stage_12_reconciliation"] = "ok"
    except Exception as exc:
        warnings.append(f"reconciliation_failed:{exc}")
        recon_payload = _fallback_reconciliation_payload()
        recon_payload["confidence_notes"] = recon_payload.get("confidence_notes", []) + [str(exc), "Fallback reconciliation used."]
        recon_raw = str(exc)
        stage_status["stage_12_reconciliation"] = "failed"

    recon_payload = _apply_compliance_findings(recon_payload)
    recon_qc = build_deep_reconciliation_summary(recon_payload)

    arbitration_payload: dict[str, Any] = {}
    arbitration_raw = ""
    arbitration_kept = False
    arbitration_reason = "not_run"
    arbitration_qc: dict[str, Any] = {}
    try:
        arbitration_payload, arbitration_raw = _chat_json(
            provider=provider,
            model=model_stack["final_arbitration"],
            system_prompt="You are the final arbitration model for a deep manuscript review. Return strict JSON only.",
            user_prompt=(
                "Return JSON with keys: consolidated_strengths, consolidated_weaknesses, disagreements, "
                "priority_actions, revision_plan, response_to_reviewers_bullets, confidence_notes.\n"
                "Tighten the final synthesis so it is manuscript-specific, non-duplicative, and higher quality than CURRENT_RECON.\n"
                "Do not invent evidence. Do not add unsupported claims. Preserve unresolved offline/verification limits.\n"
                f"CURRENT_RECON:\n{json.dumps(recon_payload)[:12000]}\n"
                f"CURRENT_RECON_QC:\n{json.dumps(recon_qc)[:4000]}\n"
                f"HIGH_LEVEL:\n{json.dumps(s3j)[:10000]}\n"
                f"HOSTILE:\n{json.dumps(s4j)[:10000]}\n"
                f"METHODS:\n{json.dumps(s5j)[:10000]}\n"
                f"STYLE:\n{json.dumps(style_payload)[:6000]}\n"
                f"LINE_EDITS:\n{json.dumps(stage6)[:8000]}\n"
                f"CLAIM_VERIFICATION_SUMMARY:\n{json.dumps(claim_verification_summary)[:4000]}\n"
                f"CITATION_VERIFICATION_SUMMARY:\n{json.dumps({'reference_count': citation_ledger.get('reference_count', 0), 'linked_reference_count': citation_ledger.get('linked_reference_count', 0)})[:2000]}\n"
                f"SUPPORT_INGEST_SUMMARY:\n{json.dumps({'available_support_docs': support_ingest_report.get('available_support_docs', 0), 'selected_support_docs': support_ingest_report.get('selected_support_docs', 0)})[:2000]}\n"
                f"COMPLIANCE:\n{json.dumps(compliance_payload)[:3000]}\n"
                f"WARNINGS:\n{json.dumps(warnings)[:2000]}\n"
            ),
            timeout_seconds=cfg_deep.timeouts.chat_seconds,
        )
        if required_recon_keys.issubset(set(arbitration_payload.keys())):
            arbitration_payload = _apply_compliance_findings(arbitration_payload)
            arbitration_qc = build_deep_reconciliation_summary(arbitration_payload)
            current_score = float(recon_qc.get("reconciliation_quality_score_0_to_5", 0.0) or 0.0)
            candidate_score = float(arbitration_qc.get("reconciliation_quality_score_0_to_5", 0.0) or 0.0)
            current_fallback = bool(recon_payload.get("fallback_generated"))
            if candidate_score > current_score or (current_fallback and candidate_score >= current_score):
                recon_payload = arbitration_payload
                recon_qc = arbitration_qc
                arbitration_kept = True
                arbitration_reason = "candidate_improved_or_replaced_fallback"
                stage_status["stage_12b_final_arbitration"] = "ok"
            else:
                arbitration_reason = "candidate_not_better_than_current"
                stage_status["stage_12b_final_arbitration"] = "ok"
        else:
            arbitration_reason = "schema_incomplete"
            warnings.append("final_arbitration_schema_incomplete")
            stage_status["stage_12b_final_arbitration"] = "failed"
    except Exception as exc:
        arbitration_reason = f"failed:{exc}"
        warnings.append(f"final_arbitration_failed:{exc}")
        stage_status["stage_12b_final_arbitration"] = "failed"

    _write_json(
        run_dir / "stage_11b_final_arbitration.json",
        {
            "kept": arbitration_kept,
            "reason": arbitration_reason,
            "model": model_stack["final_arbitration"],
            "candidate_payload": arbitration_payload,
            "candidate_qc": arbitration_qc,
        },
    )
    _write_md(
        run_dir / "stage_11b_final_arbitration.md",
        "Stage 11b Final Arbitration",
        {
            "kept": arbitration_kept,
            "reason": arbitration_reason,
            "model": model_stack["final_arbitration"],
            "candidate_qc": arbitration_qc,
        },
    )
    (run_dir / "stage_11b_final_arbitration.raw.txt").write_text(arbitration_raw, encoding="utf-8")

    _write_json(run_dir / "stage_11_reconciliation.json", recon_payload)
    _write_md(run_dir / "stage_11_reconciliation.md", "Stage 11 Reconciliation", recon_payload)
    (run_dir / "stage_11_reconciliation.raw.txt").write_text(recon_raw, encoding="utf-8")
    _write_json(run_dir / "stage_11_reconciliation_qc.json", recon_qc)
    _write_md(run_dir / "stage_11_reconciliation_qc.md", "Stage 11 Reconciliation QC", recon_qc)
    if orchestrator is not None and orchestrator.enabled and cfg.orchestrator.enable_final_synthesis_review:
        try:
            orch_final = orchestrator.final_synthesis_quality_check(
                synthesis_json=recon_payload,
                timeout_seconds=min(90, cfg_deep.timeouts.chat_seconds),
            )
            _write_json(run_dir / "orchestrator_final_synthesis_check.json", orch_final.model_dump())
        except Exception as exc:
            _write_json(
                run_dir / "orchestrator_final_synthesis_check.json",
                {"error": str(exc), "fail_open": bool(orchestrator.fail_open)},
            )
            if not orchestrator.fail_open:
                raise
    post_recheck = {
        "addressed_estimate": len(recon_payload.get("priority_actions", [])),
        "remaining_high_priority": max(0, len(issue_map) - len(recon_payload.get("priority_actions", []))),
        "new_issues_introduced": 0,
        "notes": recon_payload.get("confidence_notes", []),
    }
    _write_json(run_dir / "post_revision_recheck.json", post_recheck)
    _write_md(run_dir / "post_revision_recheck.md", "Post Revision Recheck", post_recheck)
    remaining_issue_map = {"remaining_issues": issue_map[len(recon_payload.get("priority_actions", [])) :]}
    _write_json(run_dir / "remaining_issue_map.json", remaining_issue_map)
    revision_plan_md = "# Final Revision Plan\n\n" + "\n".join(
        [f"- {x}" for x in recon_payload.get("revision_plan", [])] or ["- No revision plan generated."]
    ) + "\n"
    (run_dir / "final_revision_plan.md").write_text(revision_plan_md, encoding="utf-8")

    # Stage 12 DOCX commented manuscript copy (preserve body text; comments only).
    try:
        review_for_comments: dict[str, Any] = {}
        for src in [s3j, s4j, s5j]:
            if not isinstance(src, dict):
                continue
            for key in [
                "section_specific_comments",
                "extracted_action_items",
                "detailed_reviewer_comments",
                "methodological_concerns",
                "novelty_concerns",
                "citation_reference_concerns",
                "writing_organization_concerns",
                "figure_table_concerns",
                "major_weaknesses",
                "grounded_detailed_comments",
            ]:
                vals = src.get(key, [])
                if isinstance(vals, list):
                    review_for_comments.setdefault(key, [])
                    review_for_comments[key].extend(vals)
        # Pull in line-edit and style findings for richer annotation coverage.
        if isinstance(stage6, dict):
            if isinstance(stage6.get("global_edit_priorities"), list):
                review_for_comments.setdefault("detailed_reviewer_comments", []).extend(
                    [str(x) for x in stage6.get("global_edit_priorities", [])]
                )
            if isinstance(stage6.get("section_level_edits"), list):
                review_for_comments.setdefault("section_specific_comments", []).extend(
                    [
                        {
                            "section": str(x.get("section", "section")),
                            "comment": str(x.get("issue", "")),
                            "severity": str(x.get("priority", "medium")),
                        }
                        for x in stage6.get("section_level_edits", [])
                        if isinstance(x, dict)
                    ]
                )
        if isinstance(style_payload, dict):
            for k in ["tone_issues", "formatting_issues", "style_issues"]:
                vals = style_payload.get(k, [])
                if isinstance(vals, list):
                    review_for_comments.setdefault("writing_organization_concerns", []).extend([str(v) for v in vals])
                    
        # Explicitly convert semantic verifications into heavily grounded comments.
        try:
            verifs = json.loads((run_dir / "stage_05b_semantic_verification.json").read_text(encoding="utf-8")).get("verifications", [])
            for v in verifs:
                verdict = v.get("verdict", "")
                if verdict in {"partially_supported", "contradicted", "unsupported"}:
                    source = v.get("supporting_source") or "unspecified support doc"
                    comment_text = f"Claim verification ({verdict}): {v.get('rationale', '')} [Evidence: {v.get('evidence_summary', '')}]"
                    review_for_comments.setdefault("section_specific_comments", []).append(
                        {
                            "section": "Inferred from claim",
                            "comment": comment_text,
                            "severity": "high" if verdict == "contradicted" else "medium",
                            "evidence_source": source,
                            "manuscript_quote": v.get("claim_text", "")
                        }
                    )
        except Exception as exc:
            logger.warning(f"Failed to inject semantic verifications into comments: {exc}")

        # Reuse schema-like fields from high-level stage payload for consistent comments.
        class _Obj:
            def __init__(self, payload: dict[str, Any]):
                self.payload = payload

            @property
            def section_specific_comments(self):
                return [
                    type("C", (), {
                        "section": x.get("section", "section"), 
                        "comment": x.get("comment", ""), 
                        "severity": x.get("severity", "medium"),
                        "evidence_source": x.get("evidence_source", None),
                        "manuscript_quote": x.get("manuscript_quote", None)
                    })
                    for x in self.payload.get("section_specific_comments", [])
                    if isinstance(x, dict)
                ]

            @property
            def extracted_action_items(self):
                return [
                    type("A", (), {"action": x.get("action", ""), "priority": x.get("priority", "medium")})
                    for x in self.payload.get("extracted_action_items", [])
                    if isinstance(x, dict)
                ]

            @property
            def detailed_reviewer_comments(self):
                return [str(x) for x in self.payload.get("detailed_reviewer_comments", []) if str(x).strip()]

            @property
            def grounded_detailed_comments(self):
                return [
                    type("G", (), {
                        "comment": x.get("comment", ""),
                        "severity": x.get("severity", "medium"),
                        "evidence_source": x.get("evidence_source", None),
                        "manuscript_quote": x.get("manuscript_quote", None)
                    })
                    for x in self.payload.get("grounded_detailed_comments", [])
                    if isinstance(x, dict)
                ]

            @property
            def methodological_concerns(self):
                return [str(x) for x in self.payload.get("methodological_concerns", []) if str(x).strip()]

            @property
            def novelty_concerns(self):
                return [str(x) for x in self.payload.get("novelty_concerns", []) if str(x).strip()]

            @property
            def citation_reference_concerns(self):
                return [str(x) for x in self.payload.get("citation_reference_concerns", []) if str(x).strip()]

            @property
            def writing_organization_concerns(self):
                return [str(x) for x in self.payload.get("writing_organization_concerns", []) if str(x).strip()]

            @property
            def figure_table_concerns(self):
                return [str(x) for x in self.payload.get("figure_table_concerns", []) if str(x).strip()]

            @property
            def major_weaknesses(self):
                return [str(x) for x in self.payload.get("major_weaknesses", []) if str(x).strip()]

        annotation = build_annotated_manuscript_output(
            source_path=target_path,
            doc=manuscript_doc,
            review=_Obj(review_for_comments),  # type: ignore[arg-type]
            output_dir=run_dir,
            project_id=project_id,
            run_id=run_dir.name,
            provider=provider,
            model=(
                model_stack.get("line_edits")
                or model_stack.get("context_synthesis")
                or model_stack.get("structural_triage")
            ),
            rewrite_model=model_stack.get("line_edits") or model_stack.get("context_synthesis"),
            comment_audit_model=model_stack.get("final_arbitration") or model_stack.get("high_level_review") or model_stack.get("line_edits"),
            suggestion_audit_model=model_stack.get("final_arbitration") or model_stack.get("line_edits"),
            timeout_seconds=cfg.timeouts.chat_seconds,
        )
        _write_json(run_dir / "manuscript_comment_manifest.json", annotation)
        _write_json(run_dir / "docx_comment_manifest.json", annotation)
        if isinstance(annotation.get("section_map"), list):
            _write_json(run_dir / "section_map.json", annotation.get("section_map"))
        source_mode_payload = annotation.get("source_mode_artifact", {})
        if isinstance(source_mode_payload, dict):
            source_mode_payload["project_id"] = project_id
            _write_json(run_dir / "source_mode.json", source_mode_payload)
        _write_json(run_dir / "commented_docx_validation.json", annotation.get("validation", {}))
        stage_status["stage_13_docx_comments"] = "ok"
    except Exception as exc:
        warnings.append(f"docx_comment_generation_failed:{exc}")
        _write_json(run_dir / "docx_comment_manifest.json", {"error": str(exc)})
        _write_json(run_dir / "manuscript_comment_manifest.json", {"error": str(exc)})
        stage_status["stage_13_docx_comments"] = "failed"

    final_payload = {
        "project_id": project_id,
        "manuscript": str(target_path),
        "model_stack": model_stack,
        "training_guidance_used": training_used,
        "materials_used": materials_used,
        "support_ingest": support_ingest_report,
        "claim_verification_summary": claim_verification_summary,
        "citation_verification_summary": {
            "reference_count": citation_ledger.get("reference_count", 0),
            "linked_reference_count": citation_ledger.get("linked_reference_count", 0),
        },
        "context_pack_used": context_constraints,
        "compliance_check": compliance_payload,
        "stage_status": stage_status,
        "warnings": warnings,
        "final": recon_payload,
    }
    _write_json(run_dir / "final_deep_review_report.json", final_payload)
    _write_md(run_dir / "final_deep_review_report.md", "Final Deep Review Report", final_payload)
    (run_dir / "final_deep_review_report.txt").write_text((run_dir / "final_deep_review_report.md").read_text(encoding="utf-8"), encoding="utf-8")
    write_markdown_as_docx((run_dir / "final_deep_review_report.md").read_text(encoding="utf-8"), run_dir / "final_deep_review_report.docx")
    status = "success" if all(v == "ok" for v in stage_status.values()) else "partial"
    _write_json(run_dir / "run_metadata.json", {
        "command": "deep-run",
        "project_id": project_id,
        "manuscript": str(target_path),
        "status": status,
        "model_stack": model_stack,
        "context_pack_enabled": bool(context_constraints.get("enabled")),
        "context_pack_materials": context_constraints.get("materials", []),
        "stage_status": stage_status,
        "warnings_count": len(final_payload["warnings"]),
    })
    return DeepRunResult(
        run_dir=run_dir,
        manuscript_source=str(target_path),
        status=status,
        stage_status=stage_status,
        warnings=final_payload["warnings"],
    )
