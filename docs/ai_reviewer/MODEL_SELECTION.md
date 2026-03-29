# Model Selection Guide

## Default Policy

- Balanced reviewer: `mistral-small3.2:latest`
- Deep reviewer: `phi4-reasoning:latest`
- Repair fallback: `qwen2.5:7b-instruct`, `mistral-small3.2:latest`
- Embedding default: `bge-m3:latest`
- Embedding fallback: `nomic-embed-text-v2-moe:latest`

Deep-run stage routing (when installed):
- critique-heavy stages may prefer `llama3.3:70b-instruct-q4_K_M`
- context/style stages prefer `mistral-small3.2:latest`
- reconciliation/repair prefer `qwen2.5:7b-instruct`

## Choosing For Task

- Fast first-pass screening:
  - profile: `quick`
  - model: smaller/medium local chat model
- Production review memo:
  - profile: `balanced`
  - model: `mistral-small3.2:latest`
- Deep technical critique:
  - profile: `deep` or `methods`
  - model: `phi4-reasoning:latest`
- Formatting rescue:
  - repair model: `qwen2.5:7b-instruct` or `mistral-small3.2:latest`

## How To Evaluate Models Locally

1. `ai-reviewer test-models`
2. `ai-reviewer benchmark --models <comma-separated-list>`
3. Prefer models with:
   - high structured pass rate
   - low repair dependence
   - high completeness score
   - acceptable latency

## Interpreting Benchmark Tags

- `best default`: strong balance of quality and reliability
- `best quality`: high completeness and stable formatting
- `best speed`: fastest usable option
- `use only for repair`: avoid as primary reviewer
- `avoid for primary review`: unstable formatting or weak completeness
