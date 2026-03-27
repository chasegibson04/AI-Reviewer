param(
    [string]$ProjectA = "20260325163524_test-existingphactorpaper",
    [string]$ProjectB = "20260327051312_miniaturization_d2b",
    [string]$Profile = "balanced"
)

$ErrorActionPreference = "Stop"

Write-Host "Running concurrent reviews for $ProjectA and $ProjectB with profile '$Profile'"
$jobA = Start-Job -ScriptBlock { param($p,$prof) python -m ai_reviewer.cli review --project $p --profile $prof } -ArgumentList $ProjectA, $Profile
$jobB = Start-Job -ScriptBlock { param($p,$prof) python -m ai_reviewer.cli review --project $p --profile $prof } -ArgumentList $ProjectB, $Profile

Wait-Job $jobA,$jobB | Out-Null
Write-Host "Job A state:" (Get-Job $jobA).State
Write-Host "Job B state:" (Get-Job $jobB).State
Receive-Job $jobA | Out-Host
Receive-Job $jobB | Out-Host
Remove-Job $jobA,$jobB

Write-Host "Testing same-project collision on $ProjectA"
$jobC = Start-Job -ScriptBlock { param($p,$prof) python -m ai_reviewer.cli review --project $p --profile $prof } -ArgumentList $ProjectA, $Profile
Start-Sleep -Seconds 2
$jobD = Start-Job -ScriptBlock { param($p,$prof) python -m ai_reviewer.cli review --project $p --profile $prof } -ArgumentList $ProjectA, $Profile

Wait-Job $jobC,$jobD | Out-Null
Write-Host "Job C state:" (Get-Job $jobC).State
Write-Host "Job D state:" (Get-Job $jobD).State
Receive-Job $jobC | Out-Host
Receive-Job $jobD | Out-Host
Remove-Job $jobC,$jobD
