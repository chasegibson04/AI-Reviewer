# llama.cpp Backend Integration

`claude-review` supports `llama.cpp` as an optional local inference backend. This allows for high-performance, local-only manuscript review without dependency on external services or the Ollama daemon.

## Overview
The `llama.cpp` integration uses the `llama-server` executable, which provides an OpenAI-compatible API. `claude-review` communicates with this server via the `LlamaCppProvider`.

## Capabilities
- **Local-First:** Runs entirely on your machine.
- **OpenAI Compatible:** Supports standard chat completion routes.
- **Streaming:** Real-time token streaming in interactive mode.
- **Customizable:** Easily swap models by pointing to different GGUF files.

## Setup
1. **Install llama.cpp:** Use `scripts/install_llama_cpp_turboquant.sh` to clone and build (requires `cmake` and a C++ compiler).
2. **Download a Model:** Obtain a GGUF model (e.g., Qwen2.5-Coder-7B-Instruct-GGUF).
3. **Run the Server:** Use `scripts/run_llama_cpp_server.sh --model <path_to_gguf>`.
4. **Configure claude-review:** Set `LLAMA_CPP_BASE_URL=http://localhost:8080/v1` in your `.env`.

## Diagnostics
Run `claude-review doctor --runtime` to check:
- If `llama-server` is in your PATH or `vendor/` directory.
- Reachability of the configured endpoint.
- OpenAI compatibility of the backend.

## Benchmarking
Use the `llama_cpp_standard` profile to compare performance against Ollama or remote providers.
```bash
claude-review benchmark --target miniaturization_d2b --profile llama_cpp_standard
```
