from src.bridge.python import review_mcp_server as bridge


def test_citation_abstract_only_fallback_is_labeled() -> None:
    content = (
        "The intervention consistently improved yield in all conditions [1].\n\n"
        "References\n"
        "[1] Smith J. Example study. Journal. 2021. doi:10.1000/example"
    )
    references = bridge._extract_reference_entries(content)
    model_plan = bridge._resolve_stage_models(
        reasoning_mode_requested="gemma_single",
        profile="one_big_model",
        explicit_model_target="gemma4:31b",
        available_models=[],
    )

    original_fetch = bridge._fetch_openalex_metadata
    original_diag = bridge._diagnose_model_runtime
    try:
        bridge._fetch_openalex_metadata = lambda _ref: {  # type: ignore[assignment]
            "abstract_inverted_index": {
                "unrelated": [0],
                "mechanism": [1],
                "discussion": [2],
            }
        }
        bridge._diagnose_model_runtime = lambda _model: {  # type: ignore[assignment]
            "usable_for_citation_verification": False
        }

        ledger, details, _usage, summary, stage, _assertions = bridge._run_line_by_line_citation_verification(
            content=content,
            references=references,
            support_docs=[],
            model_plan=model_plan,
            allow_abstract_fallback=True,
        )
    finally:
        bridge._fetch_openalex_metadata = original_fetch  # type: ignore[assignment]
        bridge._diagnose_model_runtime = original_diag  # type: ignore[assignment]

    statuses = [row.get("status") for row in ledger.get("entries", [])]
    assert "abstract_only" in statuses
    assert stage.get("status") == "heuristic_only"
    assert summary.get("unsupported_or_unclear", 0) >= 1
    assert any("abstract only" in str(row.get("issue", "")).lower() for row in details)
