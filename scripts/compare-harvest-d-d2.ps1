param(
  [string]$SmallRun = "harvest-d-runs\D2-SMALLA-SEED-V2-20260902-225456",
  [string]$QwenRun = "harvest-d-runs\D2-QWEN-SEED-V2-20260903-044741"
)

$ErrorActionPreference = "Stop"

$smallPath = Join-Path $SmallRun "trials.jsonl"
$qwenPath = Join-Path $QwenRun "trials.jsonl"

if (-not (Test-Path $smallPath)) { throw "Missing SMALL_A trials: $smallPath" }
if (-not (Test-Path $qwenPath)) { throw "Missing QWEN trials: $qwenPath" }

$small = @(Get-Content $smallPath | ForEach-Object { $_ | ConvertFrom-Json })
$qwen = @(Get-Content $qwenPath | ForEach-Object { $_ | ConvertFrom-Json })
$qwenByCase = @{}
foreach ($row in $qwen) { $qwenByCase[$row.case_id] = $row }

$rows = @()
foreach ($a in $small) {
  if (-not $qwenByCase.ContainsKey($a.case_id)) { throw "QWEN run missing case: $($a.case_id)" }
  $b = $qwenByCase[$a.case_id]

  if ((-not $a.semantic_success) -and $b.semantic_success) {
    $result = "QWEN_GAIN"
  } elseif ($a.semantic_success -and (-not $b.semantic_success)) {
    $result = "SMALL_GAIN"
  } elseif ($a.semantic_success -and $b.semantic_success) {
    $result = "BOTH"
  } else {
    $result = "NEITHER"
  }

  $rows += [pscustomobject]@{
    Case = $a.case_id
    Family = $a.family
    Difficulty = $a.difficulty
    Small = [bool]$a.semantic_success
    Qwen = [bool]$b.semantic_success
    SmallDisp = [bool]$a.disposition_correct
    QwenDisp = [bool]$b.disposition_correct
    SmallAns = [bool]$a.answer_correct
    QwenAns = [bool]$b.answer_correct
    Result = $result
  }
}

$rows | Sort-Object Family, Difficulty | Format-Table -AutoSize

Write-Host ""
Write-Host "=== D2 TRANSITION SUMMARY ==="
$rows | Group-Object Result | Sort-Object Name | ForEach-Object {
  [pscustomobject]@{ Result = $_.Name; Cases = $_.Count }
} | Format-Table -AutoSize
