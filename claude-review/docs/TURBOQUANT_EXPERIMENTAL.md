# TurboQuant Experimental Backend

`TurboQuant` is an **experimental** performance optimization backend for `claude-review`. It is a specialized fork of `llama.cpp` focused on KV-cache optimizations, particularly useful for long-context tasks like manuscript review.

## Status: EXPERIMENTAL
TurboQuant is not a required dependency and is not guaranteed to improve review quality. It is intended for users who want to push local performance on long-context scientific documents.

## Key Features
- **KV-Cache Optimization:** Turbo cache modes for reduced memory usage and faster processing of long documents.
- **Improved Throughput:** Designed for high-token-count workloads like full manuscript digestion.
- **OpenAI-Compatible Extension:** Exposes `turbo_cache` parameters via the `llama-server` API.

## When to Use TurboQuant
TurboQuant is best suited for:
- `Stage 3: Digestion` (Full manuscript + supporting literature).
- `Stage 6: Methods & Rigor` (Detailed analysis of methodological sections).
- `Stage 10: Arbitration` (Reconciling findings from multiple stages).

## How to Enable
1. **Build TurboQuant:** Run `scripts/install_llama_cpp_turboquant.sh` to fetch and build the specialized fork into `vendor/llama-cpp-turboquant/`.
2. **Start the Turbo Server:** Use `scripts/run_llama_cpp_turboquant_server.sh`.
3. **Use the Profile:** Run reviews or benchmarks with `--profile llama_cpp_turboquant`.

## Quality Guardrails
- `claude-review` **will not** silently substitute TurboQuant for other backends.
- If TurboQuant is configured but unavailable, the system will fall back to `llama_cpp_standard` with a visible warning and artifact log.
- TurboQuant is only recommended for specific, context-heavy stages in the `ReviewPipeline`.

## Benchmarking Comparison
The system includes a `benchmark_local_matrix` profile that compares:
- Ollama (Baseline)
- llama.cpp (Standard)
- llama.cpp (TurboQuant)

Check `reports/benchmark_<target>_matrix.json` for a detailed breakdown of timing, accuracy, and artifact completeness across these backends.
