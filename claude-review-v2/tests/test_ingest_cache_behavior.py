from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from src.bridge.python import review_mcp_server as bridge


ALLOWED_PROJECT_A = "20260325163524_test-existingphactorpaper"


def _build_sandbox() -> tuple[Path, Path]:
    project_root = Path(__file__).resolve().parents[1]
    source_root = (
        project_root.parent
        / "projects"
        / ALLOWED_PROJECT_A
        / "materials"
    )
    manuscript_src = source_root / "manuscript" / "designing-chemical-reaction-arrays-using-phactor-and-chatgpt.pdf"
    support_src = source_root / "other" / "d1sc06932b.pdf"
    if not manuscript_src.exists() or not support_src.exists():
        raise FileNotFoundError("Allowed-project fixtures are missing for cache behavior test.")

    sandbox_root = project_root / ".runtime" / "cache_test_sandboxes"
    sandbox_root.mkdir(parents=True, exist_ok=True)
    sandbox = Path(tempfile.mkdtemp(prefix="cache_case_", dir=str(sandbox_root)))
    (sandbox / "support").mkdir(parents=True, exist_ok=True)
    manuscript_dst = sandbox / "manuscript.pdf"
    support_dst = sandbox / "support" / "support_a.pdf"
    shutil.copy2(manuscript_src, manuscript_dst)
    shutil.copy2(support_src, support_dst)

    # Ensure this test starts from a real cold-cache state for the sandbox copy.
    # Cache keys are path-based, so previous test runs against the same sandbox
    # location can otherwise make the first ingest appear "reused".
    for candidate in (manuscript_dst, support_dst):
        cache_file = bridge.SUPPORT_CACHE_ROOT / f"{bridge._sha1_text(str(candidate.resolve()))}.json"
        if cache_file.exists():
            cache_file.unlink()

    return manuscript_dst, support_dst


def test_support_ingest_cache_reuse_and_invalidation() -> None:
    manuscript_path, support_path = _build_sandbox()
    model_plan = bridge._resolve_stage_models(
        reasoning_mode_requested="gemma_single",
        profile="one_big_model",
        explicit_model_target="gemma4:31b",
        available_models=[],
    )
    original_diag = bridge._diagnose_model_runtime
    try:
        bridge._diagnose_model_runtime = lambda _model: {  # type: ignore[assignment]
            "usable_for_ingest": False
        }

        report_a, _usage_a, docs_a, _stage_a = bridge._ingest_support_documents(
            manuscript_path=manuscript_path,
            reasoning_mode="gemma_single",
            model_plan=model_plan,
            reference_entries=[],
        )
        assert report_a["available_support_docs"] >= 1
        assert report_a["cache_reused_docs"] == 0
        assert len(docs_a) >= 1

        report_b, _usage_b, docs_b, _stage_b = bridge._ingest_support_documents(
            manuscript_path=manuscript_path,
            reasoning_mode="gemma_single",
            model_plan=model_plan,
            reference_entries=[],
        )
        assert report_b["cache_reused_docs"] >= 1
        assert len(docs_b) >= 1

        with support_path.open("ab") as handle:
            handle.write(b"\n%cache-bust\n")

        report_c, _usage_c, docs_c, _stage_c = bridge._ingest_support_documents(
            manuscript_path=manuscript_path,
            reasoning_mode="gemma_single",
            model_plan=model_plan,
            reference_entries=[],
        )
        assert report_c["cache_refreshed_docs"] >= 1
        assert len(docs_c) >= 1
    finally:
        bridge._diagnose_model_runtime = original_diag  # type: ignore[assignment]
