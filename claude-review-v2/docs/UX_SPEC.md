# User Experience Specification

The primary objective of `claude-review-v2` is to present the powerful AI-Reviewer manuscript analysis pipeline through an intuitive, interactive, and terminal-first interface directly inspired by OpenClaude (and Claude Code).

## Core Philosophy

- **Terminal-First & Agentic:** The application should feel like an AI assistant actively operating on a user's manuscript project. The interaction must be conversational, with the underlying complexity of the multi-stage review orchestrated behind the scenes.
- **Guided Onboarding:** Users should not encounter a bare prompt. Upon launch, the shell must intelligently assess the environment:
  - Detect installed local models (via Ollama).
  - Identify the active `projects/<project_id>` context.
  - Locate manuscript files (`materials/manuscript/`).
  - Proactively suggest next steps ("I found a manuscript in this project...", "You can start a quick review...").
- **Local-First Default:** The interaction should implicitly and explicitly prioritize local models. Remote network calls (e.g., OpenAI, Anthropic) are strictly opt-in and blocked by default.
- **Minimalist Aesthetic:** Avoid heavy, custom ASCII banners or over-branded "workstation" identities. The aesthetic should closely match the clean, streaming style of OpenClaude.

## Key Interaction Patterns

### The Session Loop

- **Input Prompt:** A concise `> ` or similar minimal indicator, ready for conversational input or slash commands.
- **Streaming Output:** The assistant's responses and reasoning should stream to the terminal in real-time.
- **Tool Execution Blocks:** When the agent invokes a review stage (e.g., "Analyzing methods for rigor..."), a distinct, visually separated block should indicate the tool's execution status (running, complete, failed) without overwhelming the chat history.

### Command Surface

Users interact with the system via natural language ("Review this manuscript for clarity") or through explicit slash commands for precise control:

- `/help` - Displays available commands and usage guidance.
- `/project` - Manages project context (init, import, list).
- `/review` - Initiates a standard review pass.
- `/deep-run` - Triggers the comprehensive, multi-stage AI-Reviewer pipeline.
- `/doctor` / `/diagnose` - Runs environment, model, and connectivity checks.
- `/profile` - Selects or configures the model routing profile (e.g., `balanced_local`, `deep_local`).
- `/artifacts` - Inspects the generated review files and manifests.
- `/replay` / `/diff` - Tools for examining previous runs or comparing drafts.

### Feedback and Diagnostics

- **Model Selection Visibility:** The active model profile (e.g., `mistral-small3.2:latest`) should be discreetly visible, perhaps in a status bar or as part of the initial greeting.
- **Clear Error Handling:** If a local model is unreachable or a manuscript is missing, the system should fail gracefully with actionable advice ("Ollama is not running. Start it with `ollama serve`.").
- **Run Summaries:** Upon completing a review or deep-run, provide a compact summary of the findings (e.g., "Found 12 issues: 3 severe, 9 moderate") and the paths to the generated artifacts. Do not dump the entire analysis into the terminal.

## Example Interaction

```
$ claude-review-v2
I found local Ollama and the 'balanced_local' profile.
I also found one active review project: 'project_alpha'.
The manuscript 'materials/manuscript/draft_v1.docx' is ready.

You can start a quick review, deep review, line-edit pass, or inspect artifacts.
Use /help to see all commands.

> /deep-run
Starting deep run on 'draft_v1.docx'...

[Tool: parse_docx] Ingesting manuscript text and structure... (Done)
[Tool: analyze_methods] Evaluating methodological rigor using phi4-reasoning...
...
```
