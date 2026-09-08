# V3 Stage 7 — Tool / Skill / Verification / Recovery Tomography Design

## Status

Owner-approved Stage-7 architecture. Design only. This document authorizes implementation planning but does **not** authorize real Qwen/Ollama/network/tool execution.

Stage 7 is the direct continuation of the Universal Capability Ratchet V3 after Stage 6 (`Failure Mutation and Neighborhood Generalization`). Its purpose is to determine whether residual failures are best repaired by a tool, reusable skill/policy, deterministic verifier, targeted recovery mechanism, model-internal improvement, escalation, or a hard safe-stop boundary.

Stage 7 must reuse the existing causal vocabulary, replay lineage, evidence stores, and `ReplayRequest -> ReplayExecutor -> TEST_REPLAY.jsonl` execution spine. It must not introduce an independent runner, transport, retry loop, or alternate replay registry.

## 1. Objective

For every residual failure admitted to Stage 7, answer:

> **Which responsibility owner actually removes the failure at the lowest durable complexity and cost, what observable evidence distinguishes that owner from nearby alternatives, and what exact boundary prevents a one-off repair from being mistaken for generalized capability?**

The Stage-7 unit of progress is a **resolved ownership distinction**, not another successful retry.

Examples:

- missing tool capability vs model capability limit;
- tool unavailable vs tool selected incorrectly;
- correct tool selected vs incorrect arguments;
- correct tool result vs incorrect result interpretation;
- generation failure vs verifier-detectable failure;
- targeted recovery vs generic retry;
- reusable procedural deficit vs one-off prompt sensitivity;
- model-internal residual vs externally removable responsibility.

Every Stage-7 experiment must change at least one named V3 decision, principally D2, D6, D7, D8, D11, or D12.

## 2. Governing constraints

1. **Existing evidence first.** Historical replay, mechanism, Stage-5 surface, and Stage-6 mutation evidence are consulted before new calls are schedulable.
2. **No new executor.** All physical replay continues through the existing canonical `ReplayExecutor`.
3. **No alternate replay lineage.** All executable probes and outcomes remain represented in `TEST_REPLAY.jsonl`; Stage-7 metadata may reference canonical records but may not replace or duplicate them.
4. **No blind retry escalation.** Failure of attempt 2 does not authorize attempt 3. A generic retry may exist only as an explicit matched control when it can change a named decision.
5. **Targeted recovery must name the changed state.** Recovery is not "try again". The recovery treatment must identify the verifier result, tool failure, state correction, action change, rollback, re-anchor, or other registered intervention that differentiates the branch.
6. **Tool decomposition is mandatory.** Tool capability, availability, selection, arguments, execution, result interpretation, and postcondition verification are distinct scientific layers.
7. **Verifier and recovery remain separable.** Detection, diagnosis, correction proposal, authorization, execution, and final verification may not be collapsed into one opaque success label.
8. **Reusable skill evidence must exceed one instance.** A procedural treatment that repairs a single fixture is not automatically a `SKILL` owner.
9. **External repair does not prove model deficiency.** Tool/verifier/skill success narrows ownership; it does not by itself establish a model-internal limit.
10. **Model limit requires alternatives to fail.** `MODEL_CAPABILITY_LIMIT`, `FINE_TUNE`, `ESCALATION`, or `SAFE_STOP` conclusions require the cheaper admissible external alternatives to be tested or already resolved by valid evidence.
11. **Stage 7 cannot certify production capability.** New mechanisms earning `MOVEMENT` must re-enter localization/generalization before Stage 8 compilation.
12. **Fresh and sealed partitions remain protected.** Development tomography may inspect partition labels but cannot consume or mutate protected confirmation evidence.
13. **No hidden-oracle routing.** Probe planning may use stored scientific labels for experiment construction, but production-relevant ownership conclusions must ultimately be supportable from observable state.
14. **Development validation remains zero-call.** Unit tests, preflight, permanent audit, historical eligibility scans, and auto-planning must construct no live model/tool/network transport.
15. **Negative evidence changes the map.** A failed tool/skill/verifier/recovery treatment must narrow ownership, boundary, routing, escalation, fine-tuning eligibility, or safe-stop disposition.
16. **Complexity pays rent.** If a simpler deterministic owner produces equivalent verified capability, the more complex owner does not advance.

