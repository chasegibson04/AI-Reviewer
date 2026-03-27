# Privacy / Egress Audit

This document summarizes known network egress paths and how strict offline mode constrains them.

## Static Egress Inventory

| Path | Purpose | Default | Strict Offline Behavior | Manuscript Data Exposure |
| --- | --- | --- | --- | --- |
| `ai_reviewer/models/ollama_provider.py` | Local model calls to Ollama (`/api/chat`, `/api/embed`) | Enabled | Requires localhost/127.0.0.1; non-local URLs rejected | Manuscript content can be sent to local Ollama only |
| `ai_reviewer/launcher_checks.py` | Launcher self-check to Ollama `/api/version` | Enabled | Localhost only | No manuscript data |
| `ai_reviewer/tools/scholarly_tools.py` | DOI metadata via Crossref/OpenAlex | Disabled | Returns `{enabled: False}` in strict offline | No manuscript data in strict offline |
| `ai_reviewer/slack/*` | Local Slack simulation file IO | Disabled unless invoked | No network usage | No manuscript data leaves machine |
| Launcher pip install | Dependency setup | Enabled on first run | Uses pip network during setup only | No manuscript data |

## Notes
- There are no OpenAI/Anthropic/remote provider integrations in the runtime path.
- Strict offline mode blocks non-local Ollama base URLs.
- Any scholarly DOI lookup is disabled when strict offline is enabled.

## Runtime Verification (Mac)

Suggested commands to verify outbound connections during runtime:

1. Launcher startup:
```
nettop -m tcp -p <PID>
```
2. Minimal review:
```
lsof -i -n -P | grep ai_reviewer
```
3. Deep-run startup (no manuscript content required beyond smoke test):
```
netstat -an | grep ESTABLISHED
```

Expected behavior in strict offline mode:
- Only `127.0.0.1:11434` (Ollama) connections should appear.
- No non-local endpoints should be contacted during review/deep-run workflows.

If non-local connections appear, disable strict offline override and inspect configuration.
