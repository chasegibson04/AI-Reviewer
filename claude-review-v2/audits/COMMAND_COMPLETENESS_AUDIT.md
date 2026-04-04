# COMMAND_COMPLETENESS_AUDIT
Date: 2026-04-04

Required commands audited:
- `/project`
- `/review`
- `/deep-run`
- `/artifacts`
- `/diagnose`
- `/doctor`
- `/replay`
- `/diff`
- `/profile`

## Status by command
- `/project`: Implemented as LocalJSX command (`src/commands/project/project.tsx`), surfaces manuscripts/projects/profile/model state.
- `/review`: Implemented as prompt command (`src/commands/review.ts`) with required tool sequence guidance and profile propagation.
- `/deep-run`: Implemented as prompt command (`src/commands/deep-run.ts`) with staged tool flow guidance and profile/mode injection.
- `/artifacts`: Implemented as LocalJSX command (`src/commands/artifacts/artifacts.tsx`), scans run directories and summarizes `run_summary`.
- `/diagnose`: Implemented as LocalJSX command (`src/commands/diagnose/diagnose.tsx`), surfaces backend/profile/gemma readiness.
- `/doctor`: Implemented as LocalJSX command (`src/commands/doctor/doctor.tsx`), broader readiness + recommended next actions.
- `/replay`: Implemented as prompt command (`src/commands/replay.ts`) directing `replay_run` usage.
- `/diff`: Implemented as prompt command (`src/commands/diff_review.ts`) directing `diff_run` usage.
- `/profile`: Implemented as LocalJSX command (`src/commands/profile/profile.tsx`) with numbered and alias selection and Gemma guidance.

## Gaps
- `/review`, `/deep-run`, `/replay`, `/diff` are prompt-orchestrated rather than direct deterministic implementations.
- Full interactive execution validation is constrained by Bun runtime absence in this environment.

## Conclusion
- Command set is present and wired.
- Determinism/robustness is strongest for LocalJSX commands; prompt commands depend more on model behavior.
