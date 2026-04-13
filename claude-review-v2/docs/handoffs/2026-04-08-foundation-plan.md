# Claude Review V2 Foundation Handoff

Working root: `/Users/chasegibson/Library/CloudStorage/Dropbox-UniversityofMichigan/Chase Gibson/AI-Reviewer/claude-review-v2`

Boundary:
- Code changes in this run were limited to `claude-review-v2`.
- Real validation/examples used only:
  - `20260325163524_test-existingphactorpaper`
  - `20260327051312_miniaturization_d2b`
- Forbidden projects were not inspected.

## Architectural Diagnosis
The current shell/bridge architecture is viable, but the remaining quality bottleneck is not the launcher or Gemma reachability. It is the evidence pipeline:
1. support-paper identity and cache records exist, but manuscript/reference extraction quality still controls whether those cached papers are actually reused;
2. citation verification runs sentence-by-sentence, but its usefulness rises or falls with reference-section splitting and support-to-reference matching;
3. artifact evaluation exists, but it still needs to be driven by refreshed approved-project outputs after parser fixes.

The highest-leverage foundation work is therefore:
1. reference-section extraction correctness
2. support-paper identity / manuscript-variant exclusion
3. support-to-reference matching traceability
4. artifact-first evaluation over approved-project outputs

## Proven vs Unproven
Proven in code/tests/probes:
- parser foundation for decorated reference headings and same-line parenthetical reference blocks
- support-cache schema and local `.runtime/support_ingest_cache` persistence
- support cache reuse/invalidation behavior (existing approved artifact plus targeted cache validation artifact)
- concise visible comments with richer hidden metadata separation

Not yet proven end-to-end after the latest parser fix:
- refreshed approved-project deep-run artifacts showing improved `used_sources`
- refreshed approved-project citation ledgers showing new `support_match_basis` / `source_resolution` behavior
- artifact-evaluator output on a post-fix validation root

This distinction matters. The current state is a sound foundation, not a completed end-to-end validation.

## Audit Table For Remaining Scope (Items 2-10)
| Item | Status | Evidence | Next step |
| --- | --- | --- | --- |
| 2. Sentence-level citation verification | PARTIAL | Implemented in `review_mcp_server.py`; approved-project artifacts exist; direct PDF probe now shows 26 references after parser fix | rerun approved-project artifact validation with refreshed outputs and inspect support hits/noise |
| 3. Structured support-paper ingest cache | PARTIAL | `.runtime/support_ingest_cache` exists; reuse/invalidation previously proven; `matching_hints` schema added in this run | refresh caches on approved-project runs and inspect `used_sources` / `support_match_basis` |
| 4. Artifact-first evaluation suite | PARTIAL | `tests/approved_project_artifact_evaluator.py` added; validation harness exists | run evaluator on refreshed approved-project validation root |
| 5. Concise visible comments + rich hidden metadata | DONE correctly | manifests/metadata separation already present | keep validating against citation-comment noise after refreshed runs |
| 6. Stage-level degraded-mode reporting | DONE correctly | routing trace, run summary, doctor/diagnose already expose requested/effective/fallback | no foundation change needed |
| 7. Long-context evaluation tasks | MISSING | no approved-project long-context stress artifacts yet | add after artifact evaluator is stable |
| 8. Standardized tool protocol for review stages | PARTIAL | bridge tool surface exists, but review flow is still monolithic | defer until evidence pipeline is stable |
| 9. Comment-response mode for existing reviewer comments | MISSING | no real implementation path found | safe follow-on task after evidence pipeline/evaluation |
| 10. Benchmark harness for real review workflows | PARTIAL | current benchmarking is not full artifact-producing workflow benchmarking | extend from approved-project artifact evaluator, not from throughput-only tooling |

## What Changed In This Run
### Core bridge changes
File: `src/bridge/python/review_mcp_server.py`
- strengthened `_references_split(...)` so PDF text with decorated headings like `■ REFERENCES` no longer splits early on inline body mentions of the word `references`
- improved `_extract_reference_entries(...)` so parenthetical numbered references are preferred when they yield the real reference list, and same-line `(21) ... (22) ...` blocks split correctly
- added richer support-ingest matching hints (`support_ingest_v2`) and matching score/basis tracing
- added `_is_manuscript_variant(...)` and now exclude manuscript-clone artifacts from support-paper discovery

### Tests/evaluation added or updated
Files:
- `tests/test_citation_reference_parsing.py`
- `tests/test_support_reference_linking.py`
- `tests/approved_project_artifact_evaluator.py`
- `tests/allowed_project_deep_validation.py`

New regression coverage includes:
- decorated PDF reference-heading split
- same-line numbered reference block parsing
- title extraction skipping boilerplate
- support-to-reference matching using `matching_hints`
- manuscript-variant exclusion for managed manuscript copies

## Direct Validation Results From This Run
Approved project used: `20260325163524_test-existingphactorpaper`

### Reference extraction probe
Command path: direct import of `review_mcp_server.py` against the approved manuscript PDF.
Result:
- parse engine: `pdftotext-cli-fallback`
- reference count: `26`
- previously observed behavior on this PDF path was `2` bogus reference entries

### Support matching probe
Using the approved project manuscript plus cached support docs:
- `ref 7` score `6.1` basis `['title:9', 'author:1', 'year']`
- `ref 10` score `5.2` basis `['title:6', 'year']`
- `ref 11` score `4.0` basis `['title:6']`
- `ref 12` score `5.2` basis `['title:8', 'year']`
- `ref 20` score `4.0` basis `['title:6']`

