from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from ai_reviewer.config import ReviewerConfig
from ai_reviewer.ingest.loaders import parse_file
from ai_reviewer.models.base import Provider
from ai_reviewer.orchestrator.controller import OrchestratorController, OrchestratorRuntimeState
from ai_reviewer.review.docx_export import write_markdown_as_docx
from ai_reviewer.review.engine import run_review
from ai_reviewer.review.profiles import get_profile


EVALUATION_PROFILES = [
    "quick",
    "balanced",
    "deep",
    "adversarial",
    "methods",
    "writing",
    "editor",
]


@dataclass
class EvaluationSweepResult:
    run_id: str
    output_dir: Path
    per_profile_outputs: dict[str, str]
    warnings: list[str]


def _load_validated_review(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_actions(review_json: dict) -> list[str]:
    actions = []
    for item in review_json.get("extracted_action_items", []):
        action = item.get("action") if isinstance(item, dict) else None
        if action:
            actions.append(action)
    return actions


def _disagreement_analysis(reviews: dict[str, dict]) -> dict:
    decisions = {k: v.get("recommendation", {}).get("decision", "unknown") for k, v in reviews.items()}
    confidences = {k: v.get("confidence", 0) for k, v in reviews.items()}
    return {
        "decisions": decisions,
        "confidence_spread": {
            "min": min(confidences.values()) if confidences else 0,
            "max": max(confidences.values()) if confidences else 0,
        },
        "decision_disagreement": len(set(decisions.values())) > 1 if decisions else False,
    }


def run_published_paper_evaluation_sweep(
    provider: Provider,
    config: ReviewerConfig,
    logger,
    run_id: str,
    anchor_path: Path,
    output_dir: Path,
    model: str,
    embedding_model: str | None,
    repair_models: list[str],
    profiles: Iterable[str] | None = None,
    guidance_getter: Callable[[str], tuple[str | None, list[str]]] | None = None,
    orchestrator: OrchestratorController | None = None,
) -> EvaluationSweepResult:
    profile_list = list(profiles) if profiles else EVALUATION_PROFILES
    doc = parse_file(anchor_path)

    workflows_root = output_dir / "workflows"
    workflows_root.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    per_profile_outputs: dict[str, str] = {}
    orch_state = OrchestratorRuntimeState(
        max_stage_retries=config.orchestrator.max_stage_retries,
        max_total_retries=config.orchestrator.max_total_retries,
    )

    for idx, p in enumerate(profile_list, start=1):
        profile = get_profile(p)
        bundle_dir = workflows_root / f"{idx:02d}_{p}"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        try:
            guidance_text = None
            guidance_categories: list[str] = []
            if guidance_getter is not None:
                guidance_text, guidance_categories = guidance_getter(p)
            run_review(
                provider=provider,
                doc=doc,
                profile=profile,
                model=model,
                repair_models=repair_models,
                config=config,
                bundle_dir=bundle_dir,
                embedding_model=embedding_model if profile.use_retrieval else None,
                strict_schema_override=True,
                logger=logger,
                guidance_text=guidance_text,
                guidance_categories=guidance_categories,
                orchestrator=orchestrator,
                orchestrator_state=orch_state,
                stage_name=f"evaluation_{p}",
            )
            per_profile_outputs[p] = str(bundle_dir)
        except Exception as exc:
            warn = f"Profile {p} failed: {exc}"
            warnings.append(warn)
            logger.exception(warn)

    reviews: dict[str, dict] = {}
    all_actions: list[str] = []
    summaries: dict[str, str] = {}
    repair_flags: dict[str, bool] = {}

    for p, dir_str in per_profile_outputs.items():
        bdir = Path(dir_str)
        vpath = bdir / "validated_review.json"
        if not vpath.exists():
            continue
        review_json = _load_validated_review(vpath)
        reviews[p] = review_json
        summaries[p] = review_json.get("summary", "")
        all_actions.extend(_extract_actions(review_json))
        repair_flags[p] = review_json.get("model_debug_metadata", {}).get("parse_failures", 0) > 0

    disagreement = _disagreement_analysis(reviews)
    if orchestrator is not None and orchestrator.enabled:
        distinctness_input = {
            p: (reviews[p].get("summary", "") + "\n" + "\n".join(reviews[p].get("major_weaknesses", [])[:6]))
            for p in reviews
        }
        distinctness = orchestrator.evaluate_distinctness(distinctness_input, timeout_seconds=min(90, config.timeouts.chat_seconds))
        (output_dir / "orchestrator_distinctness_report.json").write_text(
            json.dumps(distinctness.model_dump(), indent=2),
            encoding="utf-8",
        )
    else:
        distinctness = None

    meta_packet = {
        "run_id": run_id,
        "anchor_path": str(anchor_path),
        "profiles": profile_list,
        "outputs": per_profile_outputs,
        "summaries": summaries,
        "repair_required_by_profile": repair_flags,
        "action_items_aggregated": sorted(set(all_actions)),
        "disagreement_analysis": disagreement,
        "orchestrator_distinctness": distinctness.model_dump() if distinctness is not None else None,
        "warnings": warnings,
    }
    (output_dir / "evaluation_packet.json").write_text(json.dumps(meta_packet, indent=2), encoding="utf-8")

    md = ["# Published Paper Evaluation Sweep", "", "## Workflow Outputs"]
    for p, out in per_profile_outputs.items():
        md.append(f"- {p}: {out}")
    md.extend(["", "## Disagreement Analysis", f"- Decision disagreement: {disagreement['decision_disagreement']}"])
    md.extend([f"- Decisions: {disagreement['decisions']}"])
    md.extend(["", "## Aggregated Action Items"])
    for a in sorted(set(all_actions)):
        md.append(f"- {a}")
    md.extend(["", "## Warnings"])
    if warnings:
        for w in warnings:
            md.append(f"- {w}")
    else:
        md.append("- None")
    summary_md = "\n".join(md) + "\n"
    (output_dir / "evaluation_summary.md").write_text(summary_md, encoding="utf-8")
    write_markdown_as_docx(summary_md, output_dir / "evaluation_summary.docx")

    return EvaluationSweepResult(
        run_id=run_id,
        output_dir=output_dir,
        per_profile_outputs=per_profile_outputs,
        warnings=warnings,
    )
