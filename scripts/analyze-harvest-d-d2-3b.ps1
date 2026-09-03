$ErrorActionPreference = "Stop"

$smallDir = Get-ChildItem .\harvest-d-runs -Directory -Filter 'D2-SMALLA-SEED-V2-*' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$qwenDir  = Get-ChildItem .\harvest-d-runs -Directory -Filter 'D2-QWEN-SEED-V2-*' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$midDir   = Get-ChildItem .\harvest-d-runs -Directory -Filter 'D2-3B-QWEN-GAIN-*' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $smallDir -or -not $qwenDir -or -not $midDir) { throw 'Required D2 run directories not found.' }

$small = @{}
Get-Content ($smallDir.FullName + '\trials.jsonl') | ForEach-Object { $r = $_ | ConvertFrom-Json; $small[$r.case_id] = $r }
$qwen = @{}
Get-Content ($qwenDir.FullName + '\trials.jsonl') | ForEach-Object { $r = $_ | ConvertFrom-Json; $qwen[$r.case_id] = $r }
$mid = @{}
Get-Content ($midDir.FullName + '\trials.jsonl') | ForEach-Object { $r = $_ | ConvertFrom-Json; $mid[$r.case_id] = $r }

$rows = foreach ($cid in ($mid.Keys | Sort-Object)) {
  $s=$small[$cid]; $m=$mid[$cid]; $q=$qwen[$cid]
  $class = if ($m.semantic_success) { 'BOUNDARY_AT_OR_BELOW_3B' } elseif ($q.semantic_success) { 'RESIDUAL_3B_TO_9B' } else { 'UNEXPECTED' }
  [pscustomobject]@{
    Case=$cid; Family=$m.family; Difficulty=$m.difficulty;
    Small1_5B=$s.semantic_success; Mid3B=$m.semantic_success; Qwen9B=$q.semantic_success;
    MidDisp=$m.disposition_correct; MidAns=$m.answer_correct; Class=$class
  }
}

$rows | Format-Table -AutoSize
Write-Host ""
Write-Host "=== D2 3B BOUNDARY SUMMARY ==="
$rows | Group-Object Class | Select-Object Name,Count | Format-Table -AutoSize
Write-Host ""
Write-Host "Residual 3B->9B cases:"
$rows | Where-Object Class -eq 'RESIDUAL_3B_TO_9B' | Select-Object Case,Family,Difficulty | Format-Table -AutoSize
