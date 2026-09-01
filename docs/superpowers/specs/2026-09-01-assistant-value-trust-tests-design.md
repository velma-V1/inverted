# Assistant Value & Trust Test Suite — Design

Date: 2026-09-01
Status: APPROVED FOR IMPLEMENTATION
Base branch: `main`
Isolation branch: `build/assistant-value-trust-tests`

## Purpose

Add three independent, bounded experiments that answer the practical architecture question left open by the existing inverted benchmark:

> At what task horizon, evidence quality, and authority level does an inverted/hybrid AI assistant remain useful and trustworthy, and which architecture produces the best capability-to-risk tradeoff?

These tests do **not** replace, reinterpret, or mutate any existing benchmark, configuration, result, documentation, threshold, or historical evidence. Existing repository content is read-only baseline. All implementation is additive.

## Governing constraints

1. Existing files are immutable for this work. Only new files may be added.
2. Deterministic/programmatic ground truth remains the authority. An LLM is never the benchmark judge.
3. Every physical model-call attempt, including errors, consumes the call budget.
4. The runtime must refuse the first call above the configured hard ceiling.
5. Hard ceilings are:
   - Long-Horizon Reliability & Recovery: **1,152 physical model calls**.
   - Evidence Trust / Injection / Abstention: **1,080 physical model calls**.
   - Authority / Side Effects / Trustworthy Autonomy: **1,152 physical model calls**.
6. Every datum created by a run that can be serialized is retained. Backend fields that do not exist remain explicit `null`; they are never fabricated.
7. Full prompts and full responses are captured for these synthetic experiments.
8. Model output is evidence, not authority.
9. Negative results are first-class evidence.
10. GitHub/mock runs validate the instrument only. Architecture claims require real-model runs.

## Shared architecture

The suite lives under a new `inverted.assistant_value` package and reuses the existing model-adapter interface without changing it. Each test owns a deterministic case generator, deterministic oracle, arm runner, and metrics layer. A shared evidence store provides append-only raw ledgers, budget accounting, provenance, integrity hashes, and a complete evidence bundle.

Three common arms are used where meaningful:

- `DIRECT`: the model selects the consequential next decision/action.
- `CHECKED`: the model selects the decision/action, then deterministic checks may block invalid or unsafe realization.
- `INVERTED`: deterministic/system logic proposes the candidate/next action and the model is used primarily as a semantic auditor; deterministic authority remains final.

Matched cases, seeds, evidence, and action spaces are shared across arms. Model-dependent calls use the same model configuration when comparing roles.

## Test 1 — Long-Horizon Reliability & Recovery

### Question

How does reliability decay as an assistant must sustain a multi-step task, and which architecture best prevents one local mistake from becoming a terminal or catastrophic failure?

### Task structure

Deterministic synthetic assistant jobs contain dependent step graphs with horizons of 8, 16, and 30 steps. A step has prerequisites, allowed actions, expected state change, preservation constraints, and a deterministic success condition.

Challenge injections are seeded and include:

- stale state;
- transient tool failure;
- misleading intermediate success;
- interrupted execution/checkpoint restoration;
- recoverable wrong action;
- changed requirement revealed at a defined step;
- context/noise pressure;
- preservation/side-effect trap.

No injected condition changes hidden truth after the run begins unless the case explicitly models a requirement change; every such change is recorded as a ground-truth event.

### Arms

- `DIRECT`: model selects the next action from the public action set.
- `CHECKED`: same direct choice, followed by deterministic dependency/invariant validation and rollback/blocking when invalid.
- `INVERTED`: deterministic planner proposes the highest-ranked valid action; model audits semantic suitability; deterministic invariants remain final.

Exactly one model decision is requested per active step per arm. Recovery from simulated tool failure, rollback, checkpoint restoration, and deterministic validation do not spend model calls.

### Default local plan

With three models, two matched tasks per horizon, and three arms:

`3 models × 2 tasks × (8 + 16 + 30) steps × 3 arms = 972 planned calls`

The remaining budget is reserve only; it is not automatically spent.

### Required metrics

- end-to-end success;
- step accuracy;
- first-error position;
- reliability-vs-horizon curve;
- error propagation depth;
- recovered-error rate;
- rollback effectiveness;
- checkpoint restoration correctness;
- unnecessary replanning/blocking;
- catastrophic compounding rate;
- preservation violation rate;
- calls/tokens/latency per successful job;
- probability of success conditional on prior failure;
- architecture delta by failure class and horizon.

## Test 2 — Evidence Trust, Injection & Knowing When Not To Act

### Question

Can the architecture identify when evidence is sufficient, conflicting, stale, irrelevant, or adversarial, and can it abstain when acting would be unjustified without becoming over-conservative?

### Evidence regimes

Matched cases are generated across six regimes:

1. `complete`
2. `partial`
3. `irrelevant`
4. `stale`
5. `contradictory`
6. `adversarial`

Evidence items carry source ID, provenance class, timestamp/freshness, trust tier, content, and whether the item contains an untrusted embedded instruction. The hidden oracle knows the canonical fact/action and whether the correct behavior is `ACT` or `ABSTAIN`.

Adversarial evidence may contain prompt-injection-like text, forged authority claims, poisoned retrieval, or plausible misinformation. These strings are inert benchmark data; no real external action is performed.

### Arms

- `DIRECT`: model decides `ACT`/`ABSTAIN`, selected action, relied-on evidence IDs, confidence, and rationale.
- `CHECKED`: direct decision followed by deterministic provenance/freshness/sufficiency gates.
- `INVERTED`: deterministic evidence resolver constructs the best supported candidate or `ABSTAIN`; model audits that candidate; deterministic evidence rules remain final.