This means the cache is now linkable to real cited sources on the approved manuscript path, not just populated in isolation.

Additional inspectable artifact from this audit follow-up:
- `test_outputs/foundation_validation/20260408/citation_foundation_probe_heuristic.json`
  - confirms current parser/reference schema on the approved manuscript
  - confirms structured support-ingest report output
  - confirms sentence-level citation ledger sample is inspectable
  - does **not** prove final model-backed end-to-end citation quality

## Ordered To-Do List
1. Refresh approved-project deep-validation artifacts using the current bridge code.
   - Why first: every downstream quality judgment depends on updated artifacts reflecting the parser/support-discovery fixes.
   - Files: `tests/allowed_project_deep_validation.py`, `src/bridge/python/review_mcp_server.py`
   - Acceptance: fresh validation root with both approved projects and no forbidden-project paths.

2. Run the artifact evaluator on the refreshed validation root.
   - Why second: this converts fresh artifacts into a concrete gap report for comments, citation usefulness, cache usage, and degraded-mode honesty.
   - Files: `tests/approved_project_artifact_evaluator.py`
   - Acceptance: `artifact_evaluation.json` and `.md` written under the refreshed validation root.

3. Inspect refreshed citation ledgers for actual local-source reuse.
   - Why third: the parser fix should materially improve `reference_count`, `mention_count`, and `used_sources`; this now needs proof in artifacts, not just probes.
   - Files/artifacts: `citation_verification_ledger.json`, `support_usage_ledger.json`, `support_ingest_cache_index.json`
   - Acceptance: at least some local support-source matches in approved-project artifacts, with `support_match_basis` present.

4. Tighten remaining false-positive support matches.
   - Why fourth: after rerun, inspect whether any support matches are clearly wrong and adjust scoring thresholds/negative signals.
   - Files: `src/bridge/python/review_mcp_server.py`
   - Acceptance: support matches are specific and avoid manuscript self-matches or obvious title-collision matches.

5. Extend artifact evaluator into the real workflow benchmark harness.
   - Why fifth: benchmark work should build on artifact truth, not on generic throughput tests.
   - Files: likely `tests/approved_project_artifact_evaluator.py`, `src/tools/BenchmarkProjectTool/BenchmarkProjectTool.ts` or a new approved-project-only harness
   - Acceptance: reproducible artifact-producing benchmark summary across MOE and Gemma runs.

6. Implement comment-response mode for existing reviewer comments.
   - Why later: it depends on already-clean comment manifests and evidence traces but does not unblock ingest/citation correctness.
   - Files likely: review bridge + render/manifest paths
   - Acceptance: separate response manifest with concise proposed responses/fixes.

7. Add long-context evaluation tasks.
   - Why last: it is useful only after the evidence pipeline and benchmark harness are trustworthy.
   - Acceptance: approved-project stress artifacts showing whether longer context materially improves citation/support behavior.

## Dependency Map
- Reference split correctness -> reference extraction -> citation mention mapping -> support-to-reference linking -> citation comment quality
- Support cache schema/matching hints -> support-to-reference linking -> local-source reuse metrics -> artifact evaluator usefulness
- Refreshed approved-project validation -> artifact evaluator -> benchmark harness decisions
- Visible comment compaction is already stable and should not be redesigned before artifact refresh proves any remaining noise
- Comment-response mode depends on stable manifests and evidence traces, not vice versa
- Long-context evaluation depends on a trusted artifact/evaluator baseline

## Recommended Do-First Set For A Cheaper Follow-On Model
1. Rerun `tests/allowed_project_deep_validation.py` from `claude-review-v2`.
2. Run `tests/approved_project_artifact_evaluator.py` on the new validation root.
3. Inspect:
   - `citation_verification_ledger.json`
   - `support_usage_ledger.json`
   - `support_ingest_cache_index.json`
   - `manuscript_comment_manifest.json`
4. If `used_sources` is still too low, tune `_score_support_reference_match(...)` with artifact-backed negative/positive signals rather than new broad heuristics.
5. Only after that, extend benchmark/comment-response/long-context tasks.

## Baton-Pass Decision
Yes: a cheaper follow-on model can take over now.

Why:
- the next work is execution-heavy and artifact-inspection-heavy, not architecture-selection-heavy
- the main remaining uncertainty is empirical: refreshed approved-project artifacts after the parser/support-discovery fixes

The cheaper model should **not** redesign architecture first. It should:
1. rerun approved-project validation
2. evaluate the new artifacts
3. tighten support matching only if the refreshed artifacts still show weak local-source reuse
4. defer benchmark/comment-response/long-context work until that rerun is analyzed

## Commands Already Run In This Max-Reasoning Foundation Pass
- `python -m py_compile src/bridge/python/review_mcp_server.py tests/test_citation_reference_parsing.py`
- `python -m pytest -q tests/test_citation_reference_parsing.py tests/test_support_reference_linking.py`
- direct approved-project PDF parse probe via inline Python against `review_mcp_server.py`
- direct approved-project support-match probe via inline Python against `review_mcp_server.py`

## Practical Notes
- A previous long-running full validation process was killed after the parser changed, because it had been launched on stale bridge code.
- Do not trust old `20260408_001318` partial outputs for post-fix citation metrics.
- Rerun validation before making broader downstream decisions.
