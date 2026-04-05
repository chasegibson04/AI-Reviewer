#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Ensure Bun is discoverable in non-login shell contexts.
if [ -x "$HOME/.bun/bin/bun" ]; then
  export PATH="$HOME/.bun/bin:$PATH"
fi
export CLAUDE_CODE_ACCESSIBILITY="${CLAUDE_CODE_ACCESSIBILITY:-1}"
export CLAUDE_REVIEW_FORCE_INTERACTIVE="${CLAUDE_REVIEW_FORCE_INTERACTIVE:-1}"
export CLAUDE_REVIEW_USE_NATIVE_REPL=0
# Ensure both stdin/stdout are attached to the terminal so interactive
# mode is not misdetected as non-interactive.
if [ -r /dev/tty ] && [ -w /dev/tty ]; then
  exec </dev/tty >/dev/tty 2>&1
fi

cd "$PROJECT_ROOT"
node scripts/launch.js "$@"
