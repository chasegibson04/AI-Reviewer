# AI-Reviewer Architecture

`ai_reviewer` is organized around local-first review reliability:

- `config.py`: layered YAML configuration (`defaults.yaml`, optional local overrides)
- `models/ollama_provider.py`: direct Ollama HTTP API abstraction (health/list/chat/embed)
- `models/selector.py`: default model role selection and chat/embed classification
- `models/diagnostics.py`: environment and safety checks
- `ingest/loaders.py`: PDF/TXT/MD/DOCX/TEX parsing with warnings and provenance
- `ingest/chunking.py`: chunking for long-context review
- `ingest/retrieval.py`: optional embedding retrieval via local models
- `review/schema.py`: strict Pydantic review and compare schemas
- `review/repair.py`: structured output recovery pipeline
- `review/engine.py`: review/compare orchestration and artifact persistence
- `review/deep_run.py`: staged deep-run orchestration, optional context-pack ingestion, and deterministic compliance checks
- `review/render.py`: Markdown/text report rendering and review bundle writing
- `benchmarks/runner.py`: review-style benchmark and format compliance reporting
- `cli.py`: Typer + Rich terminal UX with guided launch and diagnostics

Safety defaults:
- strict offline mode (`localhost` Ollama only)
- raw response retention on by default
- strict schema validation on by default
- explicit warnings for degraded parsing/repair fallback

Legacy isolation:
- `ai_scientist/` is preserved and not invoked by default launchers or `ai-reviewer` commands.
