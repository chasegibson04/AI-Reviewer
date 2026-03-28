# Citation Fetch Integration (Pre-Run)

This repo now runs citation-paper download before review/deep-run analysis starts.

## Where it is integrated

1. Pre-run stage calls:
- `ai_reviewer/cli.py`
  - `review`: calls `fetch_citations_for_documents(...)` before review stages.
  - `deep-run`: calls `fetch_citations_for_documents(...)` before deep-run stages.

2. Citation fetch engine:
- `ai_reviewer/review/citation_fetcher.py`

## How to add/modify fetch methods

The fetch pipeline is method-driven and ordered by config.

1. Add a method function in:
- `ai_reviewer/review/citation_fetcher.py`

Method signature:
- input: `CitationMethodContext`
- output: `CitationMethodResult`

2. Register it in:
- `REGISTERED_CITATION_METHODS`

3. Enable/order it in config:
- `config/defaults.yaml` under:
  - `citation_fetch.methods`
- or env var:
  - `AI_REVIEWER_CITATION_FETCH_METHODS=method_a,method_b`

## Current built-in methods

- `doi_open_access_apis`
  - DOI-based OA lookup + PDF download.
- `crossref_lookup_then_oa`
  - Title/reference lookup via Crossref, then OA DOI download.

These are adapted from `Copy of PaperScraperV2` ideas (title extraction, Crossref lookup, robust PDF-byte validation).

## Output location and artifacts

Downloaded files:
- `projects/<project_id>/materials/other/*.pdf`

Per-run report:
- `projects/<project_id>/runs/<run_id>/artifacts/citation_fetch_report.json`

This report includes method order, attempts, statuses, saved paths, and totals.

## Important runtime switches

- `AI_REVIEWER_CITATION_FETCH_ENABLED=true|false`
- `AI_REVIEWER_CITATION_FETCH_METHODS=...`
- `AI_REVIEWER_STRICT_OFFLINE=true|false`

If `strict_offline=true`, citation download is skipped intentionally.
