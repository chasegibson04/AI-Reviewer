#!/bin/bash
cd "$(dirname "$0")/.."
echo "--- Running Claude Review Benchmark (Dry Run) ---"
npx tsx src/index.ts benchmark --target miniaturization_d2b
