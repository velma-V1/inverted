# Test 3 Section 1 — S1-R3 Corrective Protocol

## Status

Frozen corrective protocol for the next local Tier-A Section 1 run. S1-R1 and S1-R2 remain immutable historical instruments and evidence.

## Why R3 exists

The completed S1-R2 200-call run is retained as measurement-system evidence but is invalid for the primary fixed-order causal claim for two independent reasons discovered during forensic review:

1. **Control causal-order collapse.** S1-A1 and the nominal S1-A3 random-order control reduced to the same intervention-relevant causal sequence after deterministic validator-only steps were removed. Their prompts/call pattern were therefore not an independent causal contrast.
2. **Repair contract ambiguity.** The repair prompt requested only failed-part repair, while the R2 runtime treated the repairer's returned actions as a full replacement candidate. Patch-like responses could therefore erase already-correct work and manufacture regressions/catastrophes.

R2 run retained as invalid predecessor: `test3-s1-r2-20260901-140516`.
Classification: `REPAIR_CONTRACT_AMBIGUITY_AND_CONTROL_COLLAPSE`.

## R3 causal question

With equal compute and verified-bad matched starts, does a fixed component order materially change task success, catastrophe rate, or family-conditional performance when every fixed/control arm has a distinct intervention-relevant causal sequence and repair semantics are unambiguous?

## Frozen changes from R2

### Fresh holdout

- Protocol: `S1-R3`
- Holdout: `A-R3`
- 25 matched tasks across the same six families.
- Seed base: `811000`
- Seed stride: `233`
- Fault seed namespace base: `1100001`
- Seeds are disjoint from Test-2, S1-A, A-R1, and A-R2.

### Explicit repair-patch contract

`targeted_repair` must return only the actions needed to fix failed public requirements. The runtime deterministically composes that patch with the prior candidate:

- unrelated already-correct actions are retained;
- actions implicated by failed requirements are eligible for removal/replacement;
- same-path patch actions replace prior same-path actions;
- dependency-order patch action order is preserved;
- no hidden fault/oracle metadata is exposed to the model.

### Distinct causal-order control

Frozen arms:

- `S1-A0`: best-single baseline; no fixed component order.
- `S1-A1`: `requirement_validator -> retry -> targeted_repair -> final_validator`
- `S1-A2`: `requirement_validator -> targeted_repair -> final_validator -> retry`
- `S1-A3`: `requirement_validator -> targeted_repair -> retry -> final_validator`

For causal-signature validation, deterministic observation-only `requirement_validator` is excluded. The three fixed/control signatures must therefore be exactly distinct:

- A1: `retry -> targeted_repair -> final_validator`
- A2: `targeted_repair -> final_validator -> retry`
- A3: `targeted_repair -> retry -> final_validator`

Any collision fails closed **before inference**.

## Frozen invariants retained from R2

- Exactly 25 matched tasks.
- Exactly 4 arms.
- Exactly 2 physical model calls per arm-task trial.
- Exactly 100 arm-task trials.
- Exactly 200 physical calls total.
- Exactly 50 physical calls per arm.
- No cache hits.
- No internal/transport inference retries.
- No outcome-dependent early stopping.
- Balanced deterministic arm execution schedule.
- Same six task families and extra L4 repair-containment stress case.
- Same resolved Test-2 models: best single/executor and repairer are loaded from committed Test-2 Tier-A evidence.
- Same preregistered R2 verdict thresholds; R3 changes instrument validity, not statistical decision boundaries.
- Same underpowered-screen caveat: a non-decisive R3 result cannot exclude small effects near the S0 target effect; S0 estimated roughly 260 matched clusters for full-power small-effect detection.

## Primary validity gate

R3 is valid for its primary causal claim only if all of the following hold:

- protocol `S1-R3` and holdout `A-R3`;
- 25 matched tasks and 100 complete arm-task trials;
- 200 total physical calls and 50 per arm;
- exactly two calls per trial;
- zero cache hits and zero internal retries;
- verified-bad deterministic starts;
- public-only prompts;
- full matched-task schedule and balanced arm positions;
- at least one active intervention per trial;
- three distinct fixed/control causal-order signatures;
- repair responses use the explicit patch-composition runtime.

If any condition fails, the primary verdict is `S1_R3_INVALID_PROTOCOL` and the evidence is retained.

## Verdict precedence

R3 reuses the frozen R2 thresholds and precedence with R3 labels:

1. invalid protocol;
2. aggregate large fixed-order signal;
3. category-conditional fixed-order signal;
4. negative/harmful fixed-order signal;
5. non-decisive.

No R2 result is reinterpreted as valid by this protocol. R3 is a new prospective measurement after the R2 instrument defects were identified.
