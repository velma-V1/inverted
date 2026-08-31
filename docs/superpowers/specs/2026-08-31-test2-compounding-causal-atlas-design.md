# Test 2 Compounding Causal Atlas — Design

## Purpose

Test 2 is not another broad arm benchmark. It is a causal architecture experiment that determines:

1. which components create wins;
2. which components prevent, repair, displace, or introduce failures;
3. which component orders compound best;
4. where gains saturate;
5. which model is best for which role/task/fault class;
6. whether heterogeneous role specialization beats one-model-for-everything;
7. the smallest near-best architecture;
8. the remaining bottleneck and highest-value next experiment.

Test 1 remains immutable evidence. Test 2 is implemented as a parallel harness and reuses Test-1 domain/task/oracle/model primitives without changing Test-1 semantics.

## Non-negotiable constraints

- GitHub/model-free analysis may be large.
- Local Ollama inference must remain bounded: hard ceiling **480 physical model calls** for the full Test-2 local campaign.
- No scientific early stopping. Every preregistered local phase completes unless infrastructure fails.
- The five local models are exactly:
  - `qwen3.5:9b-q8_0`
  - `llama3.1:8b`
  - `ministral-3:3b-instruct-2512-q8_0`
  - `cogito:3b-v1-preview-llama-q8_0`
  - `granite4:7b-a1b-h`
- Model calls use deterministic benchmark settings compatible with the existing Ollama adapter (`temperature=0`, structured JSON contracts, `think=false`).
- Identical model requests are deduplicated by a deterministic call hash; cached reuse is allowed only when model, exact messages, schema/role, and inference settings are identical.
- Every prompt and every response character must be preserved in the evidence packet.
- Deterministic authority remains final; model output is evidence, not authority.
- No new experimental factor is added unless it answers an architectural decision that cannot be derived from existing data.

## Experimental decomposition

### 1. Model-free causal atlas

The model-free portion can be exhaustive because it consumes no local inference. It evaluates deterministic/synthetic cases and replayable Test-1 candidate evidence to produce:

- standalone component effects;
- progressive effects;
- reverse ablations;
- pairwise and selected higher-order interactions;
- valid component-order rankings where model-generation state is unchanged;
- failure kill chains;
- saturation curves;
- break-even thresholds;
- minimum sufficient architecture;
- reliability/cost Pareto frontiers.

Replay analysis must explicitly distinguish **causal replay** from **non-causal counterfactuals**. Any ordering that would have changed an upstream model prompt/response is marked `REQUIRES_NEW_INFERENCE` rather than treated as observed causal evidence.

### 2. Controlled progressive component ladder

Every component is evaluated in three ways:

- `STANDALONE`: baseline + component;
- `PROGRESSIVE`: current best stack + component;
- `ABLATION`: full discovered stack - component.

Components covered by Test 2:

- formalization / structured IR;
- structural/schema validation;
- public requirement validation;
- retry count;
- structured repair feedback;
- targeted repair versus full regeneration;
- deterministic revalidation;
- holistic semantic audit;
- atomic/requirement-wise audit;
- selective audit routing;
- final deterministic revalidation;
- model-role specialization;
- fixed model ensembles/juries derived from already-recorded judgments.

### 3. Outcome transition ledger

Every comparison must classify matched cases into:

- `FAIL_TO_SUCCESS` — recovered win;
- `SUCCESS_TO_FAIL` — regression;
- `FAIL_TO_BLOCKED` — prevented unsafe/incorrect realization, not a win;
- `FAIL_TO_DIFFERENT_FAIL` — displaced failure;
- `CATASTROPHIC_TO_SAFE` — catastrophic removed;
- `SAFE_TO_CATASTROPHIC` — catastrophic introduced;
- `SUCCESS_TO_SUCCESS` — preserved win;
- `FAIL_TO_FAIL` — no outcome recovery.

Reports must never equate blocked failures with recovered wins.

### 4. Failure kill chain

For every failure/fault, record the first stage that detects or eliminates it:

`formalization -> executor -> validator -> repair -> revalidation -> auditor -> final validator -> escaped`

Required derived fields:

- failures prevented;
- failures repaired;
- failures displaced;
- failures escaped;
- catastrophics removed/added;
- first effective defense by fault type;
- residual failures after each layer.

### 5. Local model capability atlas

The bounded local campaign measures each model by:

- role: formalizer, executor, repairer, auditor;
- family: state, policy, reconciliation;
- representation class;
- complexity;
- requirement count;
- fault class;
- output demand.

It produces role/task/fault/complexity/representation rankings instead of one global model score.

### 6. Layered routing analysis

Test 2 must compare four ceilings:

1. `BEST_SINGLE_MODEL` — one model owns every AI role;
2. `BEST_STATIC_ROLE_ASSIGNMENT` — fixed best model per role;
3. `BEST_TASK_TYPE_ROUTER` — routing by observable task metadata;
4. `ORACLE_PER_TASK_MODEL` — retrospective upper bound selecting the best observed model per task.

`routing_regret = oracle_per_task_result - routed_result` is reported per task and in aggregate.

### 7. Model complementarity

For each model pair, compute:

- both succeed;
- A-only succeeds;
- B-only succeeds;
- both fail;
- error overlap;
- unique wins;
- complementarity;
- disagreement precision as a risk signal.

A lower-scoring but less-correlated model may be more valuable in a layered system than a higher-scoring redundant model.

## Local inference budget

The local campaign has a **hard runtime-enforced call ceiling of 480**. The intended allocation is:

| Phase | Maximum calls |
| --- | ---: |
| Formalization profiling | 60 |
| Execution profiling | 60 |
| Fixed-candidate auditing | 100 |
| Atomic-audit comparison | 20 |
| Structured-feedback × repair-strategy experiment | 80 |
| Progressive layered holdout / role specialization | 110 |
| Stability probes on decision-sensitive cells | 40 |
| Reserve | 10 |
| **Hard maximum** | **480** |