## 3. Reuse existing causal contracts

Stage 7 reuses the existing `DivergenceClass` values:

- `TOOL_CAPABILITY`
- `TOOL_SELECTION`
- `TOOL_ARGUMENTS`
- `TOOL_INTERPRETATION`
- `VERIFIER_FEEDBACK`
- `RECOVERY_POLICY`
- `SKILL_DEFICIT`
- `MODEL_CAPABILITY_LIMIT`

Stage 7 also reuses the existing `ArchitectureOwner` values:

- `MODEL`
- `SYSTEM`
- `TOOL`
- `SKILL`
- `VERIFIER`
- `RECOVERY`
- `ROUTER`
- `FINE_TUNE`
- `ESCALATION`
- `SAFE_STOP`

And it reuses the existing intervention kinds where applicable:

- `TOOL`
- `SKILL`
- `VERIFICATION_RECOVERY`
- `DETERMINISTIC`
- `ESCALATION`
- `SHAM`
- `ABLATION`

Stage 7 must not create synonymous duplicate enums or a parallel owner taxonomy.

## 4. Architecture

Stage 7 adds a bounded tomography layer over existing stores and replay machinery.

```text
canonical failure/mechanism evidence
            |
            v
   TomographyEligibility
            |
            v
    TomographyPlanner  ---- historical/reused evidence
            |
            v
   TomographyProbeSpec
            |
            v
  TomographyReplayCompiler
            |
            v
 existing ReplayRequest / ReplayExecutor
            |
            v
      TEST_REPLAY.jsonl
            |
            v
   TomographyEvidenceStore
            |
            v
   TomographyAnalyzer
            |
            +--> ownership/boundary disposition
            |
            +--> new MOVEMENT mechanism -> Stage 4 -> 5 -> 6
            |
            +--> qualified residual -> Stage 8/9/10/11 path
```

The new layer owns **experimental design and scientific interpretation only**. It does not own model transport, tool transport, replay identity, or final production routing.

## 5. Components

### 5.1 `tomography_core.py`

Frozen Stage-7 scientific contracts.

Required primary contracts:

```python
class TomographyAxis(str, Enum):
    TOOL_AVAILABILITY = "TOOL_AVAILABILITY"
    TOOL_SELECTION = "TOOL_SELECTION"
    TOOL_ARGUMENTS = "TOOL_ARGUMENTS"
    TOOL_EXECUTION_RESULT = "TOOL_EXECUTION_RESULT"
    TOOL_RESULT_INTERPRETATION = "TOOL_RESULT_INTERPRETATION"
    VERIFIER_VISIBILITY = "VERIFIER_VISIBILITY"
    VERIFIER_FEEDBACK = "VERIFIER_FEEDBACK"
    TARGETED_RECOVERY = "TARGETED_RECOVERY"
    GENERIC_RETRY_CONTROL = "GENERIC_RETRY_CONTROL"
    SKILL_PROCEDURE = "SKILL_PROCEDURE"
    SKILL_TRIGGER = "SKILL_TRIGGER"
    ESCALATION_REFERENCE = "ESCALATION_REFERENCE"
```

