# Model Selection Guide

## Default Policy

- Balanced reviewer: `gemma3:27b`
- Deep reviewer: `llama3.3:70b-instruct-q4_K_M` (if installed)
- Repair fallback: `mistral-small3.1:24b`, `qwen2.5:7b-instruct`
- Embedding default: `mxbai-embed-large:latest`
- Embedding fallback: `nomic-embed-text-v2-moe:latest`

## Choosing For Task

- Fast first-pass screening:
  - profile: `quick`
  - model: smaller/medium local chat model
- Production review memo:
  - profile: `balanced`
  - model: `gemma3:27b`
- Deep technical critique:
  - profile: `deep` or `methods`
  - model: `llama3.3:70b-instruct-q4_K_M`
- Formatting rescue:
  - repair model: `mistral-small3.1:24b` or `qwen2.5:7b-instruct`

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
