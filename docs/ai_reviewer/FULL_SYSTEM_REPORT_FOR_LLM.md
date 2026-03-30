# AI-Reviewer / PaperReviewer: Full System Report For LLMs

Date: 2026-03-29
Repository: `AI-Reviewer`

This file is an implementation-grounded summary for another agent. It is intentionally concise and aligned to the validated system state after Stage 10.

## 1. System Identity

AI-Reviewer is a local-first manuscript review system that produces:
- structured review reports
- commented manuscript DOCX output
- suggested-revision DOCX output
- run-local manifests and validation artifacts

It is not a cloud-first reviewer and not an autonomous research agent.

## 2. Main Runtime Paths

Core commands:
- `review`
- `deep-run`
- `evaluate-paper`
- `compare`
- `diagnose`
- `benchmark`
- `training ...`

Primary code paths:
- `ai_reviewer/cli.py`
- `ai_reviewer/review/engine.py`
- `ai_reviewer/review/deep_run.py`
- `ai_reviewer/review/manuscript_annotation.py`
- `ai_reviewer/review/citation_fetcher.py`
- `ai_reviewer/tools/docx_tools.py`
- `ai_reviewer/models/selector.py`

## 3. Config and Runtime Policy

Merge order:
1. `config/defaults.yaml`
2. `config/local.yaml`
3. `config/local.override.yaml`
4. `--config-path`
5. environment overrides

Important repo defaults:
- `strict_offline: true`
- citation fetch enabled and still allowed under strict offline using sanitized metadata/OA queries
- `deep_run_routing.mode: default`

Important caveat:
- local overrides can make real runs materially stronger than repo defaults
- benchmark artifacts in `audits/` are the source of truth for what actually ran on this machine

## 4. Review Pipeline

`review` does, in order:
1. resolve project/direct input
2. optional citation fetch stage
3. parse manuscript
4. filter support materials before grounding
5. optional retrieval
6. generate/repair review output
7. enrich sparse output when needed
8. generate commented manuscript output
9. generate suggested-revision output
10. verify required artifacts

Artifacts per document include:
- `validated_review.json`
- `review_report.md`
- `run_metadata.json`
- `section_map.json`
- comment/suggested-change manifests
- commented/suggested DOCX validation JSONs

## 5. Deep-Run Pipeline

Deep-run is staged, not a single prompt.

Stage families:
- source ingest and structural triage
- support/manuscript digestion
- context/evidence linking and synthesis
- high-level, hostile, and methods critique
- line edits and style alignment
- optional deterministic context-pack compliance check
- reconciliation
- bounded final arbitration
- manuscript annotation and final report bundle

Deep-run writes:
- `deep_run_plan.json`
- `stage_model_stack.json`
- stage JSON/MD artifacts
- `final_deep_review_report.{json,md,txt,docx}`

## 6. Model Routing

`ai_reviewer/models/selector.py` now owns deep-run stage routing.

Supported routing modes:
- `default`
- `max_quality`

Safety rules:
- embedding models never enter chat stages
- multimodal models are not used for text-only deep-run stages
- Mac ARM fallback is explicit for large-model absence

Validated benchmark result:
- max-quality routing improved style/edit surfacing
- max-quality routing did not yet consistently improve final reconciliation quality

## 7. Native DOCX and Suggested Revisions

`ai_reviewer/review/manuscript_annotation.py` plus `ai_reviewer/tools/docx_tools.py` now support:
- clean native DOCX
- DOCX with existing comments
- prior AI-commented DOCX
- prior AI-suggested DOCX

Policy:
- preserve old comments
- preserve visible old suggestion blocks
- strip visible suggestion blocks from analysis text
- layer new comments on top
- append follow-up suggestion blocks when needed

Validation tracks:
- meaningful new review state
- silent no-op suspicion

Suggested revisions are span-faithful where possible and now abstain more aggressively on malformed or non-local issues.

Current limitation:
- output is still visible suggestion-block markup, not Word track changes

## 8. Verification and Privacy

Citation fetch is metadata-only when online fetching is enabled.

Current method chain:
- `doi_open_access_apis`
- `crossref_lookup_then_oa`
- `local_project_pdf_match`
- `crossref_short_title_then_oa`

Query policy:
- no raw manuscript text
- no long manuscript excerpts
- no support-paper full text
- query logging records type and length only

Verification labels distinguish retrieval from proof:
- `citation_exists`
- `metadata_match_likely`
- `support_relationship_not_verified`
- `external_metadata_check_only`
- `needs_human_verification`

The system does not currently verify full claim-to-paper support.

## 9. Optional Layers

Figure review:
- currently text-only on validated paths
- useful mainly as caption-parsing/nearby-text critique
- benchmarked worse than OFF on the two approved PDFs
- should remain OFF by default

Context-pack/compliance:
- deterministic opt-in layer
- useful for concrete requirements like missing reporting items
- should not replace normal manuscript review

## 10. Honest Current Gaps

- balanced review reports can still be too generic
- deep-run reconciliation/final arbitration still falls back too often
- manifest schema is not fully uniform across older and newer runs
- figure review is not yet a general quality win
- suggested revisions are not native track changes
