# Stage 10 Markdown Inventory

## Files Inspected

| File | Status | Why | Remaining doc debt |
| --- | --- | --- | --- |
| `README.md` | changed | Reconciled product positioning, runtime defaults vs local overrides, manuscript outputs, DOCX behavior, verification posture, and optional-layer caveats. | Keep synced with future config default changes. |
| `docs/ai_reviewer/WORKFLOW_MECHANICS.md` | changed | Rewrote to match validated stage flow, routing modes, citation policy, DOCX behavior, and known weak points. | Add stage timing/depth accounting once Stage 10+ runtime accounting is expanded further. |
| `docs/ai_reviewer/ARCHITECTURE.md` | changed | Updated module responsibilities and explicit deep-run routing / DOCX validation architecture. | Manifest schema uniformity is still not fully solved. |
| `docs/ai_reviewer/FULL_SYSTEM_REPORT_FOR_LLM.md` | changed | Replaced stale long-form summary with a concise implementation-grounded system report aligned to final validated behavior. | Revisit once reconciliation/final-arbitration quality materially improves. |
| `docs/ai_reviewer/MODEL_SELECTION.md` | changed | Documented repo defaults vs local overrides, routing modes, benchmark-backed max-quality guidance, and safety rules. | Benchmark guidance should be refreshed when max-quality reconciliation improves. |
| `docs/ai_reviewer/orchestrator_design.md` | changed | Tightened to current honest orchestrator role and limitations. | Orchestrator docs may need expansion if it becomes a primary quality gate later. |
| `docs/ai_reviewer/PRIVACY_AUDIT.md` | changed | Added safe-online query policy and clarified metadata-only verification boundaries. | Full outbound verification examples could be expanded later. |
| `docs/ai_reviewer/PROJECTS_AND_SLACK.md` | changed | Reconciled project layout and project-first workflow wording. | Slack remains simulation-only and may need separate production docs if revived. |
| `docs/ai_reviewer/SECURITY.md` | changed | Reconciled strict-offline vs safe-online wording and clarified current risk boundary. | Could add a short section on approved validation project discipline if desired. |
| `docs/ai_reviewer/TRAINING_MATERIALS.md` | changed | Tightened to current cache/injection behavior and limits. | Could add one concrete artifact example later. |
| `docs/ai_reviewer/TROUBLESHOOTING.md` | changed | Updated around DOCX no-op checks, safe-online verification, figure-review caveat, and final validation commands. | Add more launcher-specific Mac examples only if needed. |
| `docs/citation_fetch_methods.md` | changed | Reconciled method chain, verification labels, privacy policy, and extension path. | Add future method notes only when new methods are actually shipped. |
| `audits/TESTING_PROCEDURE.md` | changed | Stage 9 produced a strict, mechanical validation procedure with exact command matrix and pass/fail rules. | Keep command IDs/examples refreshed as project fixtures evolve. |
| `docs/design/suggested_changes_docx.md` | changed | Updated to match span-faithful rewrites, verifier gates, fallback/abstention behavior, and current output limitation. | Replace limitation section if native track changes are ever implemented. |
| `audits/docx_native_fixtures/README.md` | changed | Reconciled fixture source policy and no-op validation semantics. | Keep synced with fixture generator changes. |
| `audits/stage1_baseline_audit.md` | unchanged | Historical audit artifact; still accurate as a baseline snapshot. | Snapshot only; not a runtime doc. |
| `audits/stage2_section_mapping_report.md` | unchanged | Historical stage report retained as evidence. | Snapshot only; not a runtime doc. |
| `audits/stage3_comment_quality_report.md` | unchanged | Historical stage report retained as evidence. | Snapshot only; not a runtime doc. |
| `audits/stage4_suggested_revisions_report.md` | unchanged | Historical stage report retained as evidence. | Snapshot only; not a runtime doc. |
| `audits/stage5_docx_native_report.md` | unchanged | Historical stage report retained as evidence. | Snapshot only; not a runtime doc. |
| `audits/stage6_verification_report.md` | unchanged | Historical stage report retained as evidence. | Snapshot only; not a runtime doc. |
| `audits/stage7_max_quality_stack_report.md` | unchanged | Historical stage report retained as evidence. | Snapshot only; not a runtime doc. |
| `audits/stage8_figure_compliance_context_report.md` | unchanged | Historical stage report retained as evidence. | Snapshot only; not a runtime doc. |
| `audits/stage9_validation_report.md` | unchanged | Final validation report from Stage 9; used as evidence, not rewritten. | Snapshot only; not a runtime doc. |

## Remaining Global Doc Debt

- Final synthesis quality is still weaker than the manuscript-comment/rewrite layers; docs now state that honestly, but the product still needs the runtime improvement.
- Suggested revisions still use visible suggestion-block markup instead of native Word track changes.
- Figure review remains text-only and is not yet documented as a strong default feature because it is not one.
- Older run artifacts still use slightly different manifest shapes, which complicates automated comparisons and must remain documented as a limitation.
