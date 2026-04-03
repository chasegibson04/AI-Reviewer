# COMMAND_AND_TOOL_AUDIT
Date: 2026-04-03

## Command usability snapshot
- `/project`: active workspace/project/manuscript/profile summary with next actions.
- `/review`: prompt command with selected run profile/mode/model injected into execution instructions.
- `/deep-run`: staged deep-run prompt with selected run profile/mode/model injected.
- `/artifacts`: scans artifact directories and reports per-run summary when `run_summary.json` exists.
- `/diagnose`: backend/bridge/manuscript/project/profile/Gemma readiness report.
- `/doctor`: manuscript-domain doctor output with local model and profile readiness checks.
- `/replay`: prompt command guiding `replay_run` usage.
- `/diff`: prompt command guiding `diff_run` usage.
- `/profile`: guided numeric/alias selection flow and reset support.

## Review tools: shell-usable status
All required tools remain registered and bridge-callable through tool wrappers:
- inspect_project
- discover_manuscript
- parse_docx
- parse_pdf
- map_sections
- digest_manuscript
- analyze_terminology
- analyze_coherence
- analyze_methods
- analyze_figures_tables
- analyze_citations
- analyze_journal_format
- generate_line_edits
- arbitrate_review
- render_outputs
- validate_outputs
- replay_run
- diff_run
- benchmark_project

## Remaining caveats
- `/review`, `/deep-run`, `/replay`, `/diff` are still LLM-guided orchestration commands, not deterministic local command pipelines.
- Full CLI invocation smoke for these commands is blocked by missing Bun runtime in this environment.
