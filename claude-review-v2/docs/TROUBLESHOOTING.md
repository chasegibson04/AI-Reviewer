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
- inspect `support_usage_ledger.json`; zero used sources means ingest may be populating cache without successfully linking cited references to local support papers
- inspect `citation_verification_ledger.json` for `source_resolution`, `support_match_score`, and `support_match_basis` fields before claiming local-paper verification is working

## 6) Ingest Cache Not Reused

### Symptom

- repeated expensive ingest on unchanged sources

### Checks

- inspect `support_ingest_report.json`
- inspect `support_ingest_cache_index.json`

### Expected

- unchanged sources should appear as cache reused
- changed source fingerprints should trigger refresh/re-ingest
- cache reuse alone is not proof that citation verification is using those sources; confirm linkage separately in `support_usage_ledger.json`

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

## 9) Color-Palette Audit Returns Too Many Near-Duplicates

### Symptom

- palette flooded by anti-aliasing shades
- output feels like pixel noise instead of representative colors

### Checks

- inspect `color_palette_full.json`
- inspect `color_palette_filtered.json`
- inspect `color_palette_report.pdf`

### Fix direction

- raise `merge_distance`
- raise `min_pixel_count` or `min_pixel_fraction`
- keep the rendered-page honesty model in mind: this utility is not raw PDF object extraction

## 10) Color-Palette Audit Fails To Render PDF

### Symptom

- `extract_color_palette` returns a PDF render error
- `/color-palette` exits before writing artifacts

### Checks

```bash
which pdftoppm
which pdftocairo
python - <<'PY'
import importlib.util
print('pdf2image', importlib.util.find_spec('pdf2image') is not None)
print('PIL', importlib.util.find_spec('PIL') is not None)
print('reportlab', importlib.util.find_spec('reportlab') is not None)
PY
```

### Fix

- ensure Poppler CLI tools are available (`pdftoppm` and/or `pdftocairo`)
- ensure Python packages are present: `pdf2image`, `Pillow`, `reportlab`
- rerun the tool from the `claude-review-v2` root so outputs stay local
