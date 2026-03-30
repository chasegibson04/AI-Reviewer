from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from ai_reviewer.config import load_config
from ai_reviewer.ingest.loaders import parse_file
from ai_reviewer.models.ollama_provider import OllamaProvider
from ai_reviewer.models.selector import infer_model_roles, split_chat_and_embedding_models
from ai_reviewer.paths import REPO_ROOT
from ai_reviewer.projects.store import ProjectStore
from ai_reviewer.review.deep_run import run_deep_run
from ai_reviewer.review.engine import run_review
from ai_reviewer.review.profiles import get_profile


APPROVED_PROJECTS = [
    "20260325163524_test-existingphactorpaper",
    "20260327051312_miniaturization_d2b",
]
CONTEXT_PACK_CATEGORIES = {"style_guide", "journal_instructions", "reference_example", "methods_reference"}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _first_pdf(project_root: Path) -> Path:
    files = sorted((project_root / "materials" / "manuscript").glob("*.pdf"))
    if not files:
        raise FileNotFoundError(f"No manuscript PDF found under {project_root / 'materials' / 'manuscript'}")
    return files[0]


def _supporting_docs(project_root: Path) -> list:
    docs = []
    other_dir = project_root / "materials" / "other"
    if not other_dir.exists():
        return docs
    for path in sorted(other_dir.iterdir()):
        if path.is_file():
            try:
                docs.append(parse_file(path))
            except Exception:
                continue
    return docs


def _context_material_ids(project_id: str) -> list[str]:
    payload = _read_json(REPO_ROOT / "projects" / project_id / "project.json")
    return [
        str(m.get("material_id"))
        for m in payload.get("materials", [])
        if m.get("category") in CONTEXT_PACK_CATEGORIES
    ]


def _provider_and_cfg() -> tuple[OllamaProvider, Any, str, str | None]:
    cfg = load_config()
    provider = OllamaProvider(
        base_url=cfg.defaults.ollama_base_url,
        strict_offline=cfg.defaults.strict_offline,
        connect_timeout_seconds=cfg.timeouts.connect_seconds,
        chat_attempts=cfg.retries.chat_attempts,
        embed_attempts=cfg.retries.embed_attempts,
        base_backoff_seconds=cfg.retries.base_backoff_seconds,
        logger=logging.getLogger("stage8"),
    )
    installed = provider.list_models()
    chat, emb = split_chat_and_embedding_models(installed)
    roles = infer_model_roles(installed, cfg)
    model = roles.balanced_model
    embed = roles.embedding_model if roles.embedding_model in emb else None
    if model not in chat:
        raise RuntimeError(f"Balanced model {model} not available in chat pool.")
    return provider, cfg, model, embed


def _extract_review_metrics(bundle_dir: Path) -> dict[str, Any]:
    review = _read_json(bundle_dir / "artifacts" / "review.validated.json")
    specialist = _read_json(bundle_dir / "specialist_review_summary.json")
    figure_manifest = {}
    if (bundle_dir / "figure_manifest.json").exists():
        figure_manifest = _read_json(bundle_dir / "figure_manifest.json")
    figure_concerns = [str(x) for x in review.get("figure_table_concerns", []) if str(x).strip()]
    return {
        "figure_manifest_present": bool(figure_manifest),
        "figure_count": int(figure_manifest.get("critique", {}).get("figure_count", 0)) if figure_manifest else 0,
        "figure_table_concerns_count": len(figure_concerns),
        "figure_table_concerns": figure_concerns,
        "specialist_overall_score_0_to_5": specialist.get("overall_score_0_to_5"),
        "specialist_generic_item_count": specialist.get("qc_flags", {}).get("generic_item_count"),
        "warning_count": len(review.get("model_debug_metadata", {}).get("warnings", []) if isinstance(review.get("model_debug_metadata"), dict) else []),
    }


def _extract_deep_metrics(run_dir: Path) -> dict[str, Any]:
    context_pack = _read_json(run_dir / "context_pack_used.json")
    compliance = _read_json(run_dir / "stage_10b_compliance_check.json")
    final = _read_json(run_dir / "final_deep_review_report.json")
    weak = [str(x) for x in final.get("final", {}).get("consolidated_weaknesses", []) if str(x).strip()]
    actions = [str(x) for x in final.get("final", {}).get("priority_actions", []) if str(x).strip()]
    compliance_touched = [x for x in weak if "context-pack" in x.lower() or "title contains forbidden word" in x.lower()]
    compliance_actions = [x for x in actions if "compliance issue" in x.lower()]
    return {
        "context_pack_enabled": bool(context_pack.get("enabled")),
        "context_pack_materials": context_pack.get("materials", []),
        "context_priorities": context_pack.get("priorities", []),
        "compliance_finding_count": int(compliance.get("finding_count", 0)),
        "compliance_findings": compliance.get("findings", []),
        "final_weakness_count": len(weak),
        "final_priority_action_count": len(actions),
        "compliance_weakness_hits": compliance_touched,
        "compliance_action_hits": compliance_actions,
        "warnings": final.get("warnings", []),
    }


