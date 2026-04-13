# claude-review-v2 Operational Playbook

## 1. Quick start

From project root:

```bash
node scripts/launch.js
```

Or use platform wrappers:
- macOS: `./launchers/macos/claude-review-v2.sh`
- Windows: `launchers\\windows\\claude-review-v2.cmd`

## 2. Runtime readiness checks

```bash
bash scripts/doctor_runtime.sh
bash scripts/smoke_fallback.sh
```

## 3. Recommended command flow

1. `/doctor` to inspect backend/profile readiness.
2. `/profile` to pick mode (`balanced_local`, `deep_local`, `local_moe`, `one_big_model`, `full_manuscript_final_pass`).
3. `/review <manuscript-path>` for standard run.
4. `/deep-run <manuscript-path>` for staged tool-heavy run.
5. `/artifacts` to inspect outputs.
6. `/replay <run-dir>` and `/diff` for run comparison.

## 4. Big-model mode (Gemma 4)

- `one_big_model` and `full_manuscript_final_pass` prefer `gemma4:26b`, then `gemma4:31b`.
- If unavailable, fallback model is reported explicitly.

## 5. Local-only and safety policy

- Keep runs local-first with Ollama.
- Verify `network_event_log.jsonl` after runs.
- Never run blocked projects containing `pampa` or `horseshoe`.

## 6. Internal validation fixtures

For this effort, do not treat in-folder fixtures as authoritative validation.

Approved real-validation projects only:
- `20260325163524_test-existingphactorpaper`
- `20260327051312_miniaturization_d2b`

Local fixtures may still exist for lightweight bridge/unit tests, but they are not sufficient proof for manuscript-review quality, ingest/cache behavior, or citation-verification quality in this track.
