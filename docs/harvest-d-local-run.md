# Harvest D Local Runbook

## 1. Model-free readiness

Normal CI and preflight must remain model-free:

```bash
python -m pytest -q tests/test_harvest_d_core.py tests/test_harvest_d_analysis.py tests/test_harvest_d_execution.py tests/test_harvest_d_campaign.py
python -m inverted.harvest_d.cli --config configs/harvest-d.json --output harvest-d-dry-run --dry-run
```

The dry run must emit `00-HARVEST-D-MASTER-INDEX.json`, provenance, readiness, kernel/transaction fault matrices, capability/promotion placeholders, and `SHA256SUMS.csv` with `real_model_calls = 0`.

## 2. Freeze a real local model artifact

Before any D2–D6 inference record:

- exact Ollama model ID;
- quantization;
- model digest/artifact hash where available;
- runtime/Ollama version;
- context limit/configuration;
- system template;
- tool/output schema;
- generation settings;
- hardware/runtime configuration.

Qwen production anchor is expected to be the exact deployed Qwen3.5 9B artifact, not an unspecified model family name.

## 3. Case files

Real case sets are JSONL. Hidden oracle data is stored with the case but never included by `HarvestCase.model_prompt()`.

Example:

```json
{"case_id":"f1-sem-001","family":"F1","capability":"semantic","difficulty":1,"prompt":"Return exactly: ok","expected_disposition":"EXECUTE","oracle":{"kind":"TEXT_EQUALS","expected":"ok"}}
```

Oracle kinds implemented by the harness:

- `TEXT_EQUALS`
- `TEXT_CONTAINS`
- `JSON_EQUALS`

Purpose-built semantic oracles should be preferred over text oracles for consequential real cases.

## 4. Explicit local Ollama execution

No real model call occurs through the normal Harvest D CLI. Real local execution is explicit:

```bash
python -m inverted.harvest_d.local_run \
  --cases path/to/cases.jsonl \
  --output path/to/output \
  --model qwen3.5:9b-q8_0 \
  --max-calls 20 \
  --route QWEN_STANDARD
```

The runner performs exactly one physical inference action per selected case. It contains no hidden retry loop. Call-budget exhaustion raises before another model call is made.

Artifacts include:

- `trials.jsonl`
- `prompts.jsonl`
- `responses.jsonl`
- `model_calls.jsonl`
- `tokens.csv`
- `latency.csv`
- `00-HARVEST-D-LOCAL-RUN.json`
- `SHA256SUMS.csv`

## 5. Matched arms and adaptive boundary work

For D2–D5 use the Python API:

- `CallBudget`
- `ExperimentArm`
- `MatchedExperimentRunner`
- `BoundaryPlanner`
- `ModelTrialRunner`

`MatchedExperimentRunner` executes each case once per arm and never retries. `BoundaryPlanner` starts at the middle difficulty and concentrates untested cases around the observed success/failure transition.

Model choice, system prompt/scaffold, route, and `SystemInvolvement` vector are independent fields. Do not encode recovery choice inside the model identity or route label.

## 6. D6/D6B promotion rule

Qwen Explorer output is never directly promoted. A candidate knowledge object must progress:

`OBSERVED -> HYPOTHESIZED -> CAUSALLY_VERIFIED -> NEIGHBOR_GENERALIZED -> FRESH_GENERALIZED -> REGRESSION_SAFE -> PROMOTED`

Causal verification requires a same-state targeted intervention to outperform its sham. Hard-invariant violation suspends the object. Automatic knowledge may change routing/scaffold/evidence/context/decomposition/recovery recommendations, verified skills, failure signatures, and deterministic guards; it may not expand execution authority.

## 7. Frozen ceilings

`configs/harvest-d.json` defines ceilings, not quotas:

- D0 0
- D1 0
- D2 70
- D3 110
- D4 60
- D5 50
- D6 70
- D6B 30
- D7 0

Stop earlier when a sequential decision closes the question. Do not increase a ceiling without reopening the frozen design.
