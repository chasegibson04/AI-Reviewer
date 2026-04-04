# ARTIFACT_AND_VALIDATION_AUDIT
Date: 2026-04-04

## Artifact set status
Bridge render currently writes:
- `source_mode.json`
- `section_map.json`
- `manuscript_comment_manifest.json`
- `manuscript_suggested_changes_manifest.json`
- `support_ingest_report.json`
- `support_usage_ledger.json`
- `assertion_ledger.json`
- `claim_verification_summary.json`
- `citation_verification_ledger.json`
- `format_compliance_report.json`
- `terminology_definition_report.json`
- `coherence_transition_report.json`
- `figure_table_reference_report.json`
- `routing_trace.json`
- `tool_event_log.jsonl`
- `network_event_log.jsonl`
- `run_summary.json`
- `session_transcript.md`

## Validation status
`validate_outputs` checks:
- required artifact presence
- JSON/JSONL parse validity
- front-matter violation scan on suggested-change targets
- remote network event detection (non-localhost hosts)

## Meaningfulness assessment
- Artifact presence and consistency are good.
- Content quality is moderate: more specific than prior state, but still largely heuristic.
- Rendered outputs are currently JSON/MD oriented; native DOCX mutation remains partial/out-of-scope in this phase.

## Evidence run
- Latest matrix: `test_outputs/overnight/20260404_000459/`
- Quality summary: `.../quality_report.md`
- Validation reports exist per run under each profile directory.
