# `claude-review` Benchmark Plan

This document defines the benchmarking strategy, targets, and KPIs for the `claude-review` system.

## 1. Approved Benchmark Targets
Benchmarks must only be run on the following approved projects:

- **Target A:** `20260325163524_test-existingphactorpaper`
    - **Focus:** Broad review coverage, citation accuracy, and general flow.
- **Target B:** `20260327051312_miniaturization_d2b`
    - **Focus:** Complex methodological verification and claim alignment.

## 2. Prohibited Targets (Blacklist)
- **NEVER** use the following projects for benchmarking or testing:
    - **horseshoe crab** project (`20260324221200_horseshoe_crabs1`)
    - **pampa** project (`pampa-j-chemed`)
- This is a strict project-level constraint.

## 3. Key Performance Indicators (KPIs)

| KPI | Description | Target |
| :--- | :--- | :--- |
| **Artifact Completeness** | Presence and validity of all 12 pipeline stage JSON artifacts. | 100% |
| **Comment Coverage** | Number of actionable, grounded comments per 1,000 words. | > 5 |
| **Abstain Rate** | Percentage of ambiguous issues flagged for human review (rather than guessed). | > 10% |
| **Front-Matter Safety** | Number of cases where front-matter was incorrectly edited. | 0 |
| **Figure-Ref Detection** | Percentage of correctly identified and verified figure references. | > 90% |
| **Undefined-Term Detection** | Number of first-use acronyms or technical terms correctly flagged. | > 80% |
| **Latency** | End-to-end time for the full pipeline run. | < 15 mins (on `balanced` profile) |
| **Output Validation Health** | Number of structural or schema errors in final JSON manifests. | 0 |

## 4. Benchmark Command (`review benchmark`)
The `benchmark` command must:
1.  **Initialize:** Create a fresh project for the target.
2.  **Run:** Execute the full 12-stage review pipeline.
3.  **Evaluate:** Run the `Stage12 Validation Pass` and calculate KPIs.
4.  **Report:** Generate a structured `reports/benchmark_<timestamp>.json` and a human-readable Markdown summary.

## 5. Comparison Baseline
Benchmarks should compare the current `claude-review` output against the existing `AI-Reviewer` deep run results to ensure no regression in quality or coverage.
- Compare latency (end-to-end vs. individual stages).
- Compare artifact density (number of grounded comments).
- Compare validation scores from the `Stage12` pass.
