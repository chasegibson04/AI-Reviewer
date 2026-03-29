# Rigorous Integration Plan

Date: 2026-03-28

## Source Basis
Plan derived from:
- audits/rigorous_comparison_report.md
- audits/rigorous_comparison_report.json

## Ranked Recommendations (from comparison)
- Borrow soon:
  - Role taxonomy pattern (section/rigor/writing)
  - Category-level reconciliation schema
  - Scoring normalization by category
- Adapt carefully:
  - Executive-summary synthesis pattern
  - Section-specific prompt structure
- Benchmark first:
  - Large specialist swarm decomposition
  - Outlet-fit workflow expansion
- Ignore:
  - OpenAI-hardcoded runtime assumptions
  - Script-chain architecture replacement

## Selected For This Sprint (2-5 items)
1. Rigorous-inspired specialist QC summary for standard review outputs.
2. Category scoring normalization artifact (0-5) for review quality signals.
3. Deep-run reconciliation QC summary artifact.

## Module Mapping
- `ai_reviewer/review/rigorous_adapters.py`
  - New adapter module with bounded deterministic specialist/QC scoring and reconciliation QC summarization.
- `ai_reviewer/review/engine.py`
  - Extended standard review path to emit specialist summary artifacts and expose specialist score in run metadata.
- `ai_reviewer/review/deep_run.py`
  - Extended reconciliation stage to emit dedicated reconciliation QC artifacts.
- `tests/unit/test_rigorous_adapters.py`
  - Validates scoring shape/range and reconciliation QC extraction.
- `tests/integration/test_pipeline.py`
  - Verifies specialist artifacts are emitted in standard review bundle.
- `tests/integration/test_deep_run.py`
  - Verifies reconciliation QC artifact emission.

## Intentionally Deferred
- Full specialist-agent expansion.
- Outlet-fit workflow integration.
- Any provider/runtime changes away from local-first defaults.

## Risk Controls
- No repository merge.
- No changes to commented DOCX or suggested-changes DOCX pipelines.
- No cloud dependencies added.
- Bounded additive artifacts only.
