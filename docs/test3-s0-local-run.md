# Test-3 Section-0 Local Run

Status: executable model-free instrument. Section 0 permits **zero new physical model calls** and does **not** authorize architecture claims or Tier-A inference.

## 1. Install and verify

```text
python -m pip install -e ".[test]"
python -m pytest -q
```

## 2. Instrument validation with partial evidence

This checks the zero-call CLI, artifact contract, source-integrity machinery, and forensic packet without pretending the scientific input set is complete.

```text
python -m inverted.test3_s0_cli build-manifest --output test3-s0-manifest.json --source test2-model-free test2_model_free PATH_TO_TEST2_MODEL_FREE
python -m inverted.test3_s0_cli validate-instrument --config configs/test3-s0.yaml --manifest test3-s0-manifest.json --output-dir test3-s0-instrument-validation
```

Expected verdict: `PARTIAL_INPUT_EVIDENCE` when Test-1 and Test-2 Tier-A evidence are not supplied.

## 3. Scientific S0 run

The scientific run requires three verified historical source classes:

- `test1`
- `test2_tier_a`
- `test2_model_free`

Each complete bundle must include a valid `SHA256SUMS.csv`. Manifest identity fields that exist (`bundle_sha256`, `git_sha`, `run_id`) must match the observed bundle. Missing or mismatched identity data blocks the run.

```text
python -m inverted.test3_s0_cli build-manifest --output test3-s0-manifest.json --source test1 test1 PATH_TO_TEST1 --source test2-tier-a test2_tier_a PATH_TO_TEST2_TIER_A --source test2-model-free test2_model_free PATH_TO_TEST2_MODEL_FREE
python -m inverted.test3_s0_cli run --config configs/test3-s0.yaml --manifest test3-s0-manifest.json --output-dir test3-s0-run
```

The Tier-A bundle above is **historical evidence input**. Section 0 still performs zero new model inference.

## Exit codes

- `0` — successful instrument validation or discovery run
- `2` — required source class missing
- `3` — source integrity or manifest identity failure
- `4` — normalization/instrumentation failure retained as evidence

## Evidence policy

S0 preserves malformed rows, unknown fields, raw-record hashes, field-level temporal provenance, source file hashes/sizes, raw source JSON metadata, comparison/effect/order tables, verifier results and disagreement, cache/cost/token/latency metadata, counterfactual decision traces, rare edge cases, integrity anomalies, and data-quality coverage. Missing cost fields remain missing; they are never imputed.

Primary forensic outputs include `COMPLETE-EVIDENCE.txt`, `SHA256SUMS.csv`, `source_integrity.csv`, `field_provenance.csv`, `comparison_evidence.csv`, `source_metadata.jsonl`, `validator_results.csv`, `instrumentation_anomalies.csv`, `edge_cases.csv`, and `data_quality.json`.
