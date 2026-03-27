# Orchestrator Design (Local CPU-First)

## Purpose
The orchestrator is a bounded controller that improves quality control across specialist review stages.
It does not replace specialist reviewers and does not run open-ended autonomous loops.

## Model
- Default orchestrator model: `qwen3:8b`
- Low creativity (`temperature=0.0`)
- JSON-constrained outputs for controller decisions

## Responsibilities
- Evaluate stage quality (specificity, grounding, actionability, genericity)
- Decide whether a bounded retry is worthwhile
- Compare version A vs B after retry
- Evaluate profile distinctness (balanced/adversarial/methods/etc.)
- Validate final synthesis quality for deep-run

## Non-Responsibilities
- Not the primary scientific reviewer
- Not the primary manuscript author
- No external web validation in strict offline mode
- No open-ended recursion

## Retry Budgets
- `max_stage_retries` (default `1`)
- `max_total_retries` (default `3`)
- Stop retries when no material improvement is detected

## Failure Modes
- `fail_open=true`: continue baseline pipeline and log orchestrator failure
- `fail_open=false`: fail fast with explicit error

## Decision Artifacts
Written to run-local bundle directories:
- `orchestrator_decisions.json`
- `orchestrator_stage_quality.json`
- `orchestrator_retry_log.json`
- `orchestrator_distinctness_report.json` (evaluation/deep-run)
- `orchestrator_final_synthesis_check.json` (deep-run)

Each artifact contains stage-scoped decisions and quality signals for audit/debug.

