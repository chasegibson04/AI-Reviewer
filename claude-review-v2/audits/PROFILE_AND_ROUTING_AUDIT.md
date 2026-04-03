# PROFILE_AND_ROUTING_AUDIT
Date: 2026-04-03

## Profile options implemented
Selectable review profiles:
1. `balanced_local`
2. `deep_local`
3. `local_moe` (default review profile)
4. `one_big_model`
5. `full_manuscript_final_pass`
6. `quick_local`
7. `offline_strict`
8. `llama_cpp_standard`
9. `llama_cpp_turboquant`

Alias shortcuts supported in `/profile`: `moe`, `big`, `final`, `balanced`, `deep`, `quick`, `offline`.

## Gemma 4 routing behavior
- `one_big_model`:
  - prefer `gemma4:26b`
  - if unavailable, use `gemma4:31b`
  - else configured big model or largest detected local model.
- `full_manuscript_final_pass`:
  - same Gemma preference order (`26b` then `31b`) with fallback logic.

## Runtime visibility added
- `/profile` shows current profile, resolved model target, fallback usage, and inventory summary.
- `/diagnose` and `/doctor` show selected profile and Gemma detection status.
- Startup now prints active profile/mode/target and profile choices.

## Local-first routing hardening
- Provider detection now treats OpenAI-compat local base URLs (`localhost`) as `ollama` provider.
- This reduces accidental remote-default model behavior when local OpenAI-compatible endpoint is used.

## Validation evidence
- Big-model run artifact (`test_outputs/pytest_bridge_run_b/run_summary.json`) records:
  - `profile: one_big_model`
  - `mode: single big-model review`
  - `model_target: gemma4:31b`
