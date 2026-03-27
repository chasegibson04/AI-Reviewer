# Troubleshooting

## 1) Ollama Not Reachable

Symptoms:
- `ai-reviewer diagnose` reports `ollama_health` error
- launcher says Ollama unreachable

Actions:
1. Run `ollama serve`
2. Verify `http://127.0.0.1:11434/api/version`
3. Re-run `ai-reviewer diagnose`

## 2) Model Missing

Symptoms:
- review fails with model not found

Actions:
1. `ai-reviewer list-models`
2. Pull required model, e.g.:
   - `ollama pull gemma3:27b`
   - `ollama pull llama3.3:70b-instruct-q4_K_M`
   - `ollama pull mxbai-embed-large:latest`

## 3) Structured Output Failures

Symptoms:
- warnings mention parse/repair
- degraded fallback used

Actions:
1. Inspect bundle files:
   - `raw_model_response.txt`
   - `repaired_model_response.txt`
   - `warnings.json`
2. Try a stronger model/profile:
   - `--profile balanced` or `--profile deep`
3. Test with `ai-reviewer test-models`

## 4) Batch Review Has File-Level Failures

Symptoms:
- `batch_summary.json` shows errors

Actions:
1. Inspect `errors` in `artifacts/batch_summary.json`
2. Run `ai-reviewer ingest <folder>` to isolate parse issues
3. Remove unsupported/corrupt files and retry

## 5) Slow Runs

Actions:
1. Use `quick` profile
2. Disable embeddings (`--disable-embeddings`)
3. Use smaller chat model for screening
4. Run `ai-reviewer benchmark` to pick best speed model

## 6) Strict Offline Conflicts

Symptoms:
- provider initialization fails with non-local Ollama URL

Actions:
1. Set local URL in config:
   - `defaults.ollama_base_url: http://127.0.0.1:11434`
2. Keep `defaults.strict_offline: true`

## 7) Launcher Issues

Actions:
1. Check launcher log in `outputs/launcher_logs/`
2. Run `python -m ai_reviewer.launcher_checks`
3. Run CLI directly:
   - `python -m ai_reviewer diagnose`
   - `python -m ai_reviewer launch`

## 8) Run Says Complete But You Cannot Find Files

Symptoms:
- terminal prints `Review complete` or `Deep run complete`
- you cannot quickly locate reports

What changed:
- completion now prints absolute run directory and key file paths
- run is post-verified for required non-empty artifacts
- project-scoped runs write to `projects/<project_id>/runs/` (or `evaluations/`)

Actions:
1. Use project run discovery:
   - `ai-reviewer project runs --project <project_id>`
   - `ai-reviewer project last-output --project <project_id>`
2. Check printed absolute run path from the run summary panel
3. For review runs, open:
   - `<run_dir>/001_<doc>/review_report.md`
   - `<run_dir>/001_<doc>/validated_review.json`
4. For deep runs, open:
   - `<run_dir>/final_deep_review_report.md`
   - `<run_dir>/final_deep_review_report.json`
   - `<run_dir>/final_deep_review_report.docx`
5. If older runs were written to global `outputs/`, migrate metadata and folders:
   - `ai-reviewer project migrate-outputs --project <project_id>`
   - `ai-reviewer project migrate-outputs --project <project_id> --no-dry-run`
6. If verification fails, the command exits non-zero and reports missing/empty files explicitly.