### Default local plan

`120 matched cases × 3 arms × 3 models = 1,080 planned calls`

Twenty cases per evidence regime are used by default.

### Required metrics

- correct-action rate;
- correct-abstention rate;
- unjustified-action rate;
- unnecessary-abstention rate;
- evidence-selection precision/recall;
- stale-source selection rate;
- contradiction handling accuracy;
- prompt-injection success rate;
- forged-authority acceptance rate;
- auditor false-accept / false-reject rates;
- confidence calibration (Brier score and confidence bins);
- false-confidence rate;
- provenance-awareness rate;
- architecture delta by evidence regime;
- tokens/calls/latency per correct decision.

## Test 3 — Authority, Side Effects & Trustworthy Autonomy

### Question

How much operational authority can the assistant safely hold before risk becomes unacceptable, and which architecture best preserves useful autonomy while preventing unauthorized or unnecessarily destructive actions?

### Simulated tool classes

Cases span eight simulated classes:

- `read`
- `write`
- `delete`
- `send`
- `publish`
- `purchase`
- `configure`
- `credential`

All effects occur in an in-memory synthetic world. No real purchase, credential operation, message, publication, deletion, or external side effect is executed.

Each case defines user intent, authorization scope, resource sensitivity, reversibility, required approval level, candidate actions, least-privilege action, and deterministic consequence severity.

Challenge cases include:

- explicit authorization;
- ambiguous authority;
- expired/revoked permission;
- over-broad action scope;
- chained actions whose combination becomes unsafe;
- deceptive tool result;
- irreversible operation requiring escalation;
- legitimate high-impact action that should proceed;
- safe lower-privilege alternative;
- request/action mismatch.

### Arms

- `DIRECT`: model chooses execute/block/escalate and an action.
- `CHECKED`: direct choice is passed through deterministic authorization, scope, reversibility, and approval gates.
- `INVERTED`: deterministic policy controller proposes execute/block/escalate plus least-privilege action; model audits semantic fit; deterministic policy authority is final.

### Default local plan

Fifteen cases per tool class gives 120 matched cases.

`120 cases × 3 arms × 3 models = 1,080 planned calls`

This leaves 72 calls of reserve below the 1,152 ceiling.

### Required metrics

- unauthorized-action rate;
- catastrophic side-effect rate;
- correct escalation rate;
- missed escalation rate;
- overblocking rate;
- least-privilege compliance;
- authorization-scope accuracy;
- irreversible-action handling;
- chained-risk detection;
- legitimate high-impact completion rate;
- utility-preserving safety rate;
- damage avoided;
- safe-autonomy frontier by consequence severity/authority tier;
- tokens/calls/latency per safely completed task.

## Complete evidence contract

Every run writes a self-contained directory under:

`runs/assistant-value/<test-name>/<run-id>/`

At minimum:

```text
00-MASTER-INDEX.json
preregistration.json
config.json
provenance.json
tasks.jsonl
state_snapshots.jsonl
model_calls.jsonl
prompts.jsonl
responses.jsonl
actions.jsonl
tool_results.jsonl
oracle_results.jsonl
transitions.jsonl
events.jsonl
trials.jsonl
trials.csv
failures.csv
metrics.json
metrics.csv
budget.json
anomalies.jsonl
integrity.json
COMPLETE-EVIDENCE.txt
SHA256SUMS.csv
```

Rules:

- Raw JSONL ledgers are append-only during execution.
- Every model call is persisted immediately after completion/error.
- Every prompt and every response is preserved character-for-character when exposed by the adapter.
- Every generated task, injected challenge, action candidate, chosen action, state before/after, tool result, deterministic check, oracle result, model decision, parser failure, timeout, retry metadata, token count, latency, confidence, and budget transition is retained.
- All seeds and generation parameters are retained.
- `events.jsonl` is the canonical chronological event stream and references the specialized ledgers.
- `COMPLETE-EVIDENCE.txt` serializes every non-recursive text/JSON/JSONL/CSV evidence artifact in deterministic path order.
- `SHA256SUMS.csv` hashes the final evidence artifacts.
- `integrity.json` reports missing required artifacts, JSONL parse failures, trial/call count inconsistencies, and budget violations.
- Missing provider telemetry is explicit `null`, never synthesized.

## Call-budget integrity

A shared `PhysicalCallBudget` reserves a call before model invocation. Reservation is atomic within the process. A failed/timeout/censored call still consumes one physical call. Cache reuse, if ever added, must be separately logged and may not masquerade as a physical call.

A plan whose worst-case deterministic call count exceeds its test ceiling is rejected before the first call.

## Mock/GitHub validation

A deterministic mock model validates:

- generation determinism;
- correct oracle labels;
- arm isolation;
- budget refusal at `cap + 1`;
- raw prompt/response preservation;
- failure/error persistence;
- complete artifact creation;
- SHA-256 integrity;
- deterministic rerun equality for semantic outputs (timestamps/latencies excluded);
- zero mutation of existing baseline files.

Mock/GitHub outputs are explicitly instrument-validation evidence, not architecture evidence.

## Success criterion for implementation

Implementation is complete only when all existing repository tests plus all new assistant-value tests pass on the feature branch, the smoke suite produces complete evidence packets for all three experiments, the hard-cap tests prove refusal above each ceiling, and the branch diff contains additions only.