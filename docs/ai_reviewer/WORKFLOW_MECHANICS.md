# AI-Reviewer Workflow Mechanics

This document describes the current runtime behavior that was validated during the staged rebuild.

## 1. Guided Launch

`launch` is a wrapper over existing commands:
- `single-review` -> `review --project <id>`
- `batch-review` -> `review --project <id> --material-ids <...>`
- `deep-run` -> `deep-run --project <id>`
- `compare-drafts` -> `compare`
- `full-evaluation-sweep` -> `evaluate-paper`
- `benchmark-models` -> `benchmark`
- `diagnose` -> `diagnose`

Before routing it:
- syncs project folders
- syncs training-material cache when enabled
- detects local Ollama models

## 2. `review`

### Targeting

- `review <input_path>` parses the given file/folder directly
- `review --project <id>` targets manuscript materials by default
- `materials/other` are supporting docs only
- support docs are filtered by overlap and blocked markers before grounding

### Main runtime steps

Per primary document:
1. parse source
2. optional citation fetch stage
3. optional retrieval build/use
4. main review generation
5. sparse-output enrichment when needed
6. commented manuscript output
7. suggested-revision output
8. output verification

### Source modes

- PDF input -> `pdf_only_surrogate`
- native DOCX input -> `original_docx`

For native DOCX input the system now records annotation state and validates whether a re-review added meaningful new review state.

## 3. `deep-run`

`deep-run` is a bounded staged workflow.

### Stage families

1. sync, source detection, manifests
2. manuscript/support ingest and filtering
3. structural triage
4. supporting digest
5. manuscript digest
6. evidence/context linking
7. context synthesis
8. high-level review
9. hostile review
10. methods verification
11. line edits
12. style alignment
13. optional deterministic context-pack compliance check
14. reconciliation
15. bounded final arbitration
16. manuscript comment + suggested-revision generation
17. final report bundle + verification

### Key artifacts

- `deep_run_plan.json`
- `stage_model_stack.json`
- `context_pack_used.json`
- `stage_10b_compliance_check.json`
- `final_deep_review_report.{json,md,txt,docx}`
- commented/suggested manuscript outputs and validation files

### Routing modes

Configured in:
- `config/defaults.yaml`
- `deep_run_routing.mode`
- `AI_REVIEWER_DEEP_RUN_ROUTING_MODE`

Supported values:
- `default`
- `max_quality`

`default`:
- keeps digest/editor stages on balanced-capable models
- uses stronger critique models when available
- keeps reconciliation on repair-capable models

`max_quality`:
- keeps structural triage cheap
- moves digest/evidence/style stages onto stronger local models when available
- keeps final arbitration on the strongest available critique model
- is benchmarked, not assumed to be universally better

### Important honesty point

Benchmark evidence showed:
- max-quality routing improved style/edit surfacing
- max-quality routing did not yet improve final reconciliation quality consistently

## 4. Manuscript Annotation and Suggested Revisions

Current behavior:
- comments are localized to paragraphs/spans
- comments are filtered for genericity/duplication
- suggested revisions are span-faithful where possible
- rewrites are verified for fluency, faithfulness, and unsupported additions
- unsafe rewrites abstain instead of forcing bad local edits

DOCX behavior:
- existing comments are preserved
- visible prior suggestion blocks are preserved but removed from analysis text
- follow-up suggested changes are appended when prior suggestion blocks already exist

Validation artifacts:
- `manuscript_comment_manifest.json`
- `commented_docx_validation.json`
- `manuscript_suggested_changes_manifest.json`
- `suggested_changes_validation.json`

## 5. Citation Fetch and Verification

Citation fetch runs before `review` and `deep-run` when enabled and not blocked by strict offline mode.

Current configured method chain:
- `doi_open_access_apis`
- `crossref_lookup_then_oa`
- `local_project_pdf_match`
- `crossref_short_title_then_oa`

Safe-online query policy:
- no raw manuscript text
- no long manuscript excerpts
- no support-paper full text
- query logging records type and length only

Current verification labels distinguish retrieval from support:
- `citation_exists`
- `metadata_match_likely`
- `support_relationship_not_verified`
- `external_metadata_check_only`
- `needs_human_verification`

## 6. Optional Layers

### Figure review

Current validated mode is text-only:
- PDF image extraction
- heuristic caption pairing
- nearby-text critique

Validated result on the approved projects:
- figure review added more caption-parsing noise than quality
- keep OFF by default until a better multimodal path exists

### Context-pack / compliance

Current behavior:
- optional context materials can add deterministic compliance constraints
- findings are written to compliance artifacts and propagated into final weaknesses/actions
- keep opt-in; do not let it replace normal manuscript review

## 7. Failure and Fallback Behavior

- missing manuscript -> explicit failure
- stage errors -> warning + artifact when possible
- reconciliation may still fall back to deterministic synthesis
- final arbitration may be skipped if schema-incomplete
- runs are verified after artifact generation

## 8. What Is Still Weak

- balanced review memos can still read too generically
- final deep synthesis still falls back too often because reconciliation/arbitration schema compliance is weak
- suggested revisions are not native Word track changes
- figure review is not yet a reliable quality booster
