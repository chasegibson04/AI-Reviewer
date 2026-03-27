import json
from pathlib import Path
from datetime import datetime
from collections import Counter

PROJECT_ID = "20260325163524_test-existingphactorpaper"
REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = REPO_ROOT / "projects" / PROJECT_ID
AUDIT_DIR = PROJECT_DIR / "audits"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

RUN_IDS = {
    "methods_final": "20260327_050322_review",
    "writing_final": "20260327_034624_review",
    "editor_final": "20260327_034810_review",
    "balanced_final": "20260327_035015_review",
    "adversarial_final": "20260327_035251_review",
    "deep_run_final": "20260327_062441_deep_run",
    "evaluate_paper": "20260327_041903_evaluate_paper",
    "orchestrator_on": "20260327_043550_review",
    "support_off": "20260327_043919_review",
    "guidance_off": "20260327_044141_review",
}

MANUSCRIPT_DIR = PROJECT_DIR / "materials" / "manuscript"
OTHER_DIR = PROJECT_DIR / "materials" / "other"

manuscripts = [p for p in MANUSCRIPT_DIR.iterdir() if p.is_file()]
source_mode = "pdf_only_surrogate" if not any(p.suffix.lower() == ".docx" for p in manuscripts) else "original_docx"

materials_other = [p.name for p in OTHER_DIR.iterdir() if p.is_file()]

runs = sorted([p.name for p in (PROJECT_DIR / "runs").iterdir() if p.is_dir()])
evals = sorted([p.name for p in (PROJECT_DIR / "evaluations").iterdir() if p.is_dir()]) if (PROJECT_DIR / "evaluations").exists() else []

cache_dir = PROJECT_DIR / "cache"
cache_items = []
if cache_dir.exists():
    for p in cache_dir.rglob("*"):
        if p.is_file():
            cache_items.append(str(p.relative_to(PROJECT_DIR)))


def read_run_meta(run_id):
    base = PROJECT_DIR / "runs" / run_id
    candidates = list(base.rglob("run_metadata.json"))
    if not candidates:
        return {}
    return json.loads(candidates[0].read_text(encoding="utf-8"))


def read_comment_validation(run_id):
    base = PROJECT_DIR / "runs" / run_id
    candidates = list(base.rglob("commented_docx_validation.json"))
    if not candidates:
        return {}
    return json.loads(candidates[0].read_text(encoding="utf-8"))


def read_comment_manifest(run_id):
    base = PROJECT_DIR / "runs" / run_id
    candidates = list(base.rglob("manuscript_comment_manifest.json"))
    if not candidates:
        return {}
    return json.loads(candidates[0].read_text(encoding="utf-8"))


def orchestrator_enabled(run_id):
    base = PROJECT_DIR / "runs" / run_id
    return any(p.name.startswith("orchestrator_") for p in base.rglob("*.json"))

run_matrix = []
for key, run_id in RUN_IDS.items():
    if "evaluate_paper" in key:
        eval_dir = PROJECT_DIR / "evaluations" / run_id
        meta = {}
        if (eval_dir / "run_metadata.json").exists():
            meta = json.loads((eval_dir / "run_metadata.json").read_text(encoding="utf-8"))
        run_matrix.append({
            "run_id": run_id,
            "workflow": "evaluate-paper",
            "profile": None,
            "model": meta.get("model"),
            "embedding_model": meta.get("embedding_model"),
            "retrieval_used": meta.get("retrieval_used"),
            "orchestrator_enabled": orchestrator_enabled(run_id),
            "guidance_injected": meta.get("guidance_injected"),
        })
        continue
    meta = read_run_meta(run_id)
    run_matrix.append({
        "run_id": run_id,
        "workflow": "deep-run" if "deep_run" in run_id else "review",
        "profile": meta.get("profile"),
        "model": meta.get("model"),
        "embedding_model": meta.get("embedding_model"),
        "retrieval_used": meta.get("retrieval_used"),
        "orchestrator_enabled": orchestrator_enabled(run_id),
        "guidance_injected": meta.get("guidance_injected"),
        "guidance_categories": meta.get("guidance_categories"),
        "duration_seconds": meta.get("duration_seconds"),
    })

