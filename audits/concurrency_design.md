# Concurrency Design Summary

## Scope
- Different projects can run concurrently without blocking each other.
- Same-project concurrency is blocked by a project-level lock to prevent conflicting writes.

## Locking
- Lock file: `.locks/project.lock` inside each project directory.
- Lock acquisition is atomic; it records `pid`, `hostname`, `started_at`, and `ttl_seconds`.
- Stale lock recovery uses TTL (default configured via `AI_REVIEWER_LOCK_TTL_SECONDS`).

## Same-Project Policy
- By default, a second run on the same project fails fast with a clear error.
- This prevents manifest/document overwrite and avoids ambiguous "latest" references.

## Isolation
- All outputs are project-local and run-local under `projects/<id>/runs/<run_id>/`.
- Artifacts, reports, manifests, and figure outputs are written per run.
- No global temp files are used for review outputs.

## Recovery
- If a run crashes and leaves a lock, stale lock detection can recover based on TTL.
- Lock info is written to `artifacts/lock_info.json` for traceability.

## Observability
- Each run writes its own `debug.log` and run metadata inside the run directory.
- Project access guard artifacts are written in `audits/`.
