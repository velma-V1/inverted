param(
  [string]$Model = "qwen3:14b",
  [string]$Python = "py -3.14"
)

$ErrorActionPreference = "Stop"

$caseFile = "cases\harvest_d\d2-neither-9b-v1.jsonl"
$systemPrompt = "configs\harvest-d-d2-system.txt"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$out = "harvest-d-runs\D2-14B-NEITHER-$stamp"
New-Item -ItemType Directory -Force -Path $out | Out-Null

$modelRow = ollama list | Select-String -SimpleMatch $Model
if (-not $modelRow) { throw "Required model not found in ollama list: $Model" }

$gitHead = (git rev-parse HEAD).Trim()
$ollamaVersion = (ollama --version | Out-String).Trim()
$modelListRow = ($modelRow | Out-String).Trim()
$showText = (ollama show $Model | Out-String).Trim()

$prov = [ordered]@{
  stage = "D2"
  pool = "development"
  role = "RESIDUAL_CEILING_14B"
  model = $Model
  git_head = $gitHead
  ollama_version = $ollamaVersion
  ollama_list_row = $modelListRow
  case_file = $caseFile
  system_prompt_file = $systemPrompt
  route = "QWEN_STANDARD"
  transition_class = "NEITHER_1P5B_9B"
  max_calls = 8
  retries = 0
  measurement_version = "HARVEST-D-LAYERED-SCORING-v2"
  generation_options = [ordered]@{ temperature = 0.0; seed = 20260902; num_ctx = 4096 }
  started_at = (Get-Date).ToString("o")
}
$prov | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 "$out\D2-PROVENANCE.json"
$showText | Set-Content -Encoding utf8 "$out\OLLAMA-SHOW.txt"

$invoke = "$Python -m inverted.harvest_d.local_run --cases `"$caseFile`" --output `"$out`" --model `"$Model`" --max-calls 8 --route QWEN_STANDARD --system-prompt-file `"$systemPrompt`""
Invoke-Expression $invoke

$ps = (ollama ps | Out-String).Trim()
$ps | Set-Content -Encoding utf8 "$out\OLLAMA-PS-AFTER.txt"

$summary = Get-Content "$out\00-HARVEST-D-LOCAL-RUN.json" -Raw | ConvertFrom-Json
$prov.completed_at = (Get-Date).ToString("o")
$prov.semantic_successes = $summary.semantic_successes
$prov.contract_successes = $summary.contract_successes
$prov.disposition_correct = $summary.disposition_correct
$prov.answer_correct = $summary.answer_correct
$prov.schema_valid = $summary.schema_valid
$prov.format_valid = $summary.format_valid
$prov.calls = $summary.calls
$prov.ollama_ps_after = $ps
$prov | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 "$out\D2-PROVENANCE.json"

Get-ChildItem $out -File | Where-Object { $_.Name -ne "D2-SHA256SUMS.csv" } | Sort-Object Name | ForEach-Object {
  $h = Get-FileHash $_.FullName -Algorithm SHA256
  [pscustomobject]@{ file = $_.Name; sha256 = $h.Hash.ToLowerInvariant() }
} | Export-Csv "$out\D2-SHA256SUMS.csv" -NoTypeInformation

Write-Host ""
Write-Host "=== HARVEST D D2 14B NEITHER COMPLETE ==="
Write-Host "Output: $out"
Get-Content "$out\00-HARVEST-D-LOCAL-RUN.json"
Write-Host ""
Write-Host "Processor allocation after run:"
Get-Content "$out\OLLAMA-PS-AFTER.txt"
