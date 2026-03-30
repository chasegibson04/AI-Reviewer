from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from ai_reviewer.config import load_config
from ai_reviewer.models.ollama_provider import OllamaProvider
from ai_reviewer.projects.store import ProjectStore
from ai_reviewer.review.deep_run import run_deep_run
from ai_reviewer.paths import REPO_ROOT


APPROVED_PROJECT_ID = "20260325163524_test-existingphactorpaper"
APPROVED_MANUSCRIPT_ID = "20260329_174704_137524"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_metrics(run_dir: Path) -> dict:
    recon_qc = _read_json(run_dir / "stage_11_reconciliation_qc.json")
    deep_report = _read_json(run_dir / "final_deep_review_report.json")
    stage_model_stack = _read_json(run_dir / "stage_model_stack.json")
    line_edits = _read_json(run_dir / "stage_09_line_by_line_edits.json")
    style_alignment = _read_json(run_dir / "stage_10_style_alignment.json")
    final_payload = deep_report.get("final", {})
    return {
        "routing_mode": stage_model_stack.get("routing_mode"),
        "model_stack": stage_model_stack.get("model_stack", {}),
        "reconciliation_quality_score_0_to_5": recon_qc.get("reconciliation_quality_score_0_to_5"),
        "reconciliation_qc": recon_qc.get("reconciliation_qc", {}),
        "fallback_generated": bool(final_payload.get("fallback_generated")),
        "warning_count": len(deep_report.get("warnings", [])),
        "warnings": deep_report.get("warnings", []),
        "strength_count": len(final_payload.get("consolidated_strengths", [])),
        "weakness_count": len(final_payload.get("consolidated_weaknesses", [])),
        "priority_action_count": len(final_payload.get("priority_actions", [])),
        "revision_plan_count": len(final_payload.get("revision_plan", [])),
        "line_edit_count": len(line_edits.get("edits", [])),
        "style_issue_count": len(style_alignment.get("style_issues", [])),
        "formatting_issue_count": len(style_alignment.get("formatting_issues", [])),
    }


def _run_mode(mode: str, out_root: Path) -> dict:
    cfg = load_config()
    cfg.deep_run_routing.mode = mode
    provider = OllamaProvider(
        base_url=cfg.defaults.ollama_base_url,
        strict_offline=cfg.defaults.strict_offline,
        connect_timeout_seconds=cfg.timeouts.connect_seconds,
        chat_attempts=cfg.retries.chat_attempts,
        embed_attempts=cfg.retries.embed_attempts,
        base_backoff_seconds=cfg.retries.base_backoff_seconds,
        logger=logging.getLogger(f"stage7.{mode}"),
    )
    store = ProjectStore(REPO_ROOT / "projects")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = out_root / f"{stamp}_{mode}"
    run_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    result = run_deep_run(
        provider=provider,
        cfg=cfg,
        logger=logging.getLogger(f"stage7.{mode}"),
        run_dir=run_dir,
        project_id=APPROVED_PROJECT_ID,
        store=store,
        manuscript_id=APPROVED_MANUSCRIPT_ID,
        embedding_model=cfg.defaults.embedding_model,
        disable_training_guidance=False,
    )
    elapsed = round(time.perf_counter() - start, 2)
    metrics = _collect_metrics(run_dir)
    metrics.update(
        {
            "status": result.status,
            "elapsed_seconds": elapsed,
            "run_dir": str(run_dir),
        }
    )
    return metrics


def _write_markdown(path: Path, payload: dict) -> None:
    lines = ["# Stage 7 Max-Quality Benchmark", ""]
    lines.append(f"- project_id: `{payload['project_id']}`")
    lines.append(f"- manuscript_id: `{payload['manuscript_id']}`")
    lines.append("")
    for mode in ["default", "max_quality"]:
        entry = payload["runs"][mode]
        lines.append(f"## {mode}")
        lines.append(f"- run_dir: `{entry['run_dir']}`")
        lines.append(f"- elapsed_seconds: {entry['elapsed_seconds']}")
        lines.append(f"- reconciliation_quality_score_0_to_5: {entry['reconciliation_quality_score_0_to_5']}")
        lines.append(f"- fallback_generated: {entry['fallback_generated']}")
        lines.append(f"- warning_count: {entry['warning_count']}")
        lines.append(f"- line_edit_count: {entry['line_edit_count']}")
        lines.append(f"- style_issue_count: {entry['style_issue_count']}")
        lines.append(f"- formatting_issue_count: {entry['formatting_issue_count']}")
        lines.append("")
    comparison = payload["comparison"]
    lines.append("## Comparison")
    for key, value in comparison.items():
        lines.append(f"- {key}: {value}")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> None:
    out_root = REPO_ROOT / "audits" / "stage7_benchmark"
    out_root.mkdir(parents=True, exist_ok=True)
    previous_mode = os.environ.get("AI_REVIEWER_DEEP_RUN_ROUTING_MODE")
    try:
        os.environ["AI_REVIEWER_DEEP_RUN_ROUTING_MODE"] = "default"
        default_metrics = _run_mode("default", out_root)
        os.environ["AI_REVIEWER_DEEP_RUN_ROUTING_MODE"] = "max_quality"
        max_quality_metrics = _run_mode("max_quality", out_root)
    finally:
        if previous_mode is None:
            os.environ.pop("AI_REVIEWER_DEEP_RUN_ROUTING_MODE", None)
        else:
            os.environ["AI_REVIEWER_DEEP_RUN_ROUTING_MODE"] = previous_mode

    payload = {
        "project_id": APPROVED_PROJECT_ID,
        "manuscript_id": APPROVED_MANUSCRIPT_ID,
        "runs": {
            "default": default_metrics,
            "max_quality": max_quality_metrics,
        },
        "comparison": {
            "reconciliation_quality_delta": round(
                (max_quality_metrics["reconciliation_quality_score_0_to_5"] or 0.0)
                - (default_metrics["reconciliation_quality_score_0_to_5"] or 0.0),
                2,
            ),
            "fallback_removed": bool(default_metrics["fallback_generated"] and not max_quality_metrics["fallback_generated"]),
            "warning_delta": max_quality_metrics["warning_count"] - default_metrics["warning_count"],
            "line_edit_delta": max_quality_metrics["line_edit_count"] - default_metrics["line_edit_count"],
        },
    }
    (out_root / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_markdown(out_root / "summary.md", payload)


if __name__ == "__main__":
    main()
