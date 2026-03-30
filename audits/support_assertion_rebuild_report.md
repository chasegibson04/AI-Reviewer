# Support / Assertion / Citation / Compliance Rebuild Report

## Scope

This pass rebuilt the support-ingest, assertion-checking, citation-linkage, and compliance-visibility layer.

Approved projects only:
- `20260325163524_test-existingphactorpaper`
- `20260327051312_miniaturization_d2b`

## Why The Old Path Was Not Trustworthy Enough

- `materials/other` were filtered and sometimes injected into prompts, but there was no explicit support-ingest ledger and no proof of where support files influenced review decisions.
- Citation fetch reported metadata/retrieval status, but there was no claim-to-citation map and no artifact showing which manuscript assertions were actually screened.
- Internal consistency checks were broad and manuscript-level only.
- Compliance checking existed, but it was mostly a side artifact in deep-run rather than a visible output class in standard review.
- Privacy constraints existed, but the query-audit surface was not explicit enough in standalone artifacts.

## Code Changes

- Added shared verification module:
  - `ai_reviewer/review/verification.py`
- Integrated explicit artifacts into `review`:
  - `support_ingest_report.json`
  - `support_relevance_report.md`
  - `support_usage_ledger.json`
  - `assertion_ledger.json`
  - `assertion_review.md`
  - `claim_verification_summary.json`
  - `claim_to_citation_map.json`
  - `citation_verification_ledger.json`
  - `citation_accuracy_report.md`
  - `format_compliance_report.json`
- Integrated the same evidence model into `deep-run` and final report payloads.
- Added `artifacts/verification_query_audit.json` to citation fetch outputs.
- Added direct real-project audit helper:
  - `scripts/run_support_claim_validation.py`

## Real Approved-Project Validation

Artifacts written under:
- `audits/support_claim_validation/20260325163524_test-existingphactorpaper`
- `audits/support_claim_validation/20260327051312_miniaturization_d2b`
- `audits/support_claim_validation/summary.json`

Summary from current approved-project audit:
- project 1: 14 support docs available, 11 selected, 80 claims extracted/checked, 24 references extracted, 12 references linked to claims, 5 compliance findings
- project 2: 3 support docs available, 2 selected, 78 claims extracted/checked, 47 references extracted, 43 references linked to claims, 4 compliance findings

## Honest Remaining Weaknesses

- Full end-to-end model-driven `review` on the approved PDFs remained too slow to use as the primary validator for this pass.
- Claim extraction on noisy PDF text is still heuristic and can over-include some front-matter-derived prose.
- `cited_support_verified` remains intentionally rare; most outputs still land in plausible/unresolved buckets.
- Compliance checks are more visible now, but still heuristic rather than full journal-rule execution.
