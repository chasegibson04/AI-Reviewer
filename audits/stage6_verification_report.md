# Stage 6 Verification Report

## Scope

- truth / citation / support verification only
- approved projects only: `20260325163524_test-existingphactorpaper`, `20260327051312_miniaturization_d2b`

## What changed

- Citation fetch entries now carry explicit verification labels instead of retrieval status alone.
- Query policy artifacts now state that raw manuscript text, long excerpts, and support-paper full text must not be sent.
- Support-material filtering now labels selected material as `support_relationship_plausible` and skipped material as `support_relationship_not_verified`.
- Support selection is explicitly marked as `lexical_overlap_only` and `internal_consistency_check_only`, which prevents it from reading like real claim verification.
- Manuscript-like support duplicates are now blocked with `manuscript_like_duplicate`.
- Review and deep-run paths now emit `internal_consistency_checks.json`.

## Verification label policy

- `citation_exists`: a DOI or likely citation target was found or reused
- `metadata_match_likely`: reference string and resolved metadata probably match
- `support_relationship_not_verified`: retrieval did not prove the manuscript claim is supported
- `internal_consistency_check_only`: only manuscript-internal or support-overlap checks were performed
- `external_metadata_check_only`: only external metadata/retrieval checks were performed
- `needs_human_verification`: manual verification is still required

## Privacy-safe verification

- Query audit logs only query type and query length.
- Citation fetch reports now declare explicit query restrictions in `query_policy`.
- Strict-offline behavior remains unchanged: citation fetch exits early with `reason = strict_offline`.

## Focused validation results

- `20260325163524_test-existingphactorpaper`: refs=`48`, citation_exists_like=`48`, needs_human_verification=`48`, support_selected=`11`, support_skipped=`4`, duplicate_support_skipped=`1`, internal_consistency_findings=`1`
- `20260327051312_miniaturization_d2b`: refs=`94`, citation_exists_like=`94`, needs_human_verification=`94`, support_selected=`2`, support_skipped=`1`, duplicate_support_skipped=`0`, internal_consistency_findings=`0`

## Before vs after

- Before: citation fetch artifacts reported method status only. After: each entry has a `verification` block that separates citation existence from support verification.
- Before: support-material filtering only said selected/skipped by overlap. After: selected and skipped entries include verification labels, provenance, and explicit scope limits.
- Before: manuscript-like support duplicates could be selected. After: project 1 shows one duplicate support item skipped with `manuscript_like_duplicate`.
- Before: no explicit internal consistency artifact. After: `internal_consistency_checks.json` is emitted with explicit `internal_consistency_check_only` scope.

## Key artifact paths

- `audits/stage6_validation/summary.json`
- `20260325163524_test-existingphactorpaper` citation fetch: `audits/stage6_validation/20260325163524_test-existingphactorpaper/artifacts/citation_fetch_report.json`
- `20260325163524_test-existingphactorpaper` support filtering: `audits/stage6_validation/20260325163524_test-existingphactorpaper/support_material_filtering.json`
- `20260325163524_test-existingphactorpaper` internal consistency: `audits/stage6_validation/20260325163524_test-existingphactorpaper/internal_consistency_checks.json`
- `20260327051312_miniaturization_d2b` citation fetch: `audits/stage6_validation/20260327051312_miniaturization_d2b/artifacts/citation_fetch_report.json`
- `20260327051312_miniaturization_d2b` support filtering: `audits/stage6_validation/20260327051312_miniaturization_d2b/support_material_filtering.json`
- `20260327051312_miniaturization_d2b` internal consistency: `audits/stage6_validation/20260327051312_miniaturization_d2b/internal_consistency_checks.json`

## Remaining limitations

- The system still does not verify claim-to-citation support at full-text paper level.
- `citation_exists` plus `metadata_match_likely` still does not mean the cited paper actually supports the manuscript sentence.
- Support-material selection is still heuristic lexical grounding, not semantic evidence tracing.
- Internal consistency checks are lightweight and heuristic; they flag broad scope mismatches but do not reason through all claims.