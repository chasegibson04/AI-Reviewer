param(
  [switch]$Doctor,
  [switch]$Diagnose
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
Set-Location $ProjectRoot

if ($Doctor) {
  Write-Host "Running Windows doctor checks for claude-review-v2..."
  $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
  if (-not $ollamaCmd) {
    Write-Error "Ollama CLI not found in PATH."
    exit 1
  }

  & ollama --version
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  try {
    $tags = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 3
    Write-Host "Ollama service is reachable."
    $models = @($tags.models | ForEach-Object { $_.name } | Where-Object { $_ -and $_.Trim().Length -gt 0 })
    if ($models.Count -eq 0) {
      Write-Warning "No local models found. Pull at least one model (for example: ollama pull gemma4:26b)."
    } else {
      Write-Host "Local models:"
      $models | ForEach-Object { Write-Host " - $_" }
    }
  } catch {
    Write-Error "Could not reach Ollama API at http://localhost:11434/api/tags."
    exit 1
  }

  Write-Host "Windows doctor checks passed."
  exit 0
}

if ($Diagnose) {
  Write-Host "Running Windows diagnose checks for claude-review-v2..."
  python -m py_compile src/bridge/python/review_mcp_server.py tests/test_mcp_review.py tests/test_gemma_diagnose_path.py tests/overnight_validation_runner.py
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  python -m pytest -q tests/test_mcp_review.py tests/test_launch_boundary.py tests/test_gemma_diagnose_path.py
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  node --test --experimental-strip-types src/utils/providerRecommendation.test.ts src/utils/providerProfile.test.ts
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  node --test --experimental-strip-types src/utils/model/reviewProfiles.test.ts src/commands/review/runParameters.test.ts
  exit $LASTEXITCODE
}

node scripts/launch.js @args
exit $LASTEXITCODE
