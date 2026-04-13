#!/bin/bash
set -euo pipefail

echo "Running fallback smoke for claude-review-v2 (no Bun required)..."

python3 -m py_compile src/bridge/python/review_mcp_server.py
if [ -x ".venv/bin/python" ]; then
  .venv/bin/python -m pytest -q tests/test_mcp_review.py tests/test_launch_boundary.py tests/test_gemma_diagnose_path.py
else
  python3 -m pytest -q tests/test_mcp_review.py tests/test_launch_boundary.py tests/test_gemma_diagnose_path.py
fi
node --test --experimental-strip-types src/utils/providerRecommendation.test.ts src/utils/providerProfile.test.ts
node --test --experimental-strip-types src/utils/model/reviewProfiles.test.ts src/commands/review/runParameters.test.ts
bash scripts/doctor_runtime.sh

echo "Fallback smoke passed."
