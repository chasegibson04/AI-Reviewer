#!/bin/bash
cd "$(dirname "$0")/.."
echo "--- Running llama.cpp Capability Check ---"
npx tsx src/index.ts doctor --runtime
