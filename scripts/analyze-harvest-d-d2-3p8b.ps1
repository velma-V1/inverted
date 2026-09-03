param(
  [string]$SmallDir = "harvest-d-runs\D2-SMALLA-SEED-V2-20260902-225456",
  [string]$Mid3BDir = "harvest-d-runs\D2-3B-QWEN-GAIN-20260903-050959",
  [string]$Mid3P8BDir = "harvest-d-runs\D2-3P8B-RESIDUAL-20260903-051241",
  [string]$QwenDir = "harvest-d-runs\D2-QWEN-SEED-V2-20260903-044741"
)

$ErrorActionPreference = "Stop"

function Load-Trials([string]$dir) {
  $path = Join-Path $dir "trials.jsonl"
  if (-not (Test-Path $path)) { throw "Missing trials file: $path" }
  return @(Get-Content $path | ForEach-Object { $_ | ConvertFrom-Json })
}

$small = Load-Trials $SmallDir
$mid3 = Load-Trials $Mid3BDir
$mid38 = Load-Trials $Mid3P8BDir
$qwen = Load-Trials $QwenDir

$rows = foreach ($m in $mid38) {
  $s = $small | Where-Object case_id -eq $m.case_id | Select-Object -First 1
  $m3 = $mid3 | Where-Object case_id -eq $m.case_id | Select-Object -First 1
  $q = $qwen | Where-Object case_id -eq $m.case_id | Select-Object -First 1

  [pscustomobject]@{
    Case       = $m.case_id
    Family     = $m.family
    Difficulty = $m.difficulty
    Small1_5B  = [bool]$s.semantic_success
    Mid3B      = [bool]$m3.semantic_success
    Mid3P8B    = [bool]$m.semantic_success
    Qwen9B     = [bool]$q.semantic_success
    Mid38Disp  = [bool]$m.disposition_correct
    Mid38Ans   = [bool]$m.answer_correct
    Result     = if ($m.semantic_success) { "BOUNDARY_AT_OR_BELOW_3P8B" } elseif ($q.semantic_success) { "RESIDUAL_3P8B_TO_9B" } else { "UNRESOLVED" }
  }
}

$rows | Sort-Object Family,Difficulty | Format-Table -AutoSize

Write-Host ""
Write-Host "=== D2 3.8B BOUNDARY SUMMARY ==="
$rows | Group-Object Result | Sort-Object Name | ForEach-Object {
  [pscustomobject]@{ Name = $_.Name; Count = $_.Count }
} | Format-Table -AutoSize

Write-Host ""
Write-Host "Residual 3.8B->9B cases:"
$rows | Where-Object Result -eq "RESIDUAL_3P8B_TO_9B" | Select-Object Case,Family,Difficulty,Mid38Disp,Mid38Ans | Format-Table -AutoSize
