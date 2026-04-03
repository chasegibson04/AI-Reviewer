# BUILD_AND_RUNTIME_AUDIT
Date: 2026-04-03

## Canonical path status
- `scripts/smoke.sh` fails in this environment because Bun is unavailable (`bun: command not found`).
- Bun-native build path remains environment-blocked.

## Implemented fallback runtime path
Added `scripts/smoke_fallback.sh` to validate a defensible local path without Bun:
1. Python bridge compile check
2. Bridge integration test
3. Node provider/profile tests
4. New review-profile routing tests
5. Runtime doctor script (`scripts/doctor_runtime.sh`)

Result: fallback smoke passes in current environment.

## Additional runtime hardening
- Provider detection now recognizes local OpenAI-compatible endpoint URLs as `ollama` provider.
- This reduces remote-default drift when using local Ollama through OpenAI-compatible transport.

## Remaining blockers
- Cannot prove full OpenClaude standalone Bun build in this environment.
- Repo-wide typecheck remains noisy with pre-existing upstream/internal assumptions.