```python
class TomographyDisposition(str, Enum):
    TOOL_REQUIRED = "TOOL_REQUIRED"
    TOOL_SELECTION_DEFICIT = "TOOL_SELECTION_DEFICIT"
    TOOL_ARGUMENT_DEFICIT = "TOOL_ARGUMENT_DEFICIT"
    TOOL_INTERPRETATION_DEFICIT = "TOOL_INTERPRETATION_DEFICIT"
    VERIFIER_SUFFICIENT = "VERIFIER_SUFFICIENT"
    RECOVERY_SUFFICIENT = "RECOVERY_SUFFICIENT"
    SKILL_CANDIDATE = "SKILL_CANDIDATE"
    EXTERNAL_MECHANISM_MOVEMENT = "EXTERNAL_MECHANISM_MOVEMENT"
    MODEL_INTERNAL_RESIDUAL = "MODEL_INTERNAL_RESIDUAL"
    ESCALATION_CANDIDATE = "ESCALATION_CANDIDATE"
    SAFE_STOP_BOUNDARY = "SAFE_STOP_BOUNDARY"
    UNRESOLVED = "UNRESOLVED"
```

Additional frozen records:

- `TomographyProbeSpec`
- `TomographyStudy`
- `TomographyOutcome`
- `TomographyAssessment`
- `TomographyPolicy`

All IDs must be content-addressed from canonical scientific payloads. Records must reject non-finite/nondeterministic values, implicit mutable state, and undeclared changed dimensions.

### 5.2 `tomography_store.py`

Append-only Stage-7 scientific metadata store.

Files:

```text
tomography-studies.jsonl
tomography-outcomes.jsonl
tomography-assessments.jsonl
SHA256SUMS.csv
```

The store references canonical replay request/result IDs instead of storing alternate raw responses.

Validation requires:

- referenced root failure exists;
- referenced mechanism/hypothesis exists where required;
- referenced replay requests/results are canonical;
- parent state and failure lineage match;
- partition contamination is forbidden;
- logical IDs are immutable;
- manifests detect tampering;
- no outcome may silently rewrite a prior scientific conclusion.

### 5.3 `tomography_eligibility.py`

Deterministic zero-call admission and classification.

A failure/mechanism region may enter Stage 7 when one or more of these are true:

- autopsy identifies a Stage-7 divergence class;
- Stage 3/4 evidence leaves tool/skill/verifier/recovery ownership unresolved;
- Stage 5 operating-surface evidence shows a persistent residual not explained by prompt/context/cognition parameters;
- Stage 6 identifies a boundary where an external mechanism is decision-relevant;
- historical evidence already contains tool/verifier/recovery contrasts that can be normalized without fresh inference.

Ineligible examples:

- saturated direct-success region with no live ownership decision;
- `FRESH`/`SEALED` development contamination;
- no reconstructable model-visible/tool-visible state;
- question already answered by canonical evidence;
- proposed probe cannot change a named V3 decision.

Output statuses:

- `ELIGIBLE`
- `ANSWERED_BY_EXISTING_EVIDENCE`
- `NO_DECISION_CHANGING_PROBE`
- `INSUFFICIENT_REPLAY_STATE`
- `PROTECTED_PARTITION`
- `REQUIRES_PRIOR_LOCALIZATION`

`scan-tomography-eligibility` and `plan-tomography --auto-eligible` must remain `MODEL_CALLS=0`.

### 5.4 `tomography_planner.py`

Selects the smallest set of probes whose possible outcomes can change ownership or the next architectural decision.

Default ordering is **diagnostic, not globally fixed**. Where admissible, the planner prefers contrasts that isolate the earliest unresolved layer:

```text
tool unavailable?
    -> tool supplied
       -> correct tool forced
          -> correct arguments forced
             -> canonical result supplied
                -> interpretation isolated
                   -> verifier feedback isolated
                      -> targeted recovery isolated
                         -> reusable skill isolated
                            -> model/escalation residual
```

The planner must never expand this into an exhaustive Cartesian product.

Required planner properties:

