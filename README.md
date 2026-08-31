# Inverted AI Architecture Benchmark

A falsifiable experiment for one narrow architectural question:

> Does a non-AI system that generates/executes candidate outcomes, with an AI model used primarily as auditor, outperform the same model used as the direct executor?

The benchmark does **not** claim universal proof. A decisive campaign returns `SUPPORTED`, `REFUTED`, or `INCONCLUSIVE` for the preregistered tested hypothesis. Smoke/development runs return `NON-DECISIVE` by design.

## Why this benchmark is hard to fake

Six matched arms run on identical seeded tasks:

- `A_DIRECT` — AI chooses actions.
- `B_DIRECT_CHECKED` — AI chooses actions plus deterministic structural and public-requirement verification/retry.
- `C_SYSTEM` — non-AI candidate executor alone.
- `D_INVERTED` — non-AI candidate executor plus AI semantic auditor.
- `E_RANDOM_AUDITOR` — retry/control arm proving that rejection opportunities alone are not the effect.
- `F_ORACLE_AUDITOR` — hidden-oracle upper bound.

Three task families (`state`, `policy`, `reconciliation`) scale through four complexity levels. The system executor is swept through 20%, 40%, 60%, 80%, and 95% configured candidate quality using seeded fault injection. Both direct and system paths receive the same public structured requirements; hidden oracle labels and criticality are never exposed to either architecture. Ground truth is deterministic program logic and is never an LLM judge.

## Telemetry

Every run captures all normalized data the serving backend exposes. Missing provider data remains `null`; it is never fabricated.

Per model call this includes identifiers, role, model/provider, timestamps, wall latency, TTFT when available, input/output/total/reasoning/cache token classes, tokens/sec, provider evaluation/load durations, HTTP/error/timeout data, retry fields, finish reason, parser status, inference parameters, known cost, raw usage/provider telemetry, and optionally full prompt/response content.

Per candidate it records the task/candidate IDs, attempt, configured quality, injected fault category, oracle truth, auditor/control decision, rejection history, and audit rationale. Per trial it records success, requirement accuracy, catastrophic failure, tokens, calls, latency, audit confusion counts, terminal status, and failure taxonomy.

The final report prints the aggregate analysis and, with `include_raw_rows: true`, the full trial, candidate/audit, and model-call ledgers. Raw JSONL/CSV is retained for independent recomputation.

Each run writes:

```text
events.jsonl
model_calls.jsonl
trials.csv
trials.jsonl
failures.csv
summary.json
summary.csv
report.txt
config.json
provenance.json
```

## Install

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

## Smoke test

The smoke test uses a deterministic mock model only to prove benchmark plumbing and CI. It can never produce a scientific yes/no verdict.

```bash
python -m inverted.cli --config configs/smoke.yaml
```

## Decisive local/Ollama campaign

Pick **three genuinely different model families/capacity tiers**. Do not use three quantizations of the same model as the three-model diversity requirement.

Example shell setup:

```bash
export INVERTED_MODEL_1='your-first-ollama-model'
export INVERTED_MODEL_2='your-second-ollama-model'
export INVERTED_MODEL_3='your-third-ollama-model'
python -m inverted.cli --config configs/decisive.yaml
```

PowerShell:

```powershell
$env:INVERTED_MODEL_1='your-first-ollama-model'
$env:INVERTED_MODEL_2='your-second-ollama-model'
$env:INVERTED_MODEL_3='your-third-ollama-model'
python -m inverted.cli --config configs/decisive.yaml
```

`configs/decisive.yaml` runs 3 families × 4 complexity levels × 5 executor-quality levels × 5 seeds × 3 epochs × 6 arms × 3 model configurations = **16,200 trials**, before candidate retries. This is deliberately much larger than the smoke benchmark.

## OpenAI-compatible endpoints

Replace a model entry with:

```yaml
- provider: openai-compatible
  model: your-model
  base_url: https://provider.example
  api_key_env: PROVIDER_API_KEY
  temperature: 0.0
  max_tokens: 1024
  timeout_s: 180
  # Optional only if prices are known and you want cost accounting:
  # price_per_m_input: 0.0
  # price_per_m_output: 0.0
```

API-key values are read from the environment and are never written to benchmark artifacts.

## Verdict

`SUPPORTED` requires all preregistered support gates, including ≥10 percentage-point D-vs-A advantage, 95% bootstrap CI excluding zero, wins in at least 2/3 families, superiority to the random-auditor control, no ≥2-point catastrophic-failure increase, positive equal-token-budget advantage, cross-model/seed reproduction, and no decisive loss to the checked conventional baseline.

`REFUTED` requires adequately powered evidence for a preregistered failure condition. Anything between those standards is `INCONCLUSIVE` rather than being forced into a yes/no claim.

See `docs/superpowers/specs/2026-08-30-inverted-architecture-benchmark-design.md` for the complete preregistration.
