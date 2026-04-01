#!/bin/bash
cd "$(dirname "$0")/.."
echo "--- Running Claude Review Smoke Tests ---"
npx tsx tests/smoke.test.ts
