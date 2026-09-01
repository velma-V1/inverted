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

## Automatic 010 → inverted handoff on Windows

`scripts/wait-for-010-and-run-inverted.ps1` is intended for starting while the 010 live C/D experiment is still running. It:

1. observes a running Python process whose command line matches `alien` by default;
2. refuses to start inverted if it never observed 010;
3. waits for the match to disappear for three consecutive checks;
4. disables AC sleep, updates/installs the benchmark, checks Ollama and all three models;
5. runs the decisive campaign with checkpoint/resume/exact progress;
6. preserves a failed/interrupted run for resume;
7. verifies all ten final evidence files before printing `INVERTED BENCHMARK COMPLETE`.

After the repository containing this script is on `main`, the normal launch is:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\inverted\scripts\wait-for-010-and-run-inverted.ps1" -ProcessPattern "alien"
```

If the repo has not been cloned yet, clone/update it first; the handoff script itself will also clone the repository if its configured repo path is absent.

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

## Post-benchmark Qwen experiment candidates — planning notes only

These are **README-only planning candidates** for follow-on experiments after the real preregistered Inverted benchmark completes. They are not implemented, do not modify the current benchmark, and should not gain separate files or architecture references until we explicitly decide to build/test one.

Build order is intentional: **001 is first; 006 is last.** Each stage moves from cheap, reversible external structure toward expensive, invasive intervention.

### 001 — Minimal Relational Brain

**Hypothesis:** Qwen can improve from an extremely small adaptive substrate built from only `NODE + EDGE + STATE + TRANSITION + OUTCOME`.

**Architecture:** keep nodes, evidence-backed relationships, active state, transitions, and verified outcomes in a small SQLite store. Seed only a few relevant nodes for each task, spread activation over a hard-bounded number of edges, rank paths by relevance and evidence-backed utility, feed the smallest useful connected packet to Qwen, then update only relationships actually implicated in the verified result.

**Important rule:** do not use arbitrary permanent edge weights. Track successes/failures with conservative priors so one lucky event cannot dominate future behavior. Every durable relationship must retain provenance; weak paths become dormant rather than being destroyed.

**First comparison:** Qwen alone vs Qwen + Minimal Relational Brain. Measure task success, repeated failures, unseen transfer, wrong-path activation, token/latency cost, and edge-ablation impact.

### 002 — Portable Cognitive Workspace

**Hypothesis:** Qwen will handle long, interrupted, and evolving tasks more reliably if it carries a compact external working state through the entire task and promotes only verified improvements into reusable procedures.

**Architecture:** use a bounded `TASK_STATE` projection plus an append-only journal. The state contains goal, phase, plan, completed work, next action, constraints, known facts, unresolved questions, failed approaches, artifacts, and confidence. It explicitly does **not** store full chain-of-thought. Reusable candidate skills/patterns/edge cases/tools are promoted only after verification and replay.

**Important rule:** immutable journal + reconstructable mutable state. If the working state becomes corrupted, it can be rebuilt. Retrieval is strictly token-budgeted and failed approaches are preserved so Qwen does not loop.

**First comparison:** Qwen alone vs traveling state only vs traveling state + verified reusable procedures. Measure plan drift, repeated work, interruption recovery, cross-task reuse, retrieval precision, and token cost.

### 003 — Graph Memory Brain

**Hypothesis:** explicit relational retrieval can recover multi-hop dependencies, causes, fixes, conflicts, and superseded knowledge that flat retrieval misses.

**Architecture:** start with SQLite rather than a graph server. Candidate node types include task, failure, solution, skill, fact, tool, constraint, pattern, and outcome. Candidate relations include `CAUSES`, `FIXED_BY`, `FAILED_WITH`, `REQUIRES`, `CONFLICTS_WITH`, `APPLIES_TO`, `SUPERSEDES`, `SIMILAR_TO`, and `VALIDATED_BY`. Seed nodes through lexical/semantic retrieval, expand at most one or two hops, filter stale/weak edges, deduplicate, and return only a small ranked relational packet.

**Important rule:** the graph is never an unauditable truth store. Every durable node/edge has provenance and temporal validity. Conflicting claims can coexist until evidence resolves them. Traversal depth/fan-out are hard-capped.

**First comparison:** Qwen baseline vs flat memory with the same information budget vs graph retrieval. The graph only wins if structure itself improves held-out relational tasks.

### 004 — Hybrid Portable Brain

**Hypothesis:** if 001–003 each prove useful, their best components can be combined into a portable cognitive layer without sacrificing auditability or simplicity.

**Architecture:** canonical immutable evidence + working state/journal + reusable skills/patterns/tools + evidence-weighted relational memory + a derived/rebuildable graph/index. Working memory answers "what am I doing now?"; procedural memory answers "how has this been solved before?"; episodic memory answers "what happened?"; relational memory answers "what connects/causes/fixes/conflicts?"; evidence answers "why trust it?".

**Important rule:** the filesystem/evidence layer remains canonical. The graph and indexes are disposable derivatives. Retrieval compiles the smallest sufficient packet under a hard context budget, and every component is logged so it can be ablated.

**First comparison:** best single earlier component vs best two-component combination vs full hybrid, under matched stored-information and token budgets. Keep the simpler design if the hybrid does not add measurable marginal value.

### 005 — Live Codex Intervention

**Hypothesis:** a stronger model observing Qwen's streamed reasoning may rescue failures before completion often enough to outperform simpler post-hoc critique.

**Architecture:** stream Qwen/Ollama reasoning/output/telemetry into a ring buffer and recorder. Feed bounded chunks to a persistent Codex observer. Codex may either do nothing or trigger **one** intervention: preserve the exact partial trajectory, stop generation, inject a short bounded correction hint, and resume Qwen.

**Important rule:** Codex cannot answer the task or see a hidden answer key. Its intervention may only identify the suspected defect and provide a bounded hint. Emitted reasoning is observation data, not guaranteed ground-truth internal computation.

**First comparison:** Qwen alone vs Qwen + one post-hoc Codex critique/retry vs Qwen + one live intervention. Primary metrics are rescue rate, damage rate, false interventions, latency, and Codex cost. Reject live intervention if timing adds little over post-hoc critique.

### 006 — Qwen Model Surgery

**Hypothesis:** when a reproducible failure survives cheaper external cognitive fixes and can be localized to a repeatable internal mechanism, a minimal causal intervention may repair the failure class without unacceptable collateral regression.

**Architecture:** use an instrumentable Hugging Face checkpoint as the laboratory patient while preserving Q4/Q8 deployment controls. Compare clean and failing runs, capture synchronized telemetry, identify candidate divergence points, perform causal patch sweeps, and only escalate when an intervention repeatedly converts failures to successes on held-out related cases.

**Intervention ladder:** activation/state patch → inference-time steering/gating → learned small gate/adapter → LoRA → targeted parameter edit → structural/topology modification.

**Important rule:** surgery is last. Every intervention must survive target tests, unseen related cases, broad reasoning/instruction/coding/tool/long-context/structured-output/safety regression, exact model/runtime provenance, and deployment re-quantization checks. Stop if no reproducible causal locus emerges.

### Shared follow-on rule

When these candidates are eventually tested, use the same Qwen model, prompts, seeds, task distributions, verifier, telemetry, scoring, token budgets, and evaluation methodology wherever possible. Change only the cognitive backend/intervention being evaluated. The active preregistered Inverted benchmark remains untouched until it is complete.
