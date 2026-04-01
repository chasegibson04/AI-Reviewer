#!/bin/bash
cd "$(dirname "$0")"
echo "--- Starting Claude Review Interactive Session ---"
npx tsx src/index.ts
