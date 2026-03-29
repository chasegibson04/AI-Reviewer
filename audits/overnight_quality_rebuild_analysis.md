# Overnight Quality Rebuild Analysis

Date: 2026-03-28

## 1. Claimed vs Actual Before-State

- Claimed: deep-run, suggested-changes, citation prefetch, orchestrator/QC, figure review, and output verification existed.
- Actual (before this pass):
  - Suggested-changes density was weak:
    - Phactor deep-run `20260328_175942_deep_run`: 11 proposed, 5 applied.
    - Miniaturization deep-run `20260328_182044_deep_run`: 6 proposed, 3 applied.
  - Deep synthesis contamination existed:
    - Phactor final report contained support names including BioGPT and OpenAI Gym artifacts.
  - Documentation/config drift existed:
    - model defaults differed across docs and code.

## 2. Root Quality Failure Points

- Comment generation was still template-heavy and under-harvested sentence-level issues.
- Suggested-change generation treated broad issue types as globally unresolved too often.
- Rewrite verification accepted some low-alignment rewrites and rejected too many localizable edits.
- Support docs were ingested too broadly in deep-run and review context, allowing irrelevant documents into synthesis context.
- Citation fetch lacked explicit outbound query audit metadata.

## 3. Components Strengthened This Pass

- `ai_reviewer/review/manuscript_annotation.py`
  - increased candidate coverage (`max_comments` 24 -> 36)
  - denser sentence-level issue harvesting
  - generic comment filtering
  - localized structure issue handling
  - stronger rewrite verification gates + deterministic fallback rewrites
- `ai_reviewer/review/deep_run.py`
  - support relevance filtering + blocked-marker filtering
  - selected/skipped support provenance artifacts
  - final report material payload now selected-focused to reduce contamination bleed
- `ai_reviewer/review/engine.py`
  - support-doc relevance filtering before prompt grounding
- `ai_reviewer/review/citation_fetcher.py`
  - query sanitization and query-policy metadata
  - per-attempt query audit fields
- `ai_reviewer/config.py` and docs:
  - reconciled defaults with `config/defaults.yaml`

## 4. Before/After Outcomes (Latest Validated Deep-Runs)

- Phactor:
  - before: 11 suggested changes, 5 applied
  - after (`20260328_220607_deep_run`): 11 suggested changes, 10 applied
- Miniaturization:
  - before: 6 suggested changes, 3 applied
  - after (`20260328_222544_deep_run`): 6 suggested changes, 6 applied
- Contamination:
  - final deep report no longer surfaces BioGPT/OpenAI Gym strings in synthesis body.
  - support filtering artifacts now explicitly report selected vs skipped supports.

## 5. Remaining Risks

- Section mapping for miniaturization still includes residual `body` buckets and needs further heading inference quality.
- Sparse-review enrichment still frequently triggers; base model quality remains a bottleneck.
- Mac Apple Silicon behavior was validated via platform/routing tests, not by executing these exact overnight runs on Mac hardware in this session.
