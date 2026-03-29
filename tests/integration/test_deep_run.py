import json
from pathlib import Path

import pytest

from ai_reviewer.config import load_config
from ai_reviewer.projects.schema import ProjectDefaults
from ai_reviewer.projects.store import ProjectStore
from ai_reviewer.review.deep_run import DeepRunError, run_deep_run


class DeepRunProvider:
    def health(self):
        return True, "ok"

    def list_models(self):
        return ["gemma3:27b", "llama3.3:70b-instruct-q4_K_M", "mxbai-embed-large:latest", "mistral-small3.1:24b"]

    def chat(self, request):
        lower = request.system_prompt.lower()
        if "strict json" in lower and "reviewer" in lower:
            content = (
                "{"
                '"document_metadata":{"title":"Fixture"},'
                '"summary":"Summary",'
                '"major_strengths":["s"],'
                '"major_weaknesses":["w"],'
                '"novelty_concerns":[],"methodological_concerns":[],"statistical_concerns":[],"writing_organization_concerns":[],'  # noqa: E501
                '"figure_table_concerns":[],"citation_reference_concerns":[],"reproducibility_concerns":[],'  # noqa: E501
                '"suggested_experiments_analyses":[],"recommendation":{"decision":"revise","rationale":"ok"},'
                '"confidence":0.7,"detailed_reviewer_comments":["fine"],"section_specific_comments":[],"extracted_action_items":[],'  # noqa: E501
                '"model_debug_metadata":{"provider":"ollama","model":"gemma3:27b","temperature":0.2,"parse_failures":0}'
                "}"
            )
        elif "reconcile" in lower:
            content = '{"consolidated_strengths":["x"],"consolidated_weaknesses":["y"],"disagreements":[],"priority_actions":["a"],"revision_plan":["p"],"response_to_reviewers_bullets":["r"],"confidence_notes":["c"]}'  # noqa: E501
        elif "style and formatting" in lower:
            content = '{"style_issues":["s"],"formatting_issues":["f"],"tone_issues":["t"],"alignment_actions":["a"]}'
        elif "local edit suggestions" in lower:
            content = '{"section":"sec","issues":["i"],"rewrite_candidates":["r"]}'
        else:
            content = '{"manuscript_overview":"m","section_map":["s"],"claims":["c"],"methods":["m"],"results":["r"],"conclusions":["c"],"risk_areas":["x"]}'  # noqa: E501

        class R:
            total_duration = 1.0
            prompt_eval_count = 10
            eval_count = 10
            retries_used = 0
            prompt_chars = 100
            approx_prompt_tokens = 25
            raw = {}

            def __init__(self, text: str):
                self.content = text

        return R(content)

    def embed(self, text, model, timeout_seconds=90):
        class E:
            embedding = [0.1] * 16

        return E()


def _cfg_with_training(tmp_path: Path, training_enabled: bool = True):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        f"training:\n"
        f"  enabled: {str(training_enabled).lower()}\n"
        f"  source_root: {(tmp_path / 'training_materials').as_posix()}\n"
        f"  cache_root: {(tmp_path / 'training_cache').as_posix()}\n",
        encoding="utf-8",
    )
    if training_enabled:
        t = tmp_path / "training_materials" / "external_guides"
        t.mkdir(parents=True, exist_ok=True)
        (t / "g.md").write_text("# guide\n\nclear style", encoding="utf-8")
    return load_config(str(cfg_path))


def test_deep_run_project_with_manuscript_and_other(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    _, meta = store.create_project("Deep", "", [], ProjectDefaults(review_model="gemma3:27b"))
    pdir, _ = store.get_project(meta.project_id)
    (pdir / "materials" / "manuscript" / "main.md").write_text("# Main\n\nMethods and results.", encoding="utf-8")
    (pdir / "materials" / "other" / "support.md").write_text("# Support\n\nBackground.", encoding="utf-8")
    cfg = _cfg_with_training(tmp_path, training_enabled=True)
    run_dir = tmp_path / "run"
    result = run_deep_run(
        provider=DeepRunProvider(),  # type: ignore[arg-type]
        cfg=cfg,
        logger=__import__("logging").getLogger("test"),
        run_dir=run_dir,
        project_id=meta.project_id,
        store=store,
        manuscript_id=None,
        embedding_model="mxbai-embed-large:latest",
        disable_training_guidance=False,
    )
    assert result.status == "success"
    assert (run_dir / "final_deep_review_report.json").exists()
    assert (run_dir / "stage_11_reconciliation_qc.json").exists()
    assert json.loads((run_dir / "training_guidance_used.json").read_text(encoding="utf-8"))["enabled"] is True


def test_deep_run_other_only_fails_gracefully(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    _, meta = store.create_project("No Manuscript", "", [], ProjectDefaults(review_model="gemma3:27b"))
    pdir, _ = store.get_project(meta.project_id)
    (pdir / "materials" / "other" / "support.md").write_text("# Support\n\nOnly supporting.", encoding="utf-8")
    cfg = _cfg_with_training(tmp_path, training_enabled=False)
    with pytest.raises(DeepRunError):
        run_deep_run(
            provider=DeepRunProvider(),  # type: ignore[arg-type]
            cfg=cfg,
            logger=__import__("logging").getLogger("test"),
            run_dir=tmp_path / "run_fail",
            project_id=meta.project_id,
            store=store,
            manuscript_id=None,
            embedding_model="mxbai-embed-large:latest",
            disable_training_guidance=True,
        )
