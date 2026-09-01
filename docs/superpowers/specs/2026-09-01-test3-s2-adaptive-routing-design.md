# Test-3 Section 2 Adaptive Routing — Design

Date: 2026-09-01
Status: FROZEN DESIGN — NO TIER-A INFERENCE AUTHORIZED
Predecessor: S1-R3 (`S1_R3_SCREEN_NON_DECISIVE`)
Branch: `build/test3-s2-adaptive-routing`

## 1. Question

Does choosing the next operation from the verified current evidence state outperform the best fixed topology when compute is equalized?

S1-R3 established that no universal fixed order earned promotion and exposed conditional reversals: retry-first and repair-first win on different verified failure states. S2 tests whether routing on that evidence is causally useful.

## 2. Holdout B

Fresh Holdout B contains 72 matched cases:

- 6 task families: `state`, `policy`, `reconciliation`, `preservation`, `dependency_order`, `repair_containment`;
- 4 complexity levels per family;
- 3 deterministic verified failure perturbations per base task: `localized`, `compound`, `structural`.

Each trio is a causal-twin group: same underlying public task and goal, different verified current failure state. No S1 holdout task or seed may be reused.

## 3. Arms

Five real inference arms plus one analysis-only oracle:

- `S2-B0`: fixed control — S1 best fixed sequence, retry then targeted repair.
- `S2-B1`: task-family router — route uses only task family.
- `S2-B2`: failure-signature router — route uses only public verified failure signature, failure kinds, and failure count; family identity is not directly supplied.
- `S2-B3`: rich evidence-state router — route may use family, complexity, failure signature, failed-count, prior model/action, deterministic result, retry count, and budget remaining.
- `S2-B4`: seeded random router negative control — choices are deterministic from preregistered seeds and independent of outcomes.
- `S2-ORACLE`: post-hoc observed-action ceiling only; consumes zero inference and may not influence execution.

## 4. Common intervention library

Every real arm chooses from the same operations and models:

- `retry_qwen`: full regeneration using `qwen3.5:9b-q8_0`.
- `repair_cogito`: targeted repair patch using `cogito:3b-v1-preview-llama-q8_0` and S1-R3 patch composition semantics.
- `switch_llama`: full regeneration/model switch using `llama3.1:8b`.

No arm receives an action unavailable to another arm.

## 5. Equal compute and budget

Each arm-task receives exactly two physical model calls. If an active intervention succeeds before the second call, the second call executes as shadow inference and cannot mutate the trial result.

Exact planned Tier-A model calls:

`72 cases × 5 real arms × 2 calls = 720 physical model calls`.

S2 also performs bounded model-identity/provenance acquisition around the real run. Each Ollama provenance snapshot performs 6 external API requests: `/api/version`, `/api/tags`, `/api/ps`, plus one `/api/show` request for each of the 3 frozen models. A healthy Tier-A run takes one snapshot before inference and one after inference, for exactly 12 provenance API calls.

Therefore the frozen budgets are:

- scientific inference budget: **720 physical model calls**;
- provenance/API allowance: **12 external API calls**;
- combined external/AI action budget: **732 total actions**;
- repository absolute per-test ceiling: **1000 combined actions**.

The mock/CI run consumes 720 mock model actions and zero external provenance API calls, leaving 12 declared actions unused. A healthy real Tier-A run consumes 720 model calls plus 12 provenance API calls = 732 combined actions. If provenance collection fails before all 12 requests complete, actual use is retained exactly and the architecture claim is withheld rather than inventing missing usage.

The 732 combined budget is a ceiling for the frozen S2 execution, not a quota for redundant work. Its purpose is the 720-call orthogonal causal design plus the minimum provenance needed to prove which frozen models actually ran.

No outcome-dependent early stopping is permitted.

## 6. Failure perturbations

All perturbations begin from a deterministically generated known-valid candidate and are mutated without model inference. The resulting candidate must fail deterministic verification before any Tier-A call.

- `localized`: one public requirement is violated while unrelated correct work remains intact.
- `compound`: two causally distinct public requirements are violated where the task supports two; otherwise two independent mutations within the family are used and verified.
- `structural`: family-appropriate semantic/order/preservation/action corruption, including wrong operation, forbidden operation, dependency inversion, preservation violation, or repair-containment corruption.

Perturbation metadata used to construct the fixture is hidden from all production routers and prompts. Routers receive only evidence available at decision time.

## 7. Routing boundary

Allowed decision-time features:

- task family (B1/B3 only as specified);
- complexity (B3 only);
- public requirement kinds;
- failed requirement IDs/kinds/count;
- deterministic success/failure and catastrophic signal;
- action/state failure signature derived from public validator evidence;
- previous selected action/model;
- retry/action count;
- combined action budget spent/remaining.

Forbidden router/prompt features:

- target state;
- hidden gold or oracle answer;
- injected fault labels/fixture metadata;
- perturbation class label;
- future outcome;
- oracle-selected action;
- S1 result labels for the same case.

Runtime must fail closed if forbidden data crosses the public boundary.

## 8. Two-step adaptive behavior

For B3, the second operation is selected only after the first result is deterministically revalidated. The second decision may change action/model based on the updated verified state. B0/B1/B2/B4 also revalidate every active mutation but follow their frozen policy rules.

All shadow calls are recorded with the same prompts/settings they would have received at that point but cannot change state or verdict.

## 9. Stochastic divergence instrumentation