- reuse answered probes at zero calls;
- select no probe whose outcomes cannot change D2/D6/D7/D8/D11/D12;
- retain scientifically necessary negative controls;
- retain one generic retry control only when it can distinguish targeted recovery from stochastic retry;
- bound `max_new_probes` (default 3);
- calculate minimum/expected/worst-case physical calls;
- stop when remaining probes cannot change the current disposition;
- never construct adapters, transports, live tools, or model clients.

### 5.5 `tomography_replay.py`

Compiles each Stage-7 probe through canonical `ReplayRequest(mode=COUNTERFACTUAL)`.

It may compose registered interventions but must preserve leaf fidelity:

- source parent state unchanged except declared dimensions;
- tool schema/menu changes explicit;
- forced tool selection explicit;
- argument substitutions explicit;
- supplied tool result provenance explicit;
- verifier feedback explicit;
- recovery instruction/state delta explicit;
- skill procedure and trigger explicit;
- inference profile unchanged unless cognition is itself part of the registered mechanism under test.

Metadata must include:

- `tomography_study_id`
- `tomography_probe_id`
- `tomography_axis`
- expected discriminating implication;
- reused/new evidence status;
- generic-retry-control flag;
- target decision IDs.

No live tool implementation belongs in this module. Actual execution remains adapter-injected through existing replay execution.

### 5.6 `tomography_analysis.py`

Interprets matched outcomes into ownership distinctions.

The analyzer must distinguish at minimum:

#### Tool capability
Baseline fails; canonical tool result or deterministic tool-equivalent information repairs the same state, while prompt/reasoning controls do not.

Possible result: `TOOL_REQUIRED` or another externally owned mechanism. This does not by itself prove autonomous tool selection capability.

#### Tool selection
Tool is available and capable. Autonomous selection fails, while forced correct selection with otherwise matched state succeeds.

Possible result: `TOOL_SELECTION_DEFICIT`.

#### Tool arguments
Correct tool is selected. Autonomous arguments fail, while canonical arguments succeed.

Possible result: `TOOL_ARGUMENT_DEFICIT`.

#### Tool interpretation
Correct tool and arguments execute successfully. Raw/canonical result is present, but model interpretation fails; an interpretation scaffold/verifier repairs it.

Possible result: `TOOL_INTERPRETATION_DEFICIT`.

#### Verifier sufficiency
Generation produces a verifier-detectable defect. Deterministic feedback plus targeted correction repairs the same state at lower cost/complexity than additional general cognition.

Possible result: `VERIFIER_SUFFICIENT` and an external mechanism earning `MOVEMENT` if matched causal requirements are satisfied.

#### Recovery sufficiency
A targeted recovery treatment tied to observed failure state succeeds while matched generic retry does not materially outperform baseline.

Possible result: `RECOVERY_SUFFICIENT`.

#### Skill candidate
A registered reusable procedure repairs multiple eligible instances/structural neighbors with stable triggers and known stop conditions. One instance is insufficient.

Possible result: `SKILL_CANDIDATE`; if causal movement is newly demonstrated, the mechanism re-enters Stages 4–6 before compilation.

#### Model-internal residual
Admissible deterministic/tool/skill/verifier/recovery alternatives fail or are ruled out by valid existing evidence, and the residual remains attributable to model cognition.

Possible result: `MODEL_INTERNAL_RESIDUAL`, which may qualify D11 analysis but does not automatically authorize fine-tuning.

#### Escalation or safe stop
Escalation is considered only after cheaper owners fail or cannot meet the requirement. Safe stop is preferred when the action should not proceed without capability/evidence/authority that is unavailable.

### 5.7 `tomography_lab.py`

Thin orchestration layer.

Responsibilities:

1. validate canonical stores;
2. resolve one stored Stage-7 study;
3. obtain the next bounded plan;
4. compile canonical replay requests;
5. execute only through injected replay adapters;
6. append canonical replay outcomes;
7. append Stage-7 scientific outcomes;
8. analyze ownership/disposition;
9. emit next plan/stop reason;
10. return child failure snapshots generated by failed probes.

