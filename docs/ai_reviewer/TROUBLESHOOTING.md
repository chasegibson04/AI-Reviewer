# Troubleshooting

## 1. Ollama Not Reachable

```powershell
python -m ai_reviewer.cli diagnose
```

Actions:
1. run `ollama serve`
2. verify `http://127.0.0.1:11434/api/version`
3. rerun `diagnose`

## 2. Required Model Missing

Actions:
1. `ai-reviewer list-models`
2. pull the missing model
3. if deep-run routing expects a stronger model, either install it or accept selector fallback

## 3. Structured Output / Repair Warnings

Inspect:
- `raw_model_response.txt`
- `repaired_model_response.txt`
- `warnings.json`
- deep-run stage artifacts when relevant

Reality check:
- passing repair does not mean the final output is high quality
- stage 9 validation showed final synthesis is still a weak point when reconciliation/arbitration schema output is incomplete

## 4. Run Completed But Output Looks Weak

Open artifacts instead of trusting the success banner:
- `review_report.md` or `final_deep_review_report.md`
- `manuscript_comment_manifest.json`
- `manuscript_suggested_changes_manifest.json`
- `commented_docx_validation.json`
- `suggested_changes_validation.json`
- `section_map.json`

## 5. Native DOCX Re-review Looks Like A No-Op

Check:
- `source_mode.json`
- `commented_docx_validation.json`
- `suggested_changes_validation.json`

Red flags:
- `meaningful_new_review_state=false`
- `silent_noop_suspected=true`

Current expected behavior:
- preserve prior comments/suggestion blocks
- strip visible suggestion blocks from analysis text
- add new review state when warranted

## 6. Strict-Offline Conflicts

If strict offline is enabled, non-local Ollama URLs are rejected.

Actions:
1. set `defaults.ollama_base_url: http://127.0.0.1:11434`
2. keep `defaults.strict_offline: true`

## 7. Citation Fetch Needs To Be Tested

Use an explicit override:

```powershell
python -m ai_reviewer.cli review <manuscript> --project <id> --profile balanced
```

Then inspect `artifacts/citation_fetch_report.json` and confirm:
- no raw manuscript text
- no long excerpts
- metadata-only query policy

## 8. Figure Review Is Adding Noise

Current validated result on the approved PDFs:
- figure review is text-only
- it tends to add caption-parsing warnings more than useful critique

Recommendation:
- keep figure review OFF by default until a stronger path exists

## 9. Context-Pack Not Applied In Deep-Run

Check:
- `context_pack_used.json`
- `stage_10b_compliance_check.json`

Context-pack is optional and deterministic.
It is useful when it adds concrete policy checks, but it should not replace manuscript-first review.

## 10. Final Validation Before Release

Run:

```powershell
python -m pytest -q
Get-Content audits\TESTING_PROCEDURE.md
Get-Content audits\stage9_validation_report.md
```
