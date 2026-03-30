# Privacy / Egress Audit

This document summarizes the real network and privacy boundaries of the current system.

## Static Egress Inventory

| Path | Purpose | Default | Strict-Offline Behavior | Manuscript Data Exposure |
| --- | --- | --- | --- | --- |
| `ai_reviewer/models/ollama_provider.py` | Local chat/embed calls to Ollama | Enabled | Non-local Ollama URLs rejected | Manuscript content can go to local Ollama only |
| `ai_reviewer/launcher_checks.py` | Local Ollama health/version checks | Enabled | Localhost only | No manuscript data |
| `ai_reviewer/review/citation_fetcher.py` | Optional citation metadata / OA lookup | Enabled | Still allowed in strict offline; query policy remains sanitized | No raw manuscript text; only sanitized derived queries |
| `ai_reviewer/tools/scholarly_tools.py` | Optional metadata helper calls | Disabled in strict offline | Returns disabled state in strict offline | No manuscript data in strict offline |
| `ai_reviewer/slack/*` | Local Slack simulation only | Disabled unless invoked | No network path by default | No manuscript data leaves machine |
| pip install / dependency setup | Environment setup | External only during install | Not part of manuscript runtime | No manuscript data |

## Safe-Online Citation Policy

Citation fetch remains privacy-constrained regardless of `strict_offline`.

Query policy written into artifacts:
- `no_manuscript_raw_text: true`
- `no_long_manuscript_excerpts: true`
- `no_support_paper_full_text: true`
- query logging records type and length only
- `artifacts/verification_query_audit.json` records query types seen and max observed query length without storing raw queries

Allowed query classes:
- DOI lookup
- Crossref title lookup
- Crossref short-title lookup
- local project PDF title match

## What Is Not Verified

Safe-online citation fetch does not prove that a cited paper supports a manuscript claim.
Current verification labels are intentionally limited to metadata/retrieval status such as:
- `citation_exists`
- `metadata_match_likely`
- `support_relationship_not_verified`
- `external_metadata_check_only`
- `needs_human_verification`

## Runtime Verification

Suggested checks:

```powershell
python -m ai_reviewer.cli diagnose
```

In strict offline mode, expected runtime network behavior is:
- local Ollama only for model inference
- citation metadata/OA retrieval may still occur using sanitized derived queries only

In safe-online mode, expected remote activity is limited to citation metadata/OA endpoints using sanitized derived queries only.