It must not infer arbitrary treatments, construct live transports, or contain provider-specific tool logic.

## 6. Generic retry control

Stage 7 treats repeated generic retry as a scientific control, not a recovery strategy.

Rules:

- no third blind retry simply because a second attempt failed;
- a generic retry is schedulable only if stochasticity remains a live competing explanation or it is required to estimate the causal value of targeted recovery;
- its state, prompt, tools, inference profile, and seed policy must be explicitly registered;
- successful generic retry does not erase the original failure;
- generic-retry success weakens claims that a targeted recovery mechanism was necessary;
- generic-retry failure strengthens targeted recovery only when the targeted arm succeeds under matched conditions.

## 7. Tool tomography ladder

Tool failure is decomposed into observable stages:

```text
T0  capability exists?
T1  tool available to model?
T2  correct tool selected?
T3  arguments valid/correct?
T4  tool execution successful?
T5  result preserved/provenanced?
T6  result interpreted correctly?
T7  candidate action derived correctly?
T8  verifier/postcondition accepts?
T9  failure recovery succeeds?
```

The earliest observed failing transition becomes the next diagnostic boundary. Later stages are not tested until earlier prerequisites are either satisfied or supplied as a controlled counterfactual.

This prevents "tool use failed" from collapsing multiple independent defects into one label.

## 8. Skill qualification

A skill is a reusable scientific object, not a long prompt.

Minimum skill contract:

- `skill_id` / version;
- observable trigger predicate;
- allowed task/state region;
- required evidence/state;
- procedure steps;
- allowed tools;
- decision rules;
- verifier/postconditions;
- stop condition;
- recovery/escalation behavior;
- known negative-transfer boundary;
- source mechanism/evidence lineage.

A Stage-7 result may nominate a skill candidate, but promotion requires evidence beyond one local fixture. Newly discovered skill mechanisms follow the Stage-4/5/6 loop before Stage 8 compilation.

## 9. Verifier and recovery decomposition

Stage 7 must explicitly separate:

```text
GENERATION
  -> DETECTION
     -> DIAGNOSIS
        -> CORRECTION PROPOSAL
           -> AUTHORIZATION
              -> EXECUTION
                 -> FINAL VERIFICATION
```

A verifier may own detection without owning correction. Recovery may own correction strategy without owning authorization. System policy may own authorization even if the model proposes the repair.

Scientific outcomes must identify which transition moved and which remained unresolved.

## 10. Stage-4/5/6 feedback loop

This is a hard architectural gate.

When Stage 7 discovers a new external mechanism that earns causal `MOVEMENT`, it does **not** proceed directly to Stage 8.

It re-enters:

1. **Stage 4 — localization/ablation**: prove which tool/skill/verifier/recovery component is required, conditional, synergistic, redundant, harmful, etc.;
2. **Stage 5 — operating-surface deepening**: characterize dose/representation/timing/order/trigger/recurrence or other applicable operating dimensions;
3. **Stage 6 — neighborhood generalization**: test whether the mechanism survives nearby structural variants and identify its boundary.

Only after that loop can Stage 8 evaluate durable capability compilation.

Exceptions require an explicit evidence-backed reason that the mechanism was already localized and generalized by prior canonical evidence. The exception itself must be auditable.

## 11. Promotion and disposition rules

Stage 7 may produce ownership/disposition evidence and may cause a newly demonstrated mechanism to earn `MOVEMENT` under existing causal promotion rules.

Stage 7 may **not** emit `CERTIFIED`.

Stage 7 must not manufacture `TIER_CANDIDATE` solely from tomography. `TIER_CANDIDATE` remains tied to generalized evidence after the appropriate Stage-6 neighborhood gate.

Disposition is separate from promotion:

- disposition says **who/what appears to own the residual**;
- promotion says **how strong/generalized the mechanism evidence is**.

This separation prevents a correct ownership label from being mistaken for production readiness.

