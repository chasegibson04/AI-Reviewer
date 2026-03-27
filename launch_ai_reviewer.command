#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="$SCRIPT_DIR/launchers/launch_ai_reviewer.sh"

if [ ! -f "$TARGET" ]; then
  echo "ERROR: launcher script not found: $TARGET"
  if [ "${AI_REVIEWER_NO_PAUSE:-}" = "" ]; then
    echo ""
    read -r -p "Press Enter to close this window..." _
  fi
  exit 1
fi

set +e
/bin/bash "$TARGET"
RC=$?
set -e

if [ "${AI_REVIEWER_NO_PAUSE:-}" = "" ]; then
  echo ""
  read -r -p "Press Enter to close this window..." _
fi
exit "$RC"
