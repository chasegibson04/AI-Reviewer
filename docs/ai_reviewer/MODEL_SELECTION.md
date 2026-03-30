# Model Selection Guide

## 1. Repo Defaults vs Local Overrides

Repository defaults from `config/defaults.yaml`:
- balanced review: `mistral-small3.2:latest`
- deep review: `phi4-reasoning:latest`
- embedding default: `bge-m3:latest`
- embedding fallback: `nomic-embed-text-v2-moe:latest`
- repair fallback: `qwen2.5:7b-instruct`, `mistral-small3.2:latest`
- deep-run routing mode: `default`

Important distinction:
- `config/local.yaml` and env overrides may route stronger models in practice
- use run artifacts and benchmark reports to describe what actually ran on a specific machine

## 2. Deep-Run Routing Modes

Configured by:
- `deep_run_routing.mode`
- `AI_REVIEWER_DEEP_RUN_ROUTING_MODE`

Supported modes:
- `default`
- `max_quality`

### `default`

Intent:
- keep structural work cheap
- use strong critique models when available
- keep reconciliation on repair-capable models

Typical pattern:
- `structural_triage`: `phi4-mini:latest` or `qwen3:4b`
- digest/evidence/style: balanced-capable local chat model
- critique-heavy stages: strongest available review model, often `llama3.3:70b-instruct-q4_K_M` when installed
- `reconciliation`: repair-capable model such as `qwen2.5:7b-instruct`
- `final_arbitration`: strongest available critique model

### `max_quality`

Intent:
- spend more latency/RAM on digest, evidence, line-edit, and style stages
- keep strongest large model on critique and arbitration stages
- avoid repair-class models for reconciliation unless forced by availability

Validated policy:
- `structural_triage`: `phi4-mini:latest` or `qwen3:4b`
- digest/evidence/context: prefer `gemma3:27b`, then `mistral-small3.1:24b`, then balanced fallback
- high-level/hostile/methods/final arbitration: strongest available critique model
- line edits/style alignment: strong editor-capable chat model
- reconciliation: strong editor/review model rather than repair-class fallback
- the strongest critique/arbitration stages now receive explicit claim-verification, citation-linkage, support-ingest, and compliance summaries

## 3. Benchmark Interpretation

Validated stage-7 result:
- max-quality improved style/edit surfacing
- max-quality did not yet improve final reconciliation quality consistently

Use `max_quality` when:
- local RAM budget is large
- you want stronger edit/style passes
- you accept slower runs

Do not claim `max_quality` is universally better until reconciliation/final arbitration quality improves.

## 4. Safety Rules

- embedding models are never routed into deep-run chat stages
- multimodal models are not routed into text-only deep-run stages
- Mac ARM fallback is explicit when a 70B lane is unavailable

Mac ARM fallback examples:
- `qwen3:32b`
- `qwen3:14b`
- `gemma3:27b`
- `mistral-small3.1:24b`
- `phi4-reasoning:latest`

## 5. Practical Selection Advice

- fast screening:
  - `quick` profile
  - smaller local chat model
- standard review:
  - `balanced` profile
  - repo default or local balanced override
- deep critique:
  - `deep` or `methods` profile
  - strong reasoning model
- rigorous run with large local RAM:
  - `deep-run`
  - `deep_run_routing.mode: max_quality`
  - benchmark first, then keep only if artifact quality improves for your workload

## 6. Validation Commands

```powershell
python scripts\run_stage7_max_quality_benchmark.py
Get-Content audits\stage7_benchmark\summary.json
```