## 12. Historical zero-call bootstrap

Historical Stage-7 planning consumes existing replay/causal/surface/mutation evidence without inference.

The bootstrap must:

1. validate the canonical replay registry;
2. identify failure families with Stage-7 divergence/ownership evidence;
3. reuse completed historical tool/verifier/recovery contrasts where reconstructable;
4. reject questions already answered;
5. reject unreconstructable probes;
6. produce eligible study plans or an explicit zero-call boundary status.

Acceptable zero-call boundary statuses include:

- `NO_ELIGIBLE_TOMOGRAPHY_STUDIES`
- `ALL_STAGE7_DECISIONS_ALREADY_ANSWERED`
- `INSUFFICIENT_REPLAY_STATE`
- `REQUIRES_PRIOR_LOCALIZATION`

No boundary status may silently construct Qwen, Ollama, HTTP clients, live tools, or connector transports.

## 13. CLI surfaces

Required safe surfaces:

```text
scan-tomography-eligibility
plan-tomography --study-id <id>
plan-tomography --auto-eligible
show-tomography-study --study-id <id>
show-tomography-assessment --study-id <id>
```

All commands above are zero-call planning/query surfaces.

Any future executable Stage-7 CLI must require explicit execution authorization and must reuse the same replay execution authorization boundary already established by the capability-ratchet system. Planning must never imply execution permission.

## 14. Public API

Stable public contracts should expose only the objects required by external orchestration/tests. At minimum:

- `TomographyAxis`
- `TomographyDisposition`
- `TomographyPolicy`
- `TomographyProbeSpec`
- `TomographyStudy`
- `TomographyOutcome`
- `TomographyAssessment`
- `TomographyEvidenceStore`
- `TomographyPlanner`
- `TomographyReplayCompiler`
- `TomographyAnalyzer`
- `TomographyLab`
- deterministic eligibility/auto-planning entry point

Internal helper classes remain private unless another subsystem actually needs them.

## 15. Permanent audit

Extend the permanent V3 replay-foundation audit to verify Stage 7 cannot silently regress.

Required audit assertions:

- existing Stage-7 divergence classes remain present;
- existing architecture owners remain present;
- Stage-7 public contracts exist;
- zero-call auto-planning exists;
- auto-planning constructs no live model/tool/network transport;
- no independent executor/transport was added to Stage 7;
- canonical replay linkage is enforced;
- generic third-retry logic is absent;
- targeted recovery requires explicit changed state;
- tool capability/selection/arguments/interpretation remain separable;
- verifier and recovery remain separable;
- `FRESH`/`SEALED` contamination is rejected;
- Stage-7 cannot emit `CERTIFIED`;
- newly discovered `MOVEMENT` mechanisms are routed back through Stage 4/5/6 unless prior generalized evidence is explicitly referenced;
- Stage-7 source/tests/workflow cannot silently disappear.

## 16. Development/preflight tests

All implementation validation before real experiments uses deterministic fake adapters and planted fixtures.

The planted matrix must include at least:

1. **Tool capability:** baseline failure; supplied correct result succeeds.
2. **Tool selection:** autonomous wrong selection fails; forced correct selection succeeds.
3. **Tool arguments:** selected correct tool with bad arguments fails; canonical arguments succeed.
4. **Tool interpretation:** correct result supplied; raw interpretation fails; bounded interpretation/verifier treatment succeeds.
5. **Verifier detection only:** verifier catches the defect but no recovery is provided; outcome remains failure.
6. **Targeted recovery:** verifier feedback + targeted repair succeeds.
7. **Generic retry negative control:** blind retry fails while targeted recovery succeeds.
8. **Generic retry confound:** blind retry also succeeds, preventing overclaim that targeted recovery was necessary.
9. **Skill candidate:** same registered procedure succeeds on multiple admissible instances; one planted boundary instance fails.
10. **Model-internal residual:** admissible external mechanisms fail, preserving the residual rather than fabricating an owner.
11. **Escalation reference:** stronger-reference success changes D11/D2 evidence but is not relabeled as Qwen success.
12. **Safe stop:** insufficient authority/evidence correctly terminates without forced execution.
13. **Child snapshot:** a failed tomography replay creates/links a child failure snapshot.
14. **Partition protection:** synthetic/development treatment cannot consume `FRESH`/`SEALED` evidence.
15. **Zero-call bootstrap:** construction of Qwen/Ollama/httpx/socket/live-tool entry points is booby-trapped and planning remains green.

