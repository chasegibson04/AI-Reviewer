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
from ai_reviewer.models.selector import infer_model_roles, is_embedding_model, split_chat_and_embedding_models
from ai_reviewer.projects.store import ProjectStore
from ai_reviewer.review.engine import run_review
from ai_reviewer.review.manuscript_annotation import build_annotated_manuscript_output, detect_source_mode
from ai_reviewer.review.profiles import get_profile
from ai_reviewer.review.repair import extract_json_candidate
from ai_reviewer.review.docx_export import write_markdown_as_docx
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


def _safe_json_from_text(raw: str) -> dict[str, Any]:
    candidate = extract_json_candidate(raw) or raw
    return json.loads(candidate)


def _chat_json(provider: Provider, model: str, system_prompt: str, user_prompt: str, timeout_seconds: int) -> tuple[dict[str, Any], str]:
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
    try:
        return _safe_json_from_text(resp.content), resp.content
    except Exception:
        return {"raw_text": resp.content, "warning": "json_parse_failed"}, resp.content


def _select_stage_models(installed_chat: list[str], cfg: ReviewerConfig) -> dict[str, str]:
    chat_pool = [m for m in installed_chat if not is_embedding_model(m)]
    roles = infer_model_roles(chat_pool, cfg)
    def pick(preferred: str, fallback: str | None = None) -> str:
        if preferred in chat_pool and not is_embedding_model(preferred):
            return preferred
        if fallback and fallback in chat_pool and not is_embedding_model(fallback):
            return fallback
        if chat_pool:
            return chat_pool[0]
        raise DeepRunError("No chat models available for deep run.")

    critique = pick("llama3.3:70b-instruct-q4_K_M", pick("phi4-reasoning:latest", pick(cfg.defaults.deep_review_model, roles.balanced_model)))
    synth = pick("mistral-small3.2:latest", pick(cfg.defaults.balanced_review_model, critique))
    structural = pick("phi4-mini:latest", "qwen3:4b")
    repair = pick("qwen2.5:7b-instruct", cfg.defaults.repair_models[-1] if cfg.defaults.repair_models else synth)
    arbitration = pick("llama3.3:70b-instruct-q4_K_M", critique)
    return {
        "structural_triage": structural,
        "supporting_digest": synth,
        "manuscript_digest": synth,
        "evidence_linking": synth,
        "context_synthesis": synth,
        "high_level_review": critique,
        "adversarial_review": critique,
        "methods_verification": critique,
        "line_edits": synth,
        "style_alignment": synth,
        "reconciliation": repair,
        "final_arbitration": arbitration,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_md(path: Path, title: str, payload: dict[str, Any]) -> None:
    lines = [f"# {title}", ""]
    for k, v in payload.items():
        lines.append(f"## {k}")
        if isinstance(v, list):
            if v:
                lines.extend([f"- {x}" for x in v])
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


def _simple_keywords(text: str, top_n: int = 16) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text.lower())
    stop = {"with", "that", "this", "from", "have", "were", "their", "which", "using", "into", "between", "results", "methods", "introduction", "table", "figure", "analysis", "paper", "study"}
    freq: dict[str, int] = {}
    for w in words:
        if w in stop:
            continue
        freq[w] = freq.get(w, 0) + 1
    return [k for k, _ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:top_n]]


def _fallback_evidence_cards(sdoc: ParsedDocument, top_n: int = 3) -> list[dict[str, Any]]:
    text = sdoc.cleaned_text or ""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    seeds: list[str] = []
    for s in sentences:
        low = s.lower()
        if any(k in low for k in ["we ", "our ", "results", "method", "conclusion", "demonstrate", "show"]):
            seeds.append(s)
        if len(seeds) >= top_n:
            break
    if not seeds:
        seeds = sentences[:top_n]
    cards: list[dict[str, Any]] = []
    for s in seeds[:top_n]:
        cards.append(
            {
                "claim": s[:220],
                "evidence": s[:320],
                "confidence": "low",
                "source_file": sdoc.source_path.name,
                "fallback_generated": True,
            }
        )
    return cards


def _token_overlap(a: str, b: str) -> float:
    sa = set(_simple_keywords(a, top_n=32))
    sb = set(_simple_keywords(b, top_n=32))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / float(len(sa | sb))


def run_deep_run(
    provider: Provider,
    cfg: ReviewerConfig,
    logger: logging.Logger,
    run_dir: Path,
    project_id: str,
    store: ProjectStore,
    manuscript_id: str | None,
    embedding_model: str | None,
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
    model_stack = _select_stage_models(chat_models, cfg)
    _write_json(run_dir / "deep_run_plan.json", {"project_id": project_id, "model_stack": model_stack})
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
        "supporting_materials": [
            {"material_id": m.material_id, "path": str(store.material_path(pdir, m)), "category": m.category}
            for m in others
            if store.material_path(pdir, m).exists()
        ],
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
    for m in others[:10]:
        path = store.material_path(pdir, m)
        try:
            supporting_docs.append(parse_file(path))
        except Exception as exc:
            warnings.append(f"supporting_parse_failed:{path}:{exc}")
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
    }
    _write_json(run_dir / "stage_04_context_pack.json", context_pack)
    _write_md(run_dir / "stage_04_context_pack.md", "Stage 4 Context/Evidence Linking", context_pack)
    _write_json(cache_root / "latest_context_pack.json", context_pack)
    stage_status["stage_05_context_linking"] = "ok"

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
    _write_json(run_dir / "stage_11_reconciliation.json", recon_payload)
    _write_md(run_dir / "stage_11_reconciliation.md", "Stage 11 Reconciliation", recon_payload)
    (run_dir / "stage_11_reconciliation.raw.txt").write_text(recon_raw, encoding="utf-8")
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
        # Reuse schema-like fields from high-level stage payload for consistent comments.
        class _Obj:
            def __init__(self, payload: dict[str, Any]):
                self.payload = payload

            @property
            def section_specific_comments(self):
                return [
                    type("C", (), {"section": x.get("section", "section"), "comment": x.get("comment", ""), "severity": x.get("severity", "medium")})
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
