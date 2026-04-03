# LOCAL_ONLY_VALIDATION_PLAN
Date: 2026-04-03

## Executed validation path
1. Runtime doctor checks
- Ran `scripts/doctor_runtime.sh`
- Confirmed local Ollama API reachable and local models listed.

2. Bridge integration run
- Ran `tests/test_mcp_review.py` end-to-end.
- Produced artifacts under:
  - `test_outputs/pytest_bridge_run_a/`
  - `test_outputs/pytest_bridge_run_b/`

3. Local-only network evidence
- `network_event_log.jsonl` shows localhost-only healthcheck events.
- `validation_report.json` for both runs shows `remote_network_events: []`.

4. Big-model path evidence
- Run B uses profile `one_big_model` with mode `single big-model review`.
- `run_summary.json` and `routing_trace.json` record `model_target: gemma4:31b`.

5. Fallback smoke evidence
- Ran `scripts/smoke_fallback.sh` successfully to validate no-Bun local path.

## Remaining validation gap
- Full Bun-native shell command invocation smoke remains blocked by environment missing Bun runtime.
