# Troubleshooting

This guide is symptom-driven and focused on local `claude-review-v2` operation.

## 1) Launcher Does Not Start

### Symptom

- launcher exits early
- no interactive shell starts

### Checks

```bash
node scripts/launch.js --print-launch-plan
```

### Expected default

- `launchTarget: line_repl`

### Fix

- if `dist` is stale/missing and Bun is installed: `bun run build`
- run fallback smoke: `bash scripts/smoke_fallback.sh`

## 2) Ollama Unreachable

### Symptom

- `/doctor` shows backend offline
- model probe failures across all lanes

### Checks

```bash
ollama list
bash scripts/doctor_runtime.sh
```

### Fix

- start/restart Ollama (`ollama serve`)
- rerun `/doctor` and `/diagnose`

## 3) Gemma Unavailable

### Symptom

- deep-run Gemma mode degrades immediately
- fallback reason cites Gemma unavailable

### Checks

```bash
ollama list
```

### Fix

```bash
ollama pull gemma4:26b
# optional
ollama pull gemma4:31b
```

## 4) Gemma Empty/No Content Responses

### Symptom

- probe lane failures (short/medium/json/ingest/citation/long)
- runtime fallback or heuristic-only stages

### Checks

- run `/doctor` and inspect Gemma probe lane statuses
- run `/diagnose` and confirm lane results
- inspect `routing_trace.json` and `run_summary.json` fallback fields

### Notes

Bridge behavior includes:

- explicit unusable probe detection
- degraded mode propagation into summary artifacts
- fallback reasoning path when Gemma path is not usable

## 5) Citation Output Too Weak or Noisy

### Symptom

- repetitive citation comments
- low-value generic messages

### Checks

- inspect `citation_verification_ledger.json`
- inspect `manuscript_comment_manifest.json`

### Fix direction

- ensure source extraction quality is adequate (prefer `pdftotext` availability)
- verify model lanes are healthy
- verify abstract-only labels are present when full docs unavailable

## 6) Ingest Cache Not Reused

### Symptom

- repeated expensive ingest on unchanged sources

### Checks

- inspect `support_ingest_report.json`
- inspect `support_ingest_cache_index.json`

### Expected

- unchanged sources should appear as cache reused
- changed source fingerprints should trigger refresh/re-ingest

## 7) Bridge Tool Failures

### Symptom

- tool calls error from shell

### Checks

```bash
python3 -m py_compile src/bridge/python/review_mcp_server.py
python3 -m pytest -q tests/test_mcp_review.py
```

### Fix

- resolve Python env mismatch
- rerun diagnostics from subproject root

## 8) Launch Path Seems to Escape Subproject

### Check

```bash
node scripts/launch.js --print-launch-plan
```

### Interpretation

- `line_repl`: in-subproject path (expected default)
- `legacy_guided_workflow`: only expected when `CLAUDE_REVIEW_ALLOW_LEGACY_GUIDED=1`