## 17. Regression requirements

Stage-7 completion requires:

- dedicated Stage-7 unit/integration suite green;
- full capability-ratchet suite green;
- explicit V2 regression green;
- full repository regression green on Linux;
- repository matrix green on supported Linux Python versions and Windows Python 3.14;
- evidence privacy green;
- permanent replay-foundation audit green;
- historical Stage-7 zero-call bootstrap produces a valid plan or valid boundary status;
- final Stage-7 invariants green;
- clean tracked tree in the completion job;
- `MODEL_CALLS=0` for development/historical planning verification.

Warnings may be recorded separately but cannot be silently promoted to blockers unless they affect scientific validity, portability, privacy, or future compatibility.

## 18. Completion artifact

A dedicated Stage-7 completion workflow must emit an immutable summary equivalent to:

```json
{
  "STAGE7_COMPLETION": "PASS",
  "MODEL_CALLS": 0,
  "eligible_studies": 0,
  "historical_stage7_status": "NO_ELIGIBLE_TOMOGRAPHY_STUDIES",
  "tool_axis_contract": true,
  "verifier_recovery_separation": true,
  "generic_third_retry_forbidden": true,
  "stage456_feedback_gate": true,
  "forgotten_count": 0,
  "orphan_assets": 0,
  "privacy_matches": 0
}
```

Exact counts/status depend on the historical corpus and must not be hardcoded unless independently proven by the completion run.

The workflow uploads its zero-call eligibility, audit, assessment/boundary output, privacy scan, and completion summary as retained evidence.

## 19. Stage-8 handoff

Stage 8 receives only mechanisms/residuals whose ownership evidence is sufficiently resolved.

Possible handoffs:

- generalized deterministic/tool/skill/verifier/recovery mechanism -> capability compilation;
- model-internal residual -> Stage 9 fine-tuning qualification candidate;
- routing-relevant conditional owner -> Stage 10 controller extraction candidate;
- unresolved residual -> remain in Stage 7 or re-enter earlier causal stages;
- escalation candidate -> explicit escalation policy research;
- unsafe/unavailable capability -> safe-stop boundary.

Stage 8 may not treat a Stage-7 success as generalized merely because the responsible owner is known.

## 20. Explicit non-goals

Stage 7 does not:

- build a general-purpose tool framework;
- invent new MCP/tool transports;
- replace `ReplayExecutor`;
- create another replay registry;
- perform exhaustive tool menus or Cartesian testing;
- repeatedly retry failures until one passes;
- promote a one-off successful recovery to a reusable skill;
- infer hidden chain-of-thought;
- consume protected confirmation evidence for development;
- authorize real inference during implementation/preflight;
- certify production behavior.

## 21. Design decision

Implement Stage 7 as a **dedicated tomography scientific layer over the existing capability-ratchet replay kernel**.

Do not merge the new responsibilities into `autopsy.py`, `interventions.py`, or `mechanisms.py` beyond narrowly required integration hooks. Those modules remain the generic causal diagnosis/intervention/localization layer; Stage 7 owns the specialized decomposition of tool, skill, verification, recovery, escalation, and model-residual responsibility.

Do not generalize the project into a universal experiment DSL at this stage. If repeated Stage-7 and later-stage structures prove a common abstraction is valuable, extract it from demonstrated duplication rather than pre-building it.
