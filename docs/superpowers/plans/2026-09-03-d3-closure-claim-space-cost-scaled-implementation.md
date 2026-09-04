# D3-Closure v2 Claim-Space Adequacy + Cost-Scaled Tomography Implementation Plan

**Goal:** Replace the fixed 158/200-call Closure design with a model-free claim-space adequacy engine and a cost-scaled adaptive inference controller that can search large information/support spaces without brute force, scale sample depth by actual model cost, and mechanically prevent claims that outrun achieved coverage.

**Normative inputs:**

- `REPO_LAWS_AND_REGULATIONS.md`
- `INVERTED_CONSTITUTION.md`
- `CLAIM_SPACE_ADEQUACY_AMENDMENT.md`
- `docs/superpowers/specs/2026-09-03-harvest-d-d3-closure-v2-design.md`
- `docs/superpowers/specs/2026-09-03-harvest-d-d3-closure-search-space-adequacy-addendum.md`
- `configs/harvest-d-local-model-cost-profile.json`

**Historical boundary:** D3-v1 remains immutable. No physical D3-Closure call may be spent until the new adequacy engine is green and physical authorization is explicitly enabled.

## Task 1 — Search-space schemas and exact zero-call accounting

Create `d3_closure_search_space.py` and tests.

Required:

- explicit factors/levels for I1-I10, representation, ordering, amount, timing, placement, A1-A4;
- effect-modifier schema for model/family/structural case features;
- exact raw theoretical count without materializing the full Cartesian product;
- deterministic treatment identities;
- legality/equivalence/no-op rules;
- reduced-space summary;
- machine-readable manifests/pruning ledger.

RED requirements:

- raw candidate count is derived from factor cardinalities, not hard-coded;
- no-op ordering/placement/timing variants collapse;
- byte/semantic-equivalent treatments share an equivalence class;
- hidden-oracle/invalid combinations are rejected;
- system-only factors never count as physical model-call candidates.

## Task 2 — Mixed-level pairwise covering design

Create `d3_closure_covering.py` and tests.

Implement deterministic greedy covering-array construction over legal factor vectors with constraints.

Required:

- 100% coverable 2-way factor-level pair coverage;
- explicit constrained/uncoverable pair report;
- deterministic seed/tie-breaking;
- no full Cartesian materialization;
- protected random/challenger sample capability;
- targeted required 3-way tuples accepted as extra coverage obligations.

The generator may optimize row count greedily; minimum mathematical covering-array size is not required. Coverage correctness is required.

## Task 3 — Hardware-aware cost model

Create `d3_closure_cost.py` and tests.

Required:

- load/version `harvest-d-local-model-cost-profile.json`;
- classify SYSTEM_ONLY as FREE;
- tiny-model override/prior as NEAR_FREE;
- installed model size > 9.5 GiB => VERY_EXPENSIVE prior;
- <= 9.5 GiB => MEDIUM_OR_CHEAPER prior;
- thinking/context-exhaustion can raise class;
- measured stable latency can refine class;
- observed spill/offload/severe latency raises class;
- inference wall time is primary local budget debit;
- physical-call count is a separate runaway guard;
- protected confirmation time/call reserve cannot be borrowed.

Budget state must track calls, seconds, tokens, system-only operations, and confirmation reserve separately.

## Task 4 — Reproducibility/cost calibration planner

Create calibration plan generation.

Required:

- exact-condition repeated calls across structurally diverse cases/models;
- default max 24 calls but adaptive early stop only under explicit stability rule;
- output fields for byte/semantic/outcome identity, latency, token/context, installed model size/digest, thinking mode, offload signal;
- empirical noise floor;
- frozen cost class by model/policy.

Calibration is a prerequisite to live search allocation, except zero-call footprint priors may fail closed before calibration.

## Task 5 — Cost-aware adaptive frontier

Create `d3_closure_frontier.py` and tests.

Each candidate tracks:

- coverage novelty;
- expected decision impact;
- main/interaction uncertainty;
- model/family conditional uncertainty;
- invariant risk;
- estimated cost seconds;
- cost class;
- evidence state;
- survivor/eliminated state.

