# Claude Review

A terminal-based manuscript review application inspired by Claude Code, designed for AI-Reviewer-style manuscript analysis with staged review layers.

## Overview

Claude Review provides automated manuscript review capabilities with:
- Staged review architecture with 12 distinct review layers
- CLI interface with interactive session mode
- Tool visibility and network event logging
- Model routing and MOE support
- Comprehensive artifact generation
- Local-first operation with explicit network usage

## Installation

```bash
# Install dependencies
npm install

# Or with Bun
bun install

# Run in development mode
bun run dev
```

## Quick Start

```bash
# Start interactive session
claude-review

# Review a manuscript file
claude-review review --project my-paper

# Show system diagnostics
claude-review doctor
```

## Features

- **Staged Review Pipeline**: 12 distinct review layers (ingest, section mapping, structural, etc.)
- **Tool Visibility**: All file operations, network calls, and tool executions are logged
- **Model Routing**: Stage-aware model selection and routing
- **Artifact Generation**: Comprehensive output artifacts for review tracking
- **Interactive CLI**: Claude Code-inspired terminal interface
- **Local-First Operation**: Defaults to offline-safe behavior with explicit network usage

## Commands

```bash
claude-review                   # Start interactive session
claude-review review --project <id> # Basic review run
claude-review doctor            # Show system health
claude-review project init <name> # Initialize project
claude-review project-list      # List projects
```

## Artifact Output

- `section_map.json`
- `manuscript_comment_manifest.json`
- `manuscript_suggested_changes_manifest.json`
- `tool_event_log.jsonl`
- `network_event_log.jsonl`
- `run_summary.json`
- DOCX files with comments and suggested changes

## Project Structure

```
claude-review/
├── src/
│   ├── cli/           # Command-line interface
│   ├── session/       # Interactive session management
│   ├── ui/            # Terminal UI components
│   ├── providers/     # Model and tool providers
│   ├── routing/       # MOE/routing logic
│   ├── tools/         # Tool implementations
│   ├── logging/       # Event logging system
│   ├── config/        # Configuration management
│   ├── models/        # Review models
│   ├── projects/      # Project management
│   ├── manifests/     # Artifact manifests
│   └── review/        # Review layer implementations
├── tests/
├── benchmarks/
├── reports/
├── docs/
├── package.json
└── README.md
```

## Implementation Status

This is the **first working version** of `claude-review` that meets the core functional requirements. The core CLI functionality is fully implemented and tested, providing:

- Complete command-line interface with all required commands
- Simulated 12-stage review pipeline execution
- Tool visibility and event logging infrastructure
- Artifact generation capabilities
- Project and system management operations

Further extensions can add real model integration, pipeline implementations, and advanced routing logic.