A runtime call-budget object must refuse the 481st physical model call. Cache hits do not consume the physical-call budget and must be logged as cache hits.

## Local phase details

### Formalization profiling

Use 12 matched tasks across families/representations and all five models (60 calls). Score:

- requirement precision/recall;
- critical requirement recall;
- hallucinated requirements;
- exact/normalized IR correctness;
- downstream oracle solvability from produced IR.

### Execution profiling

Use 12 matched structured tasks (3 families × 4 complexities) and all five models (60 calls), one-shot, no retry. This isolates generation ability.

### Fixed-candidate auditing

Use 20 fixed candidate packets × five models (100 calls), balanced between valid and invalid candidates and across injected fault types. The exact same candidates are shown to every model.

Score TP/TN/FP/FN, precision, recall, specificity, false-accept rate, false-reject rate, fault-class sensitivity, requirement-count decay, and serial-position effects where available.

### Atomic-audit comparison

Select the top two auditors from the fixed-candidate phase and evaluate the 10 hardest/discriminatory candidate packets using requirement-wise/atomic auditing (20 calls). Compare with already-recorded holistic judgments.

### Repair factorial

Select the top two repair-capable models from preceding evidence. Use 10 identical failing candidates under a 2×2 design:

- raw failed-ID feedback vs structured grounded feedback;
- full regeneration vs targeted repair/preserve-valid-work.

`10 candidates × 2 models × 4 conditions = 80 calls`.

Measure failures fixed, already-correct requirements preserved, new failures introduced, net requirements recovered, and terminal success.

### Progressive layered holdout

Use untouched holdout tasks and compare:

- best single model stack;
- progressively specialized role assignment;
- best static role stack;
- strongest alternate valid component order.

The harness must count actual physical calls and stay within the phase allocation and global 480-call cap.

### Stability probes

Use up to 40 calls on the most decision-sensitive cells (ties, unique wins, surprising failures, routing changes) and classify apparent specialization as `STABLE`, `PROVISIONAL`, or `UNSTABLE`.

## Derived analytics

The analyzer must produce at least:

- `standalone_gain`;
- `progressive_increment`;
- `ablation_loss`;
- wins created/destroyed/net;
- failures prevented/repaired/displaced/added;
- catastrophics removed/added;
- conditional component value;
- pairwise synergy/interference;
- order sensitivity and order spread;
- saturation slope;
- tokens/calls/latency per recovered success;
- failure-kill matrix;
- repair preservation rate;
- model error correlation/complementarity;
- router regret and oracle gap;
- minimum sufficient architecture within 0.5pp, 1pp, and 2pp of best;
- reliability/cost Pareto frontier;
- threshold/break-even analysis for +1pp/+3pp/+5pp/+10pp gain where mathematically estimable;
- residual bottleneck analysis;
- perfect-component ceiling estimates;
- ranked next-stride recommendation.

## Evidence outputs

Every completed Test-2 run writes a self-contained directory:

```text
results/test2/<run-id>/
  00-MASTER-INDEX.json
  raw/
    every-trial.jsonl
    every-model-call.jsonl
    every-prompt.jsonl
    every-response.jsonl
    every-candidate.jsonl
    every-event.jsonl
    every-validator-result.jsonl
    every-repair.jsonl
  effects/
    outcome-transitions.csv
    standalone-effects.csv
    progressive-effects.csv
    ablation-effects.csv
    pairwise-interactions.csv
    failure-kill-matrix.csv
    synergy-matrix.csv
  order/
    every-valid-order.csv
    order-ranking.csv
    saturation.csv
  models/
    model-task-capability-matrix.csv
    model-family-matrix.csv
    model-fault-matrix.csv
    model-complexity-curves.csv
    model-representation-matrix.csv
    model-pair-synergy.csv
    model-correlated-failures.csv
    model-unique-wins.csv
    role-champions.json
    router-policy.json
    router-holdout-results.csv
    router-regret.csv
  thresholds/
    break-even.csv
    plus-1pp.csv
    plus-3pp.csv
    plus-5pp.csv
    plus-10pp.csv
  provenance/
    config.json
    environment.json
    git.json
    models.json
    hashes.json
  TEST2-COMPLETE-EVIDENCE.txt
  TEST2-NEXT-STRIDE-REPORT.txt
  SHA256SUMS.csv
```

The master evidence text must include the complete serialized contents of every text/CSV/JSON/JSONL artifact in deterministic path order. If a GitHub-safe publication mode is requested, it may additionally split the master evidence into deterministic chunks of at most 25 MiB, with ordered hashes; the unsplit local master remains authoritative.

## GitHub validation

GitHub Actions runs the model-free Test-2 validation/simulation matrix and unit tests. It must not require Ollama or external paid inference. The workflow verifies:

- all unit tests;
- deterministic replay/analysis;
- call-budget enforcement;
- output completeness;
- master evidence contains every generated text artifact;
- reproducibility under fixed seeds;
- no mutation of Test-1 arm semantics.

GitHub artifacts are instrument/model-free validation evidence, not local-model architecture results.

## Success criteria

Test 2 is complete when:

1. GitHub model-free validation passes;
2. local runner can execute the five installed models with a hard ≤480 physical-call ceiling;
3. all approved causal/progressive/ablation analyses are generated;
4. model specialization and layered-routing outputs are generated;
5. every prompt/response character is preserved;
6. `TEST2-NEXT-STRIDE-REPORT.txt` identifies the remaining bottleneck and highest-value next experiment from the observed evidence;
7. Test-1 behavior and evidence formats remain unaffected.