support_audit = {
    "support_materials": materials_other,
    "retrieval_manifest_paths": [],
    "sample_retrieval_sources": [],
}
retrieval_manifest = PROJECT_DIR / "runs" / RUN_IDS["methods_final"] / "001_designing-chemical-reaction-arrays-using-phactor-and-chatgpt" / "artifacts" / "retrieval_manifest.json"
if retrieval_manifest.exists():
    support_audit["retrieval_manifest_paths"].append(str(retrieval_manifest))
    data = json.loads(retrieval_manifest.read_text(encoding="utf-8"))
    support_audit["sample_retrieval_sources"] = sorted({d.get("source") for d in data})

training_guidance = {}
training_path = PROJECT_DIR / "runs" / RUN_IDS["deep_run_final"] / "training_guidance_used.json"
if training_path.exists():
    training_guidance = json.loads(training_path.read_text(encoding="utf-8"))

orchestrator_benchmark = {
    "baseline_run": RUN_IDS["methods_final"],
    "orchestrated_run": RUN_IDS["orchestrator_on"],
    "baseline_comments": read_comment_manifest(RUN_IDS["methods_final"]).get("comments_added"),
    "orchestrated_comments": read_comment_manifest(RUN_IDS["orchestrator_on"]).get("comments_added"),
}

comment_validation = read_comment_validation(RUN_IDS["methods_final"])

project_inventory = {
    "project_id": PROJECT_ID,
    "manuscript_files": [p.name for p in manuscripts],
    "source_mode": source_mode,
    "materials_other": materials_other,
    "runs": runs,
    "evaluations": evals,
    "cache_items": cache_items,
}

(AUDIT_DIR / "project_inventory.json").write_text(json.dumps(project_inventory, indent=2), encoding="utf-8")
(AUDIT_DIR / "support_materials_audit.json").write_text(json.dumps(support_audit, indent=2), encoding="utf-8")
(AUDIT_DIR / "training_guidance_audit.json").write_text(json.dumps(training_guidance, indent=2), encoding="utf-8")
(AUDIT_DIR / "cache_audit.json").write_text(json.dumps({"cache_items": cache_items}, indent=2), encoding="utf-8")
(AUDIT_DIR / "orchestrator_benchmark.json").write_text(json.dumps(orchestrator_benchmark, indent=2), encoding="utf-8")
(AUDIT_DIR / "run_matrix.json").write_text(json.dumps(run_matrix, indent=2), encoding="utf-8")
(AUDIT_DIR / "commented_docx_validation.json").write_text(json.dumps(comment_validation, indent=2), encoding="utf-8")

md = []
md.append(f"# ExistingPhactorPaper Audit ({datetime.utcnow().isoformat()}Z)")
md.append(f"\n## Project Inventory\n```\n{json.dumps(project_inventory, indent=2)}\n```")
md.append(f"\n## Support Materials\n```\n{json.dumps(support_audit, indent=2)}\n```")
md.append(f"\n## Training Guidance\n```\n{json.dumps(training_guidance, indent=2)[:4000]}\n```")
md.append(f"\n## Orchestrator Benchmark\n```\n{json.dumps(orchestrator_benchmark, indent=2)}\n```")
md.append(f"\n## Run Matrix\n```\n{json.dumps(run_matrix, indent=2)}\n```")
md.append(f"\n## Comment Validation (methods_final)\n```\n{json.dumps(comment_validation, indent=2)}\n```")
(AUDIT_DIR / "existingphactorpaper_full_audit_report.md").write_text("\n".join(md), encoding="utf-8")
(AUDIT_DIR / "existingphactorpaper_full_audit_report.json").write_text(json.dumps({
    "project_inventory": project_inventory,
    "support_materials": support_audit,
    "training_guidance": training_guidance,
    "orchestrator_benchmark": orchestrator_benchmark,
    "run_matrix": run_matrix,
    "comment_validation": comment_validation,
}, indent=2), encoding="utf-8")
print("audit_written", AUDIT_DIR)
