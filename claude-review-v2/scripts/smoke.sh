#!/bin/bash

echo "Running smoke test for claude-review-v2..."
bun run build || exit 1
node dist/cli.mjs --help || exit 1
echo "Smoke test passed."
