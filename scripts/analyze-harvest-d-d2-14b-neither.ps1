param(
  [string]$RunsRoot = "harvest-d-runs"
)

$ErrorActionPreference = "Stop"

$qwenRun = Get-ChildItem $RunsRoot -Directory -Filter "D2-QWEN-SEED-V2-*" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$midRun = Get-ChildItem $RunsRoot -Directory -Filter "D2-14B-NEITHER-*" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $qwenRun) { throw "No D2 Qwen 9B run found." }
if (-not $midRun) { throw "No D2 14B NEITHER run found." }

$qwen = Get-Content (Join-Path $qwenRun.FullName "trials.jsonl") | ForEach-Object { $_ | ConvertFrom-Json }
$mid = Get-Content (Join-Path $midRun.FullName "trials.jsonl") | ForEach-Object { $_ | ConvertFrom-Json }

$rows = foreach ($m in $mid) {
  $q = $qwen | Where-Object { $_.case_id -eq $m.case_id }
  if (-not $q) { throw "Missing Qwen row for $($m.case_id)" }
  $class = if ($m.semantic_success) { "14B_RECOVERY" } elseif ($m.answer_correct -and -not $m.disposition_correct) { "ANSWER_RIGHT_DISPOSITION_WRONG" } elseif (-not $m.answer_correct -and $m.disposition_correct) { "DISPOSITION_RIGHT_ANSWER_WRONG" } elseif ($m.answer_correct -and $m.disposition_correct) { "SEMANTIC_OTHER" } else { "BOTH_WRONG" }
  [pscustomobject]@{
    Case = $m.case_id
    Family = $m.family
    Difficulty = $m.difficulty
    Qwen9B = [bool]$q.semantic_success
    Qwen14B = [bool]$m.semantic_success
    Disp14B = [bool]$m.disposition_correct
    Ans14B = [bool]$m.answer_correct
    Class = $class
  }
}

$rows | Sort-Object Family,Difficulty | Format-Table -AutoSize
Write-Host ""
Write-Host "=== D2 14B RESIDUAL SUMMARY ==="
$rows | Group-Object Class | Sort-Object Name | Select-Object Name,Count | Format-Table -AutoSize
Write-Host ""
Write-Host "14B recovered cases:"
$rows | Where-Object { $_.Class -eq "14B_RECOVERY" } | Select-Object Case,Family,Difficulty | Format-Table -AutoSize
Write-Host ""
Write-Host "Persistent answer-right/disposition-wrong cases:"
$rows | Where-Object { $_.Class -eq "ANSWER_RIGHT_DISPOSITION_WRONG" } | Select-Object Case,Family,Difficulty | Format-Table -AutoSize