def run() -> dict[str, Any]:
    provider, cfg, selected_model, selected_embed = _provider_and_cfg()
    installed_models = provider.list_models()
    repair_candidates = infer_model_roles(installed_models, cfg).repair_candidates
    out_root = REPO_ROOT / "audits" / "stage8_optional_layer_benchmark"
    out_root.mkdir(parents=True, exist_ok=True)
    store = ProjectStore(REPO_ROOT / "projects")
    summary: dict[str, Any] = {"figure_review": {}, "context_pack": {}}

    for project_id in APPROVED_PROJECTS:
        project_root = REPO_ROOT / "projects" / project_id
        pdf_path = _first_pdf(project_root)
        doc = parse_file(pdf_path)
        support_docs = _supporting_docs(project_root)
        profile = get_profile("balanced")

        project_out = out_root / project_id
        figure_out_off = project_out / "figure_off"
        figure_out_on = project_out / "figure_on"
        for path in [figure_out_off, figure_out_on]:
            if path.exists():
                shutil.rmtree(path)
            path.mkdir(parents=True, exist_ok=True)

        cfg_off = load_config()
        cfg_off.figure_review.enabled = False
        cfg_off.training.enabled = False
        run_review(
            provider=provider,
            doc=doc,
            profile=profile,
            model=selected_model,
            repair_models=repair_candidates,
            config=cfg_off,
            bundle_dir=figure_out_off,
            embedding_model=selected_embed,
            strict_schema_override=True,
            logger=logging.getLogger(f"stage8.figure.off.{project_id}"),
            supporting_docs=support_docs,
            orchestrator=None,
        )

        cfg_on = load_config()
        cfg_on.figure_review.enabled = True
        cfg_on.training.enabled = False
        run_review(
            provider=provider,
            doc=doc,
            profile=profile,
            model=selected_model,
            repair_models=repair_candidates,
            config=cfg_on,
            bundle_dir=figure_out_on,
            embedding_model=selected_embed,
            strict_schema_override=True,
            logger=logging.getLogger(f"stage8.figure.on.{project_id}"),
            supporting_docs=support_docs,
            orchestrator=None,
        )
        summary["figure_review"][project_id] = {
            "off": _extract_review_metrics(figure_out_off),
            "on": _extract_review_metrics(figure_out_on),
        }

        context_ids = _context_material_ids(project_id)
        manuscript_payload = _read_json(project_root / "project.json")
        manuscript_candidates = [
            m for m in manuscript_payload.get("materials", [])
            if m.get("category") == "manuscript_draft"
        ]
        preferred_pdf = next(
            (m for m in manuscript_candidates if str(m.get("filename", "")).lower().endswith(".pdf")),
            None,
        )
        manuscript_id = str((preferred_pdf or manuscript_candidates[0])["material_id"])
        context_off_dir = project_out / "context_pack_off"
        context_on_dir = project_out / "context_pack_on"
        for path in [context_off_dir, context_on_dir]:
            if path.exists():
                shutil.rmtree(path)
            path.mkdir(parents=True, exist_ok=True)

        cfg_deep_off = load_config()
        cfg_deep_off.training.enabled = False
        run_deep_run(
            provider=provider,
            cfg=cfg_deep_off,
            logger=logging.getLogger(f"stage8.context.off.{project_id}"),
            run_dir=context_off_dir,
            project_id=project_id,
            store=store,
            manuscript_id=manuscript_id,
            embedding_model=selected_embed,
            context_material_ids=["__none__"],
            disable_training_guidance=True,
            orchestrator=None,
        )

        cfg_deep_on = load_config()
        cfg_deep_on.training.enabled = False
        run_deep_run(
            provider=provider,
            cfg=cfg_deep_on,
            logger=logging.getLogger(f"stage8.context.on.{project_id}"),
            run_dir=context_on_dir,
            project_id=project_id,
            store=store,
            manuscript_id=manuscript_id,
            embedding_model=selected_embed,
            context_material_ids=context_ids,
            disable_training_guidance=True,
            orchestrator=None,
        )
        summary["context_pack"][project_id] = {
            "off": _extract_deep_metrics(context_off_dir),
            "on": _extract_deep_metrics(context_on_dir),
        }

    (out_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    summary = run()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
