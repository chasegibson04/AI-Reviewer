from pathlib import Path

from ai_reviewer.output_verifier import verify_deep_run, verify_evaluation_run, verify_review_run


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_verify_review_run_passes(tmp_path: Path):
    run = tmp_path / "run"
    bundle = run / "001_doc"
    _write(run / "run_metadata.json", "{}")
    _write(run / "debug.log", "log")
    _write(run / "artifacts" / "batch_summary.json", "{}")
    _write(bundle / "validated_review.json", "{}")
    _write(bundle / "review_report.md", "# ok")
    _write(bundle / "review_report.txt", "ok")
    _write(bundle / "review_report.docx", "ok")
    _write(bundle / "manuscript_comment_manifest.json", "{}")
    _write(bundle / "source_mode.json", "{}")
    _write(bundle / "commented_docx_validation.json", "{}")
    _write(bundle / "surrogate_manuscript_from_pdf_with_comments.docx", "ok")
    _write(bundle / "run_metadata.json", "{}")
    result = verify_review_run(run)
    assert result.ok


def test_verify_review_run_fails_missing_bundle(tmp_path: Path):
    run = tmp_path / "run"
    _write(run / "run_metadata.json", "{}")
    _write(run / "debug.log", "log")
    _write(run / "artifacts" / "batch_summary.json", "{}")
    result = verify_review_run(run)
    assert not result.ok
    assert any("No per-document bundle" in issue for issue in result.issues)


def test_verify_deep_run_passes(tmp_path: Path):
    run = tmp_path / "deep"
    for rel in (
        "run_metadata.json",
        "final_deep_review_report.json",
        "final_deep_review_report.md",
        "final_deep_review_report.txt",
        "final_deep_review_report.docx",
        "surrogate_manuscript_from_pdf_with_comments.docx",
        "manuscript_comment_manifest.json",
        "docx_comment_manifest.json",
        "source_mode.json",
        "commented_docx_validation.json",
        "stage_07_reconciliation.json",
        "deep_run_plan.json",
        "debug.log",
    ):
        _write(run / rel, "x")
    result = verify_deep_run(run)
    assert result.ok


def test_verify_evaluation_run_passes(tmp_path: Path):
    run = tmp_path / "eval"
    _write(run / "evaluation_packet.json", "{}")
    _write(run / "evaluation_summary.md", "# ok")
    _write(run / "evaluation_summary.docx", "ok")
    _write(run / "run_metadata.json", "{}")
    _write(run / "debug.log", "x")
    bundle = run / "workflows" / "01_quick"
    _write(bundle / "validated_review.json", "{}")
    _write(bundle / "review_report.md", "# ok")
    _write(bundle / "review_report.txt", "ok")
    _write(bundle / "review_report.docx", "ok")
    result = verify_evaluation_run(run)
    assert result.ok
