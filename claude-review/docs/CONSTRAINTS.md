# `claude-review` Constraints

The following constraints are foundational and must be strictly followed during development and runtime.

## 1. Write Boundary
- All file creation, editing, deletion, and movement must occur **ONLY** inside the `claude-review/` directory.
- **DO NOT** modify any files in the parent AI-Reviewer repository.
- Do not create symlinks that point outside `claude-review/`.

## 2. Local-First & Offline-Safe
- Default behavior must be local-first.
- The system must remain functional in an offline environment (if local models are configured).
- **NO SILENT FALLBACKS:** The system must never switch from a local provider to a remote provider without explicit user consent or profile configuration.

## 3. Network Transparency
- **NO SILENT NETWORK CALLS:** Any interaction with a remote API (LLM, metadata lookup, DOI check) must be visibly logged in the console.
- Logging must include destination, purpose, and status.
- Opt-out/Opt-in controls for network features must be clearly available in profiles.

## 4. Benchmark Blacklist
- **NEVER** use the following projects for benchmarking or testing:
    - **horseshoe crab** project (`20260324221200_horseshoe_crabs1`)
    - **pampa** project (`pampa-j-chemed`)
- Approved benchmark targets are:
    - `20260325163524_test-existingphactorpaper`
    - `20260327051312_miniaturization_d2b`

## 5. Front-Matter Safety
- The review system must **NEVER** propose edits that delete authors, affiliations, or corrupt the manuscript's front-matter metadata.
- Validation gates must catch and block any such proposed changes.

## 6. Truthfulness & Hallucination Mitigation
- Do not claim parity with existing systems (e.g., Claude Code) unless a concrete, validated path exists.
- The agent must **abstain** from fixing ambiguous or non-localizable issues.
- Every claim verification must be grounded in either the manuscript or supporting literature.

## 7. Auditability
- Every pipeline run must generate a complete, auditable JSON manifest.
- Run artifacts must include the `fingerprint` of the source manuscript and the `model_stack` used.
- Final validation reports must be generated for every run.
