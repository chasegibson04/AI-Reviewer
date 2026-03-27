#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
if [ ! -f "$REPO_ROOT/pyproject.toml" ]; then
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi
TARGET="$REPO_ROOT/launchers/launch_ai_reviewer.sh"

if [ ! -f "$TARGET" ]; then
  echo "ERROR: launcher script not found: $TARGET"
  echo "This launcher must live inside the AI-Reviewer repo."
  if [ "${AI_REVIEWER_NO_PAUSE:-}" = "" ]; then
    echo ""
    read -r -p "Press Enter to close this window..." _
  fi
  exit 1
fi

set +e
/bin/bash "$TARGET" "$REPO_ROOT"
RC=$?
set -e

if [ "${AI_REVIEWER_NO_PAUSE:-}" = "" ]; then
  echo ""
  read -r -p "Press Enter to close this window..." _
fi
exit "$RC"
