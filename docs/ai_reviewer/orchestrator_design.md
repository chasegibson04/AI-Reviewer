# Orchestrator Design

## Purpose

The orchestrator is a bounded quality-control layer.
It is not the primary reviewer and it does not run open-ended autonomous loops.

## Current State

- default: `enabled: false`
- default model: `phi4-reasoning:latest`
- decision style: low-temperature, JSON-constrained
- fail-open behavior remains configurable

## Responsibilities

- assess stage quality signals such as specificity, grounding, actionability, and genericity
- decide whether a bounded retry is justified
- compare version A vs B after retry
- evaluate cross-profile distinctness
- assess final synthesis quality when orchestrator is active

## Non-Responsibilities

- not the main manuscript reviewer
- not the final source of truth for citation verification
- not a replacement for manuscript-first comments/revisions
- no external web validation in strict offline mode

## Important Limitation

Current validation did not prove the orchestrator as the main quality driver.
The largest remaining deep-run bottleneck is still reconciliation/final-arbitration schema quality, not orchestrator availability.

## Retry Budget

- `max_stage_retries` default: `1`
- `max_total_retries` default: `3`
- retries stop when no material improvement is detected

## Artifacts

When active, run-local artifacts can include:
- `orchestrator_decisions.json`
- `orchestrator_stage_quality.json`
- `orchestrator_retry_log.json`
- `orchestrator_distinctness_report.json`
- `orchestrator_final_synthesis_check.json`

Use these for audit, not for marketing claims.
