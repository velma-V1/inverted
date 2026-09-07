param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
$ErrorActionPreference = 'Stop'
python -m inverted.capability_ratchet.cli @Args
exit $LASTEXITCODE
