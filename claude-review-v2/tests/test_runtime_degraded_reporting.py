from src.bridge.python import review_mcp_server as bridge


def test_runtime_stage_failures_set_degraded_trace() -> None:
    original_probe = bridge._run_model_probe
    original_diag = bridge._diagnose_model_runtime

    def fail_stage_probe(model: str, prompt: str, expect_json: bool = False, attempt_profile: str = "standard"):
        if attempt_profile == "stage":
            return {"ok": False, "error": "forced_stage_failure"}
        return original_probe(model, prompt, expect_json=expect_json, attempt_profile=attempt_profile)

    bridge._run_model_probe = fail_stage_probe  # type: ignore[assignment]
    bridge._diagnose_model_runtime = lambda _model: {  # type: ignore[assignment]
        "usable": False,
        "usable_for_ingest": False,
        "usable_for_citation_verification": False,
        "usable_for_long_review": False,
    }
    try:
        payload = bridge._generate_stage_reviews(
            content=(
                "Abstract. We observed a 12% increase in yield under condition A versus baseline. "
                "Methods. The procedure used randomization but did not report controls in detail."
            ),
            profile="one_big_model",
            reasoning_mode="gemma_single",
            model_target="gemma4:31b",
            section_map={"Abstract": "line:1", "Methods": "line:2"},
            manuscript_path=None,
            allow_abstract_fallback=True,
        )
    finally:
        bridge._run_model_probe = original_probe  # type: ignore[assignment]
        bridge._diagnose_model_runtime = original_diag  # type: ignore[assignment]

    trace = payload.get("routing_trace", {})
    assert trace.get("degraded") is True
    assert "forced_stage_failure" in str(trace.get("fallback_reason", ""))
