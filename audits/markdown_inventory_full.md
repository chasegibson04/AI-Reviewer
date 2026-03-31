# Full Markdown Inventory

## Scope

This inventory covers every `*.md` / `README*` file currently present in the repository at the time of this pass.

Status meanings:
- `changed`: edited in this pass or earlier staged reconciliation because the file needed to reflect current behavior or had a markdown correctness issue
- `unchanged`: inspected and left as-is because it is accurate enough, historical by design, vendored/upstream, or a fixture/template artifact rather than a runtime product doc

## Inventory

| File | Status | Why | Remaining doc debt |
| --- | --- | --- | --- |
| `README.md` | changed | Reconciled product positioning, runtime defaults vs local overrides, manuscript outputs, DOCX behavior, verification posture, and optional-layer caveats. | Keep synced with future config default changes. |
| `docs/ai_reviewer/WORKFLOW_MECHANICS.md` | changed | Rewrote to match validated stage flow, routing modes, citation policy, DOCX behavior, and known weak points. | Add runtime depth/timing accounting here if that becomes a product artifact. |
| `docs/ai_reviewer/ARCHITECTURE.md` | changed | Updated module responsibilities and explicit deep-run routing / DOCX validation architecture. | Manifest schema uniformity is still not fully solved. |
| `docs/ai_reviewer/FULL_SYSTEM_REPORT_FOR_LLM.md` | changed | Replaced stale long-form summary with a concise implementation-grounded report aligned to actual runtime behavior. | Revisit when reconciliation/final-arbitration quality materially improves. |
| `docs/ai_reviewer/MODEL_SELECTION.md` | changed | Documented repo defaults vs local overrides, routing modes, benchmark-backed max-quality guidance, and safety rules. | Refresh if max-quality reconciliation materially improves. |
| `docs/ai_reviewer/orchestrator_design.md` | changed | Tightened to the current honest orchestrator role and limitations. | Expand only if orchestrator becomes a first-class quality gate. |
| `docs/ai_reviewer/PRIVACY_AUDIT.md` | changed | Added safe-online query policy and clarified metadata-only verification boundaries. | Could add more concrete outbound verification examples later. |
| `docs/ai_reviewer/PROJECTS_AND_SLACK.md` | changed | Reconciled project layout and project-first workflow wording. | Slack remains simulation-only; separate product docs would be needed if revived. |
| `docs/ai_reviewer/SECURITY.md` | changed | Reconciled strict-offline vs safe-online wording and current risk boundary. | Could add approved-project validation discipline as a security/process note later. |
| `docs/ai_reviewer/TRAINING_MATERIALS.md` | changed | Tightened to current cache/injection behavior and limits. | Could add one concrete artifact walk-through later. |
| `docs/ai_reviewer/TROUBLESHOOTING.md` | changed | Updated around DOCX no-op checks, safe-online verification, figure-review caveat, and final validation commands. | Could add more launcher-specific Mac examples if needed. |
| `docs/citation_fetch_methods.md` | changed | Reconciled method chain, verification labels, privacy policy, and extension path. | Add future method notes only when new methods ship. |
| `docs/design/suggested_changes_docx.md` | changed | Updated to match span-faithful rewrites, verifier gates, fallback/abstention behavior, and current output limitation. | Replace limitation section if native track changes are ever implemented. |
| `audits/TESTING_PROCEDURE.md` | changed | Contains the strict validation matrix and mechanical procedure for weaker agents. | Keep commands/examples refreshed as fixtures evolve. |
| `audits/docx_native_fixtures/README.md` | changed | Reconciled fixture source policy and no-op validation semantics. | Keep synced with fixture generator changes. |
| `audits/stage1_baseline_audit.md` | unchanged | Historical stage artifact retained as evidence. | Snapshot only; not a runtime doc. |
| `audits/stage1_execution_plan.md` | unchanged | Historical stage artifact retained as evidence. | Snapshot only; not a runtime doc. |
| `audits/stage2_section_mapping_report.md` | unchanged | Historical stage artifact retained as evidence. | Snapshot only; not a runtime doc. |
| `audits/stage3_comment_quality_report.md` | unchanged | Historical stage artifact retained as evidence. | Snapshot only; not a runtime doc. |
| `audits/stage4_suggested_revisions_report.md` | unchanged | Historical stage artifact retained as evidence. | Snapshot only; not a runtime doc. |
| `audits/stage5_docx_native_report.md` | unchanged | Historical stage artifact retained as evidence. | Snapshot only; not a runtime doc. |
| `audits/stage6_verification_report.md` | unchanged | Historical stage artifact retained as evidence. | Snapshot only; not a runtime doc. |
| `audits/stage7_max_quality_stack_report.md` | unchanged | Historical stage artifact retained as evidence. | Snapshot only; not a runtime doc. |
| `audits/stage8_figure_compliance_context_report.md` | unchanged | Historical stage artifact retained as evidence. | Snapshot only; not a runtime doc. |
| `audits/stage9_validation_report.md` | unchanged | Historical stage artifact retained as evidence. | Snapshot only; not a runtime doc. |
| `audits/stage10_markdown_inventory.md` | unchanged | Existing stage-10 inventory retained as part of release evidence. | Superseded by this full inventory for repo-wide coverage. |
| `audits/docx_native_analysis.md` | unchanged | Historical analysis note for DOCX-native issues. | Snapshot only; not a runtime doc. |
| `audits/markdown_inventory_overnight.md` | unchanged | Historical inventory note from an earlier pass. | Superseded by newer inventories. |
| `audits/final_harsh_audit_packet.md` | unchanged | Historical harsh audit packet retained as evidence. | Snapshot only. |
| `audits/overnight_quality_rebuild_analysis.md` | unchanged | Historical rebuild analysis retained as evidence. | Snapshot only. |
| `audits/rigorous_comparison_report.md` | unchanged | Historical comparison retained as evidence. | Snapshot only. |
| `audits/rigorous_integration_plan.md` | unchanged | Historical planning note retained as evidence. | Snapshot only. |
| `audits/current_state_note_quality_integration.md` | unchanged | Historical note retained as evidence. | Snapshot only. |
| `rigorous-main/README.md` | unchanged | Vendored upstream/project reference README, not AI-Reviewer product behavior. | Upstream external doc; stale relative to this repo by design. |
| `rigorous-main/Agent1_Peer_Review/README.md` | unchanged | Vendored upstream module README, not the active AI-Reviewer runtime path. | Upstream external doc; not reconciled to current product behavior. |
| `rigorous-main/Agent2_Outlet_Fit/README.md` | unchanged | Vendored upstream module README, not the active AI-Reviewer runtime path. | Upstream external doc; not reconciled to current product behavior. |
| `rigorous-main/Agent1_Peer_Review/src/reviewer_agents/rigor/README.md` | unchanged | Vendored upstream explanatory README. | Upstream external doc. |
| `templates/tensorf/README.md` | unchanged | AI-Scientist template README unrelated to AI-Reviewer runtime. | Template doc only. |
| `templates/earthquake-prediction/README.md` | unchanged | AI-Scientist template README unrelated to AI-Reviewer runtime. | Template doc only. |
| `templates/MACE/README.md` | changed | Fixed broken markdown/code fence and tightened wording. | Template doc only; not a product/runtime doc. |
| `templates/probes/README.md` | unchanged | AI-Scientist template README unrelated to AI-Reviewer runtime. | Template doc only. |
| `templates/nanoGPT/WRITEUP.md` | unchanged | Template writeup scaffold, not runtime product documentation. | Template artifact only. |
| `templates/nanoGPT_lite/WRITEUP.md` | unchanged | Template writeup scaffold, not runtime product documentation. | Template artifact only. |
| `tests/fixtures/sample_short.md` | unchanged | Test fixture input, not documentation. | Fixture only. |
| `tests/fixtures/sample_long.md` | unchanged | Test fixture input, not documentation. | Fixture only. |
| `tests/fixtures/draft_old.md` | unchanged | Test fixture input, not documentation. | Fixture only. |
| `tests/fixtures/draft_new.md` | unchanged | Test fixture input, not documentation. | Fixture only. |
| `temp_old.md` | unchanged | Local temporary markdown file, not a product doc. | Consider deleting if no longer needed. |
| `temp_new.md` | unchanged | Local temporary markdown file, not a product doc. | Consider deleting if no longer needed. |

## Remaining Global Doc Debt

- Final synthesis quality is still weaker than the manuscript-comment/rewrite layers; the docs now state that honestly, but the runtime still needs the improvement.
- Suggested revisions still use visible suggestion-block markup instead of native Word track changes.
- Figure review remains text-only and is not yet a strong default feature.
- Vendored `rigorous-main/*` READMEs are intentionally left as upstream reference docs and are not reconciled to current AI-Reviewer runtime behavior.
- Temporary markdown files at repo root (`temp_old.md`, `temp_new.md`) are not product docs and should be cleaned up later if they are no longer needed.
