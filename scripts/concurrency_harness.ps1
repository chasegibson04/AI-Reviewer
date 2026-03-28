param(
    [string]$ProjectA = "20260325163524_test-existingphactorpaper",
    [string]$ProjectB = "20260327051312_miniaturization_d2b",
    [string]$Profile = "balanced",
    [string]$PythonExe = ".\\.venv\\Scripts\\python.exe",
    [string]$ConfigPath = "",
    [string]$RepoRoot = (Get-Location).Path,
    [int]$TimeoutSeconds = 600,
    [string]$Model = "gemma3:12b",
    [bool]$DisableEmbeddings = $true,
    [bool]$ForceStaleLocks = $true
)

$ErrorActionPreference = "Stop"

if ($ConfigPath) {
    Write-Host "ConfigPath was provided but review CLI does not support --config. Ignoring: $ConfigPath"
}
$cfgArgs = @()
$pythonResolved = (Resolve-Path $PythonExe).Path
$modelArgs = if ($Model) { @("--model", $Model) } else { @() }
$embedArgs = if ($DisableEmbeddings) { @("--disable-embeddings") } else { @() }

if ($ForceStaleLocks) {
    $lockPaths = @(
        (Join-Path -Path (Join-Path -Path "projects" -ChildPath $ProjectA) -ChildPath ".locks\\project.lock"),
        (Join-Path -Path (Join-Path -Path "projects" -ChildPath $ProjectB) -ChildPath ".locks\\project.lock")
    )
    foreach ($lp in $lockPaths) {
        if (Test-Path $lp) {
            (Get-Item $lp).LastWriteTime = (Get-Date).AddHours(-6)
            Write-Host "Marked lock as stale: $lp"
        }
    }
}
Write-Host "Running concurrent reviews for $ProjectA and $ProjectB with profile '$Profile'"
$jobA = Start-Job -ScriptBlock { param($root,$py,$p,$prof,$cfg,$model,$embed) Set-Location $root; & $py -m ai_reviewer.cli review --project $p --profile $prof @model @embed @cfg } -ArgumentList $RepoRoot, $pythonResolved, $ProjectA, $Profile, (,$cfgArgs), (,$modelArgs), (,$embedArgs)
$jobB = Start-Job -ScriptBlock { param($root,$py,$p,$prof,$cfg,$model,$embed) Set-Location $root; & $py -m ai_reviewer.cli review --project $p --profile $prof @model @embed @cfg } -ArgumentList $RepoRoot, $pythonResolved, $ProjectB, $Profile, (,$cfgArgs), (,$modelArgs), (,$embedArgs)

$waitResult = Wait-Job $jobA,$jobB -Timeout $TimeoutSeconds
if (-not $waitResult) {
    Write-Host "Timeout waiting for Job A/B. Stopping jobs."
    Stop-Job $jobA,$jobB -ErrorAction SilentlyContinue
}
Write-Host "Job A state:" $jobA.State
Write-Host "Job B state:" $jobB.State
$ErrorActionPreference = "Continue"
Receive-Job $jobA -Keep | Out-Host
Receive-Job $jobB -Keep | Out-Host
if ($jobA.ChildJobs[0].Error.Count -gt 0) { Write-Host "Job A errors:"; $jobA.ChildJobs[0].Error | Out-Host }
if ($jobB.ChildJobs[0].Error.Count -gt 0) { Write-Host "Job B errors:"; $jobB.ChildJobs[0].Error | Out-Host }
Remove-Job $jobA,$jobB
$ErrorActionPreference = "Stop"

Write-Host "Testing same-project collision on $ProjectA"
$jobC = Start-Job -ScriptBlock { param($root,$py,$p,$prof,$cfg,$model,$embed) Set-Location $root; & $py -m ai_reviewer.cli review --project $p --profile $prof @model @embed @cfg } -ArgumentList $RepoRoot, $pythonResolved, $ProjectA, $Profile, (,$cfgArgs), (,$modelArgs), (,$embedArgs)
Start-Sleep -Seconds 2
$jobD = Start-Job -ScriptBlock { param($root,$py,$p,$prof,$cfg,$model,$embed) Set-Location $root; & $py -m ai_reviewer.cli review --project $p --profile $prof @model @embed @cfg } -ArgumentList $RepoRoot, $pythonResolved, $ProjectA, $Profile, (,$cfgArgs), (,$modelArgs), (,$embedArgs)

$waitResult = Wait-Job $jobC,$jobD -Timeout $TimeoutSeconds
if (-not $waitResult) {
    Write-Host "Timeout waiting for Job C/D. Stopping jobs."
    Stop-Job $jobC,$jobD -ErrorAction SilentlyContinue
}
Write-Host "Job C state:" $jobC.State
Write-Host "Job D state:" $jobD.State
$ErrorActionPreference = "Continue"
Receive-Job $jobC -Keep | Out-Host
Receive-Job $jobD -Keep | Out-Host
if ($jobC.ChildJobs[0].Error.Count -gt 0) { Write-Host "Job C errors:"; $jobC.ChildJobs[0].Error | Out-Host }
if ($jobD.ChildJobs[0].Error.Count -gt 0) { Write-Host "Job D errors:"; $jobD.ChildJobs[0].Error | Out-Host }
Remove-Job $jobC,$jobD
$ErrorActionPreference = "Stop"

Write-Host "Testing aborted run + stale lock recovery on $ProjectA"
$jobE = Start-Job -ScriptBlock { param($root,$py,$p,$prof,$cfg,$model,$embed) Set-Location $root; & $py -m ai_reviewer.cli review --project $p --profile $prof @model @embed @cfg } -ArgumentList $RepoRoot, $pythonResolved, $ProjectA, $Profile, (,$cfgArgs), (,$modelArgs), (,$embedArgs)
Start-Sleep -Seconds 5
Stop-Job $jobE
Remove-Job $jobE

$lockPath = Join-Path -Path (Join-Path -Path "projects" -ChildPath $ProjectA) -ChildPath ".locks\\project.lock"
if (Test-Path $lockPath) {
  $old = (Get-Date).AddHours(-5)
  (Get-Item $lockPath).LastWriteTime = $old
  Write-Host "Marked lock as stale: $lockPath"
}

$jobF = Start-Job -ScriptBlock { param($root,$py,$p,$prof,$cfg,$model,$embed) Set-Location $root; & $py -m ai_reviewer.cli review --project $p --profile $prof @model @embed @cfg } -ArgumentList $RepoRoot, $pythonResolved, $ProjectA, $Profile, (,$cfgArgs), (,$modelArgs), (,$embedArgs)
$waitResult = Wait-Job $jobF -Timeout $TimeoutSeconds
if (-not $waitResult) {
    Write-Host "Timeout waiting for Job F. Stopping job."
    Stop-Job $jobF -ErrorAction SilentlyContinue
}
Write-Host "Job F state:" $jobF.State
$ErrorActionPreference = "Continue"
Receive-Job $jobF -Keep | Out-Host
if ($jobF.ChildJobs[0].Error.Count -gt 0) { Write-Host "Job F errors:"; $jobF.ChildJobs[0].Error | Out-Host }
Remove-Job $jobF
$ErrorActionPreference = "Stop"
