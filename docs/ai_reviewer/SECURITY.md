# AI-Reviewer Security Notes

## Default Posture

- local Ollama runtime
- strict offline enabled by default in repo defaults
- no silent cloud fallback
- output artifacts retained for auditability
- support/context materials are local files

## Important Risk Distinction

- `ai-reviewer` commands are manuscript-review workflows and do not run model-written code
- legacy `ai_scientist` code is a separate higher-risk surface and should be sandboxed if used at all

## Strict-Offline Behavior

When `defaults.strict_offline: true`:
- non-local Ollama URLs are rejected
- citation metadata/download stages are still allowed under the citation query policy
- scholarly helper tools return disabled/offline status

## Safe-Online Behavior

When strict offline is intentionally disabled:
- citation fetch can contact configured metadata/OA endpoints
- no raw manuscript text is sent
- no long manuscript excerpts are sent
- query logging records type and length only
- `artifacts/verification_query_audit.json` should contain only query classes and lengths, never raw queries
- metadata retrieval still does not equal claim verification

## Recommended Practice

- keep Ollama local-only
- keep `strict_offline: true` to prevent non-local model/provider egress
- review artifacts after runs instead of trusting success banners alone
- use `diagnose`, `doctor`, and the testing procedure before release work
