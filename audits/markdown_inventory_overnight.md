# Markdown Inventory (Overnight Stress Sprint)

Generated at: 2026-03-29T03:53:45

## Inspected Files
- `README.md`
  - Updated: yes
  - Reason: Added deep-run context-pack command and artifacts; clarified deep-run vs single-pass model routing.
- `docs/ai_reviewer/ARCHITECTURE.md`
  - Updated: yes
  - Reason: Added deep-run context-pack/compliance responsibility note.
- `docs/ai_reviewer/FULL_SYSTEM_REPORT_FOR_LLM.md`
  - Updated: yes
  - Reason: Documented context-pack stage/artifacts and post-dedupe figure behavior.
- `docs/ai_reviewer/MODEL_SELECTION.md`
  - Updated: yes
  - Reason: Clarified single-pass defaults vs deep-run stage routing.
- `docs/ai_reviewer/orchestrator_design.md`
  - Updated: yes
  - Reason: Documented orchestrator quality-gate role with optional context-pack constraints.
- `docs/ai_reviewer/PRIVACY_AUDIT.md`
  - Updated: yes
  - Reason: Added citation_fetcher egress row and query-audit notes.
- `docs/ai_reviewer/SECURITY.md`
  - Updated: yes
  - Reason: Clarified context-pack local behavior and strict-offline/network boundary.
- `docs/ai_reviewer/TROUBLESHOOTING.md`
  - Updated: yes
  - Reason: Added context-pack troubleshooting section and forced-off benchmark tip.
- `docs/ai_reviewer/WORKFLOW_MECHANICS.md`
  - Updated: yes
  - Reason: Added context-pack selection and deterministic compliance stage details.
- `docs/ai_reviewer/PROJECTS_AND_SLACK.md`
  - Updated: no
  - Reason: Current project/material and Slack simulation behavior unchanged in this pass.
- `docs/ai_reviewer/TRAINING_MATERIALS.md`
  - Updated: no
  - Reason: Training ingestion/injection behavior unchanged in this pass.
- `docs/citation_fetch_methods.md`
  - Updated: no
  - Reason: Method order/registration unchanged; docs already accurate.
- `docs/design/suggested_changes_docx.md`
  - Updated: no
  - Reason: Suggested-change rendering mechanism unchanged in this pass.
- `audits/project_access_guard.md`
  - Updated: yes
  - Reason: Refreshed for this overnight stress/quality sprint.
- `audits/overnight_quality_rebuild_analysis.md`
  - Updated: yes
  - Reason: Replaced with current-pass plan/execution and benchmark summary.
- `audits/final_harsh_audit_packet.md`
  - Updated: yes
  - Reason: Updated with current deep-run and figure benchmark outcomes.
- `audits/overnight_stress_matrix.md`
  - Updated: yes
  - Reason: Added/updated benchmark matrix for baseline vs orchestrator/context/figure scenarios.

## Remaining Doc Debt
- Add dedicated SAFE_ONLINE_MODE.md that maps strict-offline and citation-fetch-safe-online behavior to exact config toggles and artifacts.
- Add a concise QUALITY_GATES.md mapping orchestrator/stage QC signals to pass/fail criteria.
- Run one physical Apple Silicon overnight validation and append results to docs/ai_reviewer/TROUBLESHOOTING.md.
