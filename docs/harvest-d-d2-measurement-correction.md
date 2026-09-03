# Harvest D D2 Measurement Correction

## Status

APPROVED MEASUREMENT CORRECTION. CONCEPTUAL HARVEST D SCOPE UNCHANGED.

The first real SMALL_A seed run, local output `harvest-d-runs/D2-SMALLA-SEED-20260902-224538`, produced 18 physical model calls and reported 0 semantic successes under the original exact-equality scorer.

That `0/18` value is **not admissible as a D2 capability-boundary estimate**.

It remains valid evidence for harness diagnosis and response-behavior observation.

## Root cause

The original scorer collapsed several distinct phenomena into one Boolean failure:

1. invalid strict output format, including fenced JSON;
2. schema/key mismatch, such as `route` instead of `answer`;
3. incorrect disposition;
4. semantically incorrect answer;
5. semantically correct answer expressed with equivalent surface wording;
6. prompts requiring private/internal answer tokens that were not exposed to the model.

The first run therefore mixed output-contract compliance with semantic capability.

The run also used Ollama defaults because generation options were not explicitly frozen in the request body.

## Corrected measurement contract

Starting with `HARVEST-D-LAYERED-SCORING-v2`, every response records independently:

- `parseable_json`
- `format_valid`
- `schema_valid`
- `disposition_correct`
- `answer_correct`
- `semantic_success` = disposition correct AND answer correct
- `contract_success` = strict format AND strict schema AND semantic success

A fenced JSON object can therefore be semantically correct while still failing the output contract.

A genuine wrong answer remains a semantic failure.

## Seed v2

`cases/harvest_d/d2-small-a-seed-v2.jsonl` preserves the same 18 developmental capability probes and hidden answers but removes private-vocabulary guessing from string-label cases by exposing a small allowed answer vocabulary in the prompt.

This does not expose which choice is correct.

The same v2 cases and scorer must be used for matched SMALL_A/Qwen comparisons.

## Generation freeze

Ollama requests now explicitly freeze:

- temperature: `0.0`
- seed: `20260902`
- context: `4096`

No Ollama structured-output/JSON-mode assist is enabled, because that would add an architecture variable to the raw-capability arm.

## Evidence disposition

Original v1 run:

- physical calls: VALID OBSERVATIONS
- raw responses: VALID
- token/latency evidence: VALID
- GPU processor-allocation observation: VALID
- exact 0/18 boundary claim: REJECTED
- use for confirmatory capability inference: FORBIDDEN
- use for harness diagnosis: ALLOWED

Corrected v2 remains a **development pool**. It may guide D2 boundary localization but may not serve as the untouched confirmatory/fresh-family pool.
