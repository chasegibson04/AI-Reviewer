# Self-Containment Limitations

This folder is designed to run as independently as possible, but a few external dependencies still exist by design:

1. System/runtime dependencies
- Node.js 20+
- Bun (for build path)
- Python 3.10+
- Ollama service (`http://localhost:11434`) for local model execution

2. Optional parser enhancement
- If `ai_reviewer` is installed in the Python environment, the bridge can use it for richer ingest parsing.
- If unavailable, bridge fallback parsers are used (DOCX XML extraction / heuristic PDF text extraction).

3. OpenClaude upstream assumptions
- Some upstream command modules remain in `src/` and may require broader OpenClaude environment for full parity.
- The manuscript command surface documented in this folder is the validated path.

4. Windows validation scope in this environment
- Launcher scripts are implemented and syntax-validated.
- Full native interactive Windows execution was not run in this macOS environment.