Priority is information/decision value per calibrated cost after safety/invariant priority.

Fast/near-free candidates must receive a larger permissible sample allowance than otherwise-equivalent very-expensive candidates under the same inference-time budget.

Retain protected discovery/challenger budget.

## Task 6 — Local optimization and minimum-support ablation planner

Create `d3_closure_local_search.py` and tests.

Given a surviving policy, generate one-coordinate neighbors and leave-one-out removals for:

- each retained I-field;
- A1-A4;
- representation;
- ordering;
- amount;
- timing/placement.

Require at least one joint-removal challenger after single-component convergence.

No policy may be labeled MINIMUM_SUFFICIENT until all retained components have applicable ablation evidence or the claim is explicitly bounded/UNRESOLVED.

## Task 7 — Real recovery protocol

Replace synthetic C4-only recovery labeling with a real multi-step recovery plan.

Required trajectory:

`initial call -> observed failure/divergence -> detection/classification -> recovery context/frontier -> second recovery model/system action when applicable -> resulting state -> independent verification`.

System-owned recovery that requires no second model call remains zero-call; cognition-recovery claims require a real second call.

Cost-scale recovery calls like every other call.

## Task 8 — Claim adequacy report and fail-closed authorization

Create `d3_closure_adequacy.py` and tests.

Report must include:

- raw/legal/reduced search counts;
- main-effect coverage;
- 2-way coverage;
- required 3-way coverage;
- unexplored/pruned regions;
- calibration state;
- cost profile/digests;
- local-minimality capability;
- real recovery capability;
- protected confirmation state;
- claim strength currently legal;
- `physical_execution_authorized`.

Authorization is false if any mandatory element is missing/stale/unverified.

## Task 9 — Integrate model-free CLI/package

Update Closure CLI/campaign model-free mode to emit all new manifests and adequacy outputs.

The current fixed Closure plan becomes legacy/screening-only and may not authorize physical inference.

Real mode must load a fresh adequacy report and cost calibration state for the exact config/provenance before any call.

## Task 10 — Replace raw call budget with cost-scaled logical phases

Implement logical T0-T8 phase controller from the addendum.

Use a budget vector with:

- max inference wall-time seconds;
- loose physical-call runaway ceiling;
- protected confirmation seconds/calls;
- per-model/policy calibrated cost;
- required coverage obligations.

Sample counts are derived after calibration; they are not frozen globally in source code.

## Task 11 — Operational hardening carried forward from Law 28 audit

Before authorization, close all previously discovered operational defects:

- exact Ollama model digest binding for D4 and Closure;
- frozen D4 policy bound to exact Qwen digest;
- Closure CLI nonzero unless scientifically COMPLETE/authorized terminal state;
- frozen D3-v1 revalidated every real invocation;
- PowerShell test list flattening;
- actual Windows execution of D4/Closure model-free launchers in CI;
- ambiguous crash/resume hard stop;
- no blind retry;
- no false COMPLETE on missing artifacts/coverage/recovery.

## Task 12 — RED -> GREEN -> full audit

For each task:

1. add failing focused tests;
2. verify RED is for the intended missing behavior;
3. implement minimum correct production behavior;
4. run focused and Harvest D regressions;
5. run full repository suite;
6. execute Windows model-free launcher CI;
7. rerun Law 28 blocker audit;
8. rerun claim-space adequacy audit.

Only then may `configs/harvest-d-d3-closure-v2-execution-authorization.json` be changed to `physical_execution_authorized: true`.

## Completion criterion

The build is complete only when:

- every relevant CI job is green;
- model-free Closure produces valid search-space, coverage, cost-profile, and adequacy artifacts;
- the old 158/200 call assumption is no longer the scientific authority;
- fast/cheap vs slow/large models receive demonstrably different dynamic sample economics;
- >9.5 GiB current-hardware residency prior is enforced and calibrated;
- system-only work consumes zero model-call budget;
- physical execution is impossible without fresh adequacy authorization;
- final blocker audit finds no unresolved HARD BLOCKER or unbounded SCIENTIFIC RISK capable of invalidating the planned run.
