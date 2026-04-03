# REVIEW_DOMAIN_AUDIT
Date: 2026-04-03

## Domain objective
OpenClaude shell behavior with manuscript-review-native tooling, local-first defaults, and meaningful artifact output.

## What is real now
- Domain tool names required for manuscript review are present and callable via bridge.
- Parsing/discovery and section/analysis/edit/arbitration stages produce deterministic structured outputs.
- Artifact writer emits broad run output set including ledgers, compliance reports, routing trace, summaries, and transcript.
- Validation checks core safety/contract concerns and writes `validation_report.json`.

## Where quality is still below full AI-Reviewer parity
- Tool analyses are currently heuristics, not full model-backed deep review wrappers.
- Citation and claim verification reports are structurally present but simplified.
- No native DOCX mutation path from TS shell in this pass; bridge emits manifests/reports instead.

## Prompt/wrapper status
- `/review`, `/deep-run`, `/replay`, `/diff` prompts were tightened to require staged tools and honest partial reporting.
- Prompt rigor improved, but complete parity with AI-Reviewer’s strongest wrappers is still incomplete.

## Conclusion
- The review domain is now materially executable and testable with meaningful artifacts.
- It is still a partial parity implementation versus full AI-Reviewer deep-run semantics.
