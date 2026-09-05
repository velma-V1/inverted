# INVERTED — Model Operating-Surface and System Capability Program

INVERTED is an evidence-driven program for making the **whole system and every model operating inside it materially more capable in practice than the same model raw**.

The current model-uplift objective is not one universal prompt and not “make the small model beat Qwen.” It is to discover each model's **model-specific operating surface**: what information/support it needs, how much, in what order, when, where, in what representation, under which task/failure/state conditions, and at what correctness/latency/token/compute tradeoff.

The eventual policy is conditional rather than static:

`Support = f(model, task, difficulty, failure/state, context pressure, resource target, evidence state)`

Discovery maps the high-performance Pareto frontier first. Compression toward minimum-equivalent support, smaller models, fewer tokens, or simpler machinery comes afterward and must prove what capability it preserves.

The repository began with a narrower falsifiable architecture benchmark asking whether a non-AI candidate executor plus AI auditor could outperform direct model execution. That benchmark and later Harvest/Test campaigns remain preserved evidence streams; they do not limit the current project objective.

Before designing new model-uplift inference, read [`docs/OPERATING_SURFACE_EVIDENCE_FRONTIER.md`](docs/OPERATING_SURFACE_EVIDENCE_FRONTIER.md) and its JSON companion so work starts from the strongest existing evidence.

## Permanent model operating rules

Before meaningful design, testing, analysis, or implementation work, AI models and agents must read and obey [`REPO_LAWS_AND_REGULATIONS.md`](REPO_LAWS_AND_REGULATIONS.md) first. It is the sole canonical repository lawbook.

