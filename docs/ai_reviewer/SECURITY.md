# AI-Reviewer Security Notes

Default behavior is local-first and privacy-preserving:
- Uses Ollama on `http://127.0.0.1:11434`
- Does not require cloud API keys for normal review workflow
- Strict offline mode blocks non-local Ollama endpoints

Important risk distinction:
- `ai-reviewer` commands are review-focused and do not run model-written code.
- Legacy `ai_scientist` autonomous experiment code can execute model-written code and should be sandboxed.

Recommended practices:
- Keep Ollama local-only
- Run with least-privilege filesystem access where possible
- Keep raw artifacts for auditability
- Use `ai-reviewer diagnose` and `doctor` before production runs
