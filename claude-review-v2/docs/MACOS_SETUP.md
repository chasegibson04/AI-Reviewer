# macOS Setup

This guide covers a reliable local setup for `claude-review-v2` on macOS.

## 1) Prerequisites

Required:

- Node.js 20+
- Python 3.10+
- Ollama installed and running locally

Recommended:

- Bun (for build/rebuild path)
- `pdftotext` (better PDF fallback extraction)

Quick checks:

```bash
node -v
python3 --version
ollama --version
```

## 2) Start Ollama

```bash
ollama serve
ollama list
```

Gemma validation (recommended for single-model mode):

```bash
ollama pull gemma4:26b
# optional
ollama pull gemma4:31b
```

## 3) Launch

From terminal:

```bash
cd claude-review-v2
./launchers/macos/claude-review-v2.sh
```

Finder path:

- double-click `launchers/macos/claude-review-v2.command`

## 4) Verify Launch Boundary

```bash
node scripts/launch.js --print-launch-plan
```

Expected (default):

- `launchTarget` is `line_repl`

## 5) Runtime Checks

```bash
bash scripts/doctor_runtime.sh
bash scripts/smoke_fallback.sh
```

In shell:

- run `/doctor`
- run `/diagnose`

## 6) Deep-Run Mode Verification

Inside interactive shell:

- run `/deep-run`
- verify prompt asks MOE vs Single-model Gemma 4
- choose `2` for Gemma mode
- inspect generated `run_summary.json` and `routing_trace.json`

## 7) Common macOS Notes

- Finder-launched shells may not inherit the same PATH as Terminal.
- The launcher prepends `$HOME/.bun/bin` when present.
- If Bun is unavailable and `dist` is stale/missing, use fallback checks and build manually.
