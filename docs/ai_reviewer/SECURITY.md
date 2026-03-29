# AI-Reviewer Security Notes

Default behavior is local-first and privacy-preserving:
- Uses Ollama on `http://127.0.0.1:11434`
- Does not require cloud API keys for normal review workflow
- Strict offline mode blocks non-local Ollama endpoints
- Scholarly DOI lookups (Crossref/OpenAlex) are disabled when strict offline is enabled
- Optional context-pack inputs are local project materials and do not add new outbound surfaces by themselves

Important risk distinction:
- `ai-reviewer` commands are review-focused and do not run model-written code.
- Legacy `ai_scientist` autonomous experiment code can execute model-written code and should be sandboxed.

Recommended practices:
- Keep Ollama local-only
- Keep `defaults.strict_offline: true` for all manuscript workflows
- Run with least-privilege filesystem access where possible
- Keep raw artifacts for auditability
- Use `ai-reviewer diagnose` and `doctor` before production runs

Setup note:
- Initial dependency install uses pip and may require internet access.
- Runtime review workflows do not contact non-local endpoints in strict offline mode.
- When strict offline is disabled, citation fetch can contact configured metadata/OA endpoints using sanitized derived queries only.