S2 treats response non-determinism as first-class evidence. A call fingerprint is computed from normalized model identity, normalized messages/prompt, role, response schema, and inference settings.

If two calls share the same fingerprint but return different response digests, record `STOCHASTIC_RESPONSE_DIVERGENCE` with both call identities, outputs/digests, token/latency telemetry, affected arm/task, and whether the divergence changed success/catastrophe/routing outcome.

Divergence does not silently invalidate a run. Analysis must attribute observed arm differences that depend on divergent same-fingerprint responses.

## 10. Execution balance

Execution uses balanced task blocks. Arm execution position is rotated deterministically across cases so arm identity is not confounded with thermal/cache/time order. B4 random routing uses a separate frozen seed stream and never consumes runtime randomness from model outcomes.

No cache hits are allowed in Tier-A S2. Model adapters use zero transport retries.

## 11. Primary estimands

For B1/B2/B3 versus B0 and B4:

- paired wins, losses, ties, and net wins;
- success-rate delta;
- catastrophe delta;
- regret to observed oracle;
- recovery from initial verified failure;
- newly introduced failures;
- results by family, complexity, and perturbation class;
- action/model selection distribution;
- first→second action transition matrix;
- marginal value of model switch versus retry versus repair;
- execution-position effects;
- tokens, latency, and cost per recovery;
- stochastic-divergence-attributed outcomes.

Additional comparison: B2 versus B1 isolates value of failure evidence beyond coarse task-family routing.

## 12. Oracle

The observed oracle is computed after execution from actually observed arm/action trajectories only. It may select the best observed valid outcome per matched case subject to the same two-call envelope. It cannot fabricate unobserved model behavior and cannot be used to route real calls.

## 13. Verdict contract

`S2_ADAPTIVE_ROUTING_SIGNAL` requires B3 to satisfy all of:

1. positive paired net wins versus B0 of at least +4;
2. positive paired net wins versus B4 of at least +4;
3. success-rate improvement versus B0 of at least 5 percentage points;
4. no increase in aggregate catastrophes versus B0;
5. positive family/failure-mode support in at least 3 distinct strata, where each supported stratum has paired net wins >= +2 and no catastrophe increase;
6. lower regret-to-observed-oracle than B0;
7. the promotion conclusion remains after outcomes causally dependent on recorded stochastic divergence are removed.

`S2_FAILURE_EVIDENCE_INCREMENTAL_SIGNAL` may additionally be reported if B2 beats B1 by paired net wins >= +3 with no catastrophe increase.

`S2_ADAPTIVE_ROUTING_HARMFUL` applies if B3 has paired net wins <= -4 versus B0 or adds >=2 catastrophes without compensating positive net wins.

Otherwise the result is `S2_SCREEN_NON_DECISIVE`.

Protocol/integrity failure has precedence over all scientific verdicts.

## 14. Required evidence packet

S2 must retain the standard campaign evidence plus:

- `00-MASTER-INDEX.json`
- `preregistration.json`
- `config.json`
- `provenance.json`
- `model_calls.jsonl`
- `events.jsonl`
- `trials.csv`
- `validator_results.csv`
- `arm_accounting.csv`
- `arm_summaries.csv`
- `family_summaries.csv`
- `perturbation_summaries.csv`
- `complexity_summaries.csv`
- `pairwise_effects.csv`
- `routing_decisions.csv`
- `routing_state_snapshots.jsonl`
- `action_transition_matrix.csv`
- `shadow_counterfactuals.csv`
- `regret_to_oracle.csv`
- `fault_mode_effects.csv`
- `prompt_fingerprints.csv`
- `stochastic_divergence.csv`
- `action_budget.csv`
- `router_policy_snapshot.json`
- `router_policy_hashes.csv`
- `transitions.csv`
- `failures.csv`
- `wins.csv`
- `losses.csv`
- `costs.csv`
- `latency.csv`
- `tokens.csv`
- `cache.csv`
- `edge_cases.csv`
- `instrumentation_anomalies.csv`
- `protocol_failures.json`
- `verdict.json`
- `report.txt`
- `COMPLETE-EVIDENCE.txt`
- `SHA256SUMS.csv`

Every raw prompt/response, candidate/action state, validation result, active/shadow status, provenance field, edge case, anomaly, token count, latency, model/settings identity, action-class count, and hash required to reconstruct the causal path must be retained.

## 15. Progress contract

Every real/mock S2 run uses the repository testing policy and renders a split-screen-safe single-line progress meter containing progress bar, percent complete, completed/total arm-tasks, physical calls used/720, current arm/phase, elapsed time, time left, and ETA. ETA is display-only and cannot affect scientific execution.

## 16. Development gate

Implementation follows TDD. Before Tier-A authorization:

- all S2 regression/contract tests are GREEN;
- full repository pytest is GREEN;
- S2 mock validation completes exactly 720 mock physical calls;
- mock evidence reports combined action limit 732 and actual combined use 720;
- real execution is fail-closed above 732 combined external/AI actions;
- provenance transport accounting proves each real provenance API request consumes the same shared action budget;
- evidence packet completeness/hashes pass;
- public-boundary leakage tests pass;
- stochastic-divergence tests pass;
- combined action-budget fail-closed tests pass;
- split-screen progress tests pass;
- GitHub Actions S2 validation and general cross-platform workflows are GREEN on the same branch SHA.

No real model inference is authorized by this design artifact.