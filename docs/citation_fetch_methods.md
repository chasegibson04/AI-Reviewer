# Citation Fetch Methods

Citation fetch runs before `review` and `deep-run` when enabled and not blocked by strict offline mode.

## Integration Points

- `ai_reviewer/cli.py`
- `ai_reviewer/review/citation_fetcher.py`

## Current Method Chain

Configured order:
- `doi_open_access_apis`
- `crossref_lookup_then_oa`
- `local_project_pdf_match`
- `crossref_short_title_then_oa`

Meaning:
- DOI/OA and normal Crossref lookup remain primary
- local project PDF reuse and shortened-title lookup are fallbacks, not replacements

## What The Artifact Now Records

Per-run citation artifacts include:
- method order
- per-reference attempts and statuses
- normalized reference strings
- query policy
- verification policy
- per-entry verification labels

Current verification labels:
- `citation_exists`
- `metadata_match_likely`
- `support_relationship_not_verified`
- `external_metadata_check_only`
- `needs_human_verification`

These labels are intentionally honest: retrieval does not prove claim support.

## Privacy Policy

When citation fetch is allowed online:
- no raw manuscript text is sent
- no long manuscript excerpts are sent
- no support-paper full text is sent
- query logging records type and length only

Allowed query types currently include:
- `doi_lookup`
- `crossref_title_lookup`
- `crossref_short_title_lookup`
- `local_pdf_title_match`

## Runtime Switches

- `AI_REVIEWER_CITATION_FETCH_ENABLED=true|false`
- `AI_REVIEWER_CITATION_FETCH_METHODS=...`
- `AI_REVIEWER_STRICT_OFFLINE=true|false`

If `strict_offline=true`, citation fetch exits early with `reason = strict_offline`.

## Extension Point

To add a new method:
1. add a method function in `ai_reviewer/review/citation_fetcher.py`
2. register it in `REGISTERED_CITATION_METHODS`
3. add it to `config/defaults.yaml` or `AI_REVIEWER_CITATION_FETCH_METHODS`