Then read the explicit owner-approved six-law amendment in [`INVERTED_CONSTITUTION.md`](INVERTED_CONSTITUTION.md), followed by the compact operating summary in [`MODEL_OPERATING_RULES.md`](MODEL_OPERATING_RULES.md). Model-specific entry points are also provided in [`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md), and [`.github/copilot-instructions.md`](.github/copilot-instructions.md).

Two project-wide operating rules are mandatory:

> **Your requirements define the minimum. I am responsible for identifying higher-value options, missing experiments, better architecture, better telemetry, and failure modes you did not explicitly name.**

> **Do not merely satisfy the requested experiment. Ask what we will wish we had recorded six months later, and capture it now when it is cheap.**

The six-law amendment additionally requires project-first truth, highest verified capability with minimum necessary machinery, maximum valid decision value from experiments, upward ratcheting of both whole-system and model-in-system capability, decision-ready project memory, and research that terminates in the highest justified shipping tier.

Also enforce: **something has to prove it belongs.** Complexity and mechanisms must earn their place through evidence.

## Why this benchmark is hard to fake

Six matched arms run on identical seeded tasks:

- `A_DIRECT` — AI chooses actions.
- `B_DIRECT_CHECKED` — AI chooses actions plus deterministic structural and public-requirement verification/retry.
- `C_SYSTEM` — non-AI candidate executor alone.
- `D_INVERTED` — non-AI candidate executor plus AI semantic auditor.
- `E_RANDOM_AUDITOR` — retry/control arm proving that rejection opportunities alone are not the effect.
- `F_ORACLE_AUDITOR` — hidden-oracle upper bound.

Three task families (`state`, `policy`, `reconciliation`) scale through four complexity levels. The system executor is swept through 20%, 40%, 60%, 80%, and 95% configured candidate quality using seeded fault injection. Both direct and system paths receive the same public structured requirements; hidden oracle labels and criticality are never exposed to either architecture. Ground truth is deterministic program logic and is never an LLM judge.

Non-AI candidate generation is paired across auditor models: for the same task/quality/seed/epoch/attempt, different auditor models receive the same system-generated candidate sequence. Model identity cannot change that sequence.

## Efficient decisive execution plan

The scientific design still contains 180 independent task clusters, all three real models, all three task families, all four complexity levels, all five system-executor qualities, all seeds/epochs, and all six arms. The physical execution plan removes conditions that cannot change an arm:

- `A_DIRECT` and `B_DIRECT_CHECKED` run once per model/task because system-executor quality does not affect them.
- `C_SYSTEM`, `E_RANDOM_AUDITOR`, and `F_ORACLE_AUDITOR` run once per task/quality because they do not depend on model identity.
- `D_INVERTED` retains every model × task × quality condition.

The decisive campaign therefore executes **6,480 trial units**, not the old redundant 16,200-row rectangular schedule:

```text
A_DIRECT            540
B_DIRECT_CHECKED    540
C_SYSTEM            900
D_INVERTED         2700
E_RANDOM_AUDITOR    900
F_ORACLE_AUDITOR    900
TOTAL              6480
```

Statistics analytically reuse the quality-independent direct baseline across the D quality sweep, then cluster repeated model/quality effects by independent `task_id`. Removing redundant inference does not manufacture statistical power or change the primary D-vs-A estimand.

## Telemetry

Every run captures all normalized data the serving backend exposes. Missing provider data remains `null`; it is never fabricated.

Per model call this includes identifiers, role, model/provider, timestamps, wall latency, TTFT when available, input/output/total/reasoning/cache token classes, tokens/sec, provider evaluation/load durations, HTTP/error/timeout data, retry fields, finish reason, parser status, inference parameters, known cost, raw usage/provider telemetry, and optionally full prompt/response content.

Per candidate it records the task/candidate IDs, attempt, configured quality, injected fault category, oracle truth, auditor/control decision, rejection history, and audit rationale. Per trial it records success, requirement accuracy, catastrophic failure, tokens, calls, latency, audit confusion counts, terminal status, and failure taxonomy.

The final report prints the aggregate analysis and, with `include_raw_rows: true`, the full trial, candidate/audit, and model-call ledgers. Raw JSONL/CSV is retained for independent recomputation.

Each completed run writes exactly:

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

A resumable campaign may additionally maintain an append-only checkpoint JSONL while running. The checkpoint is recovery state, not part of the final ten-file evidence contract.

## Install

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

## GitHub cloud instrument validation

GitHub Actions validates everything that does not require the user's real local Ollama models. Core CI covers Linux and Windows plus Python 3.11, 3.12, and 3.14. A separate validation workflow runs deterministic known-answer cases, invariance/failure tests, and a 4,320-unit full-matrix mock stress campaign, then uploads an `inverted-validation-evidence` artifact.

All mock/cloud reports are explicitly labeled:

```text
INSTRUMENT VALIDATION — NOT ARCHITECTURE EVIDENCE
```

Synthetic results may validate the benchmark instrument, but they may never be used as evidence that the inverted architecture itself works.

## Smoke test

The smoke test uses a deterministic mock model only to prove benchmark plumbing and CI. It can never produce a scientific yes/no verdict.

```bash
python -m inverted.cli --config configs/smoke.yaml
```

## Decisive local/Ollama campaign

Pick **three genuinely different model families/capacity tiers**. Do not use three quantizations of the same model as the three-model diversity requirement.

Recommended first local set for this experiment:

```text
qwen3.5:9b-q8_0
gemma3:12b
devstral-small-2:24b
```

Manual PowerShell run with exact progress and crash recovery:

```powershell
$env:INVERTED_MODEL_1='qwen3.5:9b-q8_0'
$env:INVERTED_MODEL_2='gemma3:12b'
$env:INVERTED_MODEL_3='devstral-small-2:24b'

$RunId = "decisive-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
python -m inverted.cli `
  --config configs/decisive.yaml `
  --output-dir "$HOME\inverted-runs" `
  --run-id $RunId `
  --checkpoint "$HOME\inverted-runs\$RunId.checkpoint.jsonl" `
  --resume `
  --progress
```

Progress is exact plan progress, for example `PROGRESS 1000/6480 ...`; it is not an estimated timer.

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

`SUPPORTED` requires all preregistered support gates, including ≥10 percentage-point D-vs-A advantage, 95% clustered-bootstrap CI excluding zero, wins in at least 2/3 families, superiority to the random-auditor control, no ≥2-point catastrophic-failure increase, positive equal-token-budget advantage, cross-model/seed reproduction, and no decisive loss to the checked conventional baseline.

`REFUTED` requires adequately powered evidence for a preregistered failure condition. Anything between those standards is `INCONCLUSIVE` rather than being forced into a yes/no claim.

See `docs/superpowers/specs/2026-08-30-inverted-architecture-benchmark-design.md` and `docs/superpowers/specs/2026-08-31-hybrid-validation-and-local-handoff-design.md` for the preregistration and hybrid-validation design.
