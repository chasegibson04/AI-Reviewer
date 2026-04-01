# Claude Review

An advanced terminal-based manuscript review and editing system, inspired by the Claude Code UX and powered by the AI-Reviewer intelligence layer.

## Overview
`claude-review` is a self-contained subproject within the AI-Reviewer repository. It aims to provide a high-performance, agentic workstation for scientific manuscript review. It combines the streaming, tool-visibility, and interactive feel of Claude Code with the deep, staged, and rigorous review workflows developed for AI-Reviewer.

## Critical Write Boundary
- This project is a self-contained build.
- **DO NOT** modify, rename, delete, or reformat any file outside `claude-review/`.
- All creation, editing, and deletion of files must occur **ONLY** inside `claude-review/`.
- Do not create symlinks pointing outside this directory.
- This project does not yet "wire into" the main AI-Reviewer app.

## Architecture Summary
`claude-review` follows a layered, stage-based orchestration model:
1.  **Terminal UX:** A React-inspired (via Ink or similar) or raw-terminal streaming interface that shows tool execution and assistant reasoning in real-time.
2.  **Orchestration Layer:** A TypeScript/Node.js core that manages the review pipeline, project state, and artifact generation.
3.  **Provider/Routing Layer:** A smart-router system that selects the optimal LLM (local or remote) for each specific review stage (e.g., cheap models for indexing, reasoning-heavy models for hostile critique).
4.  **Review Engine:** A series of specialized stages that ingest, normalize, analyze, and annotate manuscripts (DOCX, PDF surrogates).

## Planned Commands
- `review login`: Configure providers and profiles.
- `review init`: Initialize a new review project from a manuscript.
- `review doctor`: Run environment and reachability diagnostics.
- `review run`: Execute the full multi-stage review pipeline.
- `review interactive`: Enter an interactive session to explore a manuscript and its review artifacts.
- `review chat`: Chat with the review agent about the manuscript.
- `review export`: Generate final commented DOCX and suggested-changes manifests.

## Current Status: Discovery & Architecture
The project is currently in the **Discovery & Architecture** phase. We are mapping the AI-Reviewer pipeline to a modern, terminal-first agentic architecture.

---
*This project is part of the AI-Reviewer ecosystem but operates as an independent, self-contained module.*
