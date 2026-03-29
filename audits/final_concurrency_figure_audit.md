# Concurrency + Figure Tooling Audit (Scope-Corrected)

## Project Access Guard
- Approved projects: 20260325163524_test-existingphactorpaper, 20260327051312_miniaturization_d2b
- Blacklisted: horseshoe crab (not present, not touched)

## Concurrency Validation
- Different-project concurrent run completed:
  - phactor: projects/20260325163524_test-existingphactorpaper/runs/20260327_181613_review
  - miniaturization: projects/20260327051312_miniaturization_d2b/runs/20260327_181613_review
  - Both runs completed with separate run dirs and outputs.
- Same-project collision behavior:
  - First run completed: projects/20260325163524_test-existingphactorpaper/runs/20260327_181922_review
  - Second run reported lock active and did not proceed (explicit lock message in harness output).
- Aborted run + stale lock recovery:
  - Aborted job, lock mtime forced stale.
  - Recovery run completed: projects/20260325163524_test-existingphactorpaper/runs/20260327_182145_review

## Lock / Isolation Evidence
- Lock acquisition recorded in run artifacts: runs/*/artifacts/lock_info.json
- Lock files are removed after successful run (verified for 20260327_181613_review).
- No cross-project overwrite observed; run dirs are project-local and run-local.

## Figure Extraction + Critique (Text-Only)
- phactor figure run: projects/20260325163524_test-existingphactorpaper/runs/20260327_155053_review
  - figure_manifest.json shows 4 extracted figures; captions not detected.
  - critique.visual_mode = text_only; notes explicitly state no VLM.
  - report includes figure/table concerns based on caption absence.
- miniaturization figure run: projects/20260327051312_miniaturization_d2b/runs/20260327_155655_review
  - figure_manifest.json shows 4 extracted figures; captions not detected.
  - critique.visual_mode = text_only; notes explicitly state no VLM.
  - report includes figure/table concerns based on caption absence.

## Limitations
- Figure critique is text-only and currently limited by missing caption detection.
- Visual understanding is not present; critique is honest about this.

## Tests
- Full pytest run completed after fixing output verifier tests.
