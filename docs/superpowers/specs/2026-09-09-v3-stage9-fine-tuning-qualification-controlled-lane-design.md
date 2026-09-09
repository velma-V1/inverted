# V3 Stage 9 — Fine-Tuning Qualification and Optional Controlled Lane

## Purpose

Stage 9 answers one narrow question: **has the evidence actually earned a fine-tuning experiment?** Fine-tuning is not a default repair, a retry mechanism, or a substitute for unresolved system ownership.

The unit of progress is a resolved D11 decision: qualify a bounded controlled tuning lane, reject fine-tuning as unjustified, demand more evidence, route to Stage 10, escalate, or establish a safe-stop boundary.

## Scientific boundary

Stage 9 consumes only canonical evidence that survived the earlier ratchet. Its preferred entry is a Stage-8 compilation candidate routed as `FINE_TUNE_CANDIDATE`; the underlying ownership must be model-internal and cheaper owners must already be resolved or explicitly falsified. Stage-7 `MODEL_INTERNAL_RESIDUAL` can support the handoff, but Stage-7 evidence without Stage-4→5→6 generalization cannot bypass the Stage-8 gate.

Qualification is distinct from training, improvement, certification, deployment, and fresh/sealed confirmation.

## Governing laws

1. Existing evidence first; historical/development planning performs zero model calls.
2. Fine-tuning is downstream of cheaper-owner exclusion. Tool, skill, verifier, recovery, representation, deterministic, and routing deficits may not be relabeled as fine-tuning deficits.
3. A one-off failure cannot qualify. The failure pattern must recur across independent canonical instances.
4. Generalization evidence is mandatory. `INSTANCE_PATCH` evidence is ineligible.
5. `FRESH` and `SEALED` partitions are protected from qualification and dataset construction.
6. Training and evaluation membership must be disjoint by failure lineage and content hash.
7. Targets must be observable contract/output evidence. Hidden chain-of-thought, private reasoning, raw forensic thinking, and hidden oracle state are forbidden training targets.
8. Oracle/scoring material may be referenced for evaluation provenance but may not leak into model-visible training inputs or targets unless it is itself an explicitly observable allowed target.
9. Every dataset row retains canonical replay/failure lineage and source hashes.
10. Qualification does not authorize training. Every controlled-lane plan is `NOT_AUTHORIZED` by default.
11. Stage 9 cannot certify or deploy.
12. A future training lane must use an explicitly authorized injected adapter; Stage 9 does not create a second model transport, trainer framework, or MCP execution layer.
13. Tuned candidates must still pass Stage 11 fresh transfer, regression, and sealed confirmation before certification.
14. Negative evidence must change D11: reject tuning, require more evidence, route escalation, or safe-stop.
15. No false precision: recurrence is a gate, not a claim of statistical sufficiency.

## Contracts

### `FineTuningEligibilityStatus`

- `ELIGIBLE`
- `ALREADY_QUALIFIED`
- `CHEAPER_OWNER_UNRESOLVED`
- `INSUFFICIENT_MODEL_OWNERSHIP_EVIDENCE`
- `INSUFFICIENT_REPEATED_PATTERN`
- `INSUFFICIENT_GENERALIZATION_EVIDENCE`
- `INSUFFICIENT_TRAINING_EXAMPLES`
- `DATASET_LEAKAGE_RISK`
- `PROTECTED_PARTITION`
- `UNSUPPORTED_SOURCE`
- `NO_CANDIDATE`

### `FineTuningDisposition`

- `QUALIFY_CONTROLLED_LANE`
- `NOT_JUSTIFIED`
- `REQUIRES_MORE_EVIDENCE`
- `ROUTE_STAGE10`
- `ROUTE_ESCALATION`
- `SAFE_STOP`
- `ALREADY_QUALIFIED`

These are D11 dispositions, not promotion states. They must remain disjoint from `MOVEMENT`, `TIER_CANDIDATE`, and `CERTIFIED`.

### `FineTuningPlanStatus`

- `PLANNED`
- `NOT_JUSTIFIED`
- `REQUIRES_MORE_EVIDENCE`
- `ALREADY_QUALIFIED`

### `FineTuningPolicy`

Default policy:

- schema version `v3-stage9-v1`
- decision ID `D11`
- protected partitions enforced
- model-internal residual required
- cheaper owners resolved required
- repeated failure pattern required
- minimum independent recurrence gate: 2 failures
- generalization evidence required
- disjoint train/eval required
- observable targets required
- oracle leakage forbidden
- regression suite required
- certification disabled
- deployment disabled
- training authorization disabled by default
- development model-call budget 0

The recurrence count is only an admissibility floor. Dataset sufficiency remains an explicit evidence decision.

## Canonical objects

### `FineTuningCandidate`

Content-addressed D11 candidate containing:

- Stage-8 candidate ID
- mechanism ID
- independent failure snapshot IDs
- generalization evidence refs
- optional Stage-7 assessment refs
- explicit cheaper-owner exclusions
- observable trigger and allowed region
- negative-transfer boundary
- source hashes
- partition
- model profile / inference regime identity
- regression evidence refs

It must reject protected partitions, unresolved cheaper owners, non-model ownership, a one-instance pattern, absent generalization, and non-finite/nondeterministic payloads.

### `FineTuningExample`

A content-addressed dataset row containing:

- canonical failure snapshot ID
- canonical replay/evidence refs
- model-visible input reference + hash
- observable target reference + hash
- role (`TRAIN` or `EVAL`)
- partition
- source model profile
- allowed target type
- exclusion/leakage metadata

The object stores references and hashes rather than copying raw model-visible/forensic/oracle payloads into Stage-9 metadata.

### `FineTuningDataset`

A deterministic package containing candidate ID, train/eval example IDs, regression refs, source hashes, and a stable dataset hash. Train/eval sets must be disjoint by example ID, failure lineage, and source content hash.

### `FineTuningQualification`

Records the D11 outcome, evidence refs, dataset ID when qualified, unresolved risks, route, and the permanent facts that training/certification/deployment remain unauthorized.

### `ControlledTuningPlan`

A qualified-but-not-authorized experiment plan containing:

- qualification and dataset IDs
- frozen base model/profile ID
- objective
- bounded hyperparameter envelope
- physical training/call budget ceiling
- preregistered evaluation and regression suite refs
- abort/stop criteria
- rollback rule
- authorization status `NOT_AUTHORIZED`
- projected development model calls = 0

The plan contains no provider client, Ollama client, HTTP client, socket, trainer transport, credential, or live tool construction.

## Evidence store

Stage-9 metadata is append-only and references canonical earlier evidence.

```text
fine-tuning-candidates.jsonl
fine-tuning-datasets.jsonl
fine-tuning-qualifications.jsonl
controlled-tuning-plans.jsonl
SHA256SUMS.csv
```

The store must enforce canonical JSON, immutable logical IDs, manifest integrity, protected-partition vetoes, source existence, no silent rewrite, and no raw response/thinking/oracle duplication.

## Eligibility algorithm

1. Run the deterministic Stage-8 compilation eligibility scan.
2. Consider only `ELIGIBLE` Stage-8 candidates that explicitly support `FINE_TUNE_CANDIDATE`.
3. Require `model_internal_residual=True` and Stage-7 model-internal ownership evidence when declared.
4. Require all cheaper Stage-8 kinds to be excluded with evidence-bearing reasons.
5. Require Stage-6 generalization or a canonical prior-generalization exception already accepted by Stage 8.
6. Group by mechanism/pattern and require at least two independent canonical failure snapshots before qualification.
7. Reject FRESH/SEALED, instance-specific, leakage-risk, missing regression, or unresolved cheaper-owner cases.
8. Do not infer dataset sufficiency merely from recurrence count.

Historical outcomes may legitimately be `NO_ELIGIBLE_FINE_TUNING_CANDIDATES`.

## Dataset compiler

The compiler is deterministic and zero-call. It accepts only registered references. It must:

- preserve source hashes;
- reject duplicated train/eval lineage;
- reject FRESH/SEALED;
- reject raw forensic reasoning / hidden CoT fields;
- reject hidden oracle/scoring-state targets;
- reject prompt/target material embedded directly in Stage-9 metadata when a canonical reference is required;
- emit a stable package hash;
- include regression and negative-transfer references.

No synthetic examples are invented by Stage 9.

## Qualification analyzer

`QUALIFY_CONTROLLED_LANE` requires all of:

- model-internal ownership established;
- cheaper owners resolved;
- repeated independent pattern;
- generalization evidence;
- leakage-safe disjoint dataset;
- observable target contract;
- preregistered regression/negative-transfer suite;
- bounded experiment geometry;
- rollback and abort rules.

Otherwise the analyzer must choose a narrower truthful disposition. Qualification never means the fine tune will work.

## CLI

Zero-call commands:

- `scan-fine-tuning-eligibility`
- `plan-fine-tuning --auto-eligible`
- `show-fine-tuning-candidate --candidate-id <id>`
- `show-fine-tuning-qualification --qualification-id <id>`
- `export-fine-tuning-dataset --candidate-id <id> --output <path>` when a deterministic registered dataset exists

No execution command is introduced in Stage 9. A future controlled training command requires a separate explicit authorization design and injected adapter.

## Public API

Expose at minimum:

- `FineTuningEligibilityStatus`
- `FineTuningDisposition`
- `FineTuningPlanStatus`
- `FineTuningPolicy`
- `FineTuningCandidate`
- `FineTuningExample`
- `FineTuningDataset`
- `FineTuningQualification`
- `ControlledTuningPlan`
- `FineTuningEvidenceStore`
- `FineTuningEligibilityScanner`
- `FineTuningDatasetCompiler`
- `FineTuningPlanner`
- `FineTuningAnalyzer`
- `FineTuningLab`
- deterministic auto-plan entrypoint

## Permanent audit

The permanent V3 audit must prove:

- Stage-9 contracts/public exports/CLI exist;
- development/historical scan and planning are zero-call;
- no trainer/model/live transport is constructed;
- no independent executor exists;
- only model-internal Stage-8 handoffs enter qualification;
- cheaper-owner veto exists;
- one-off failure veto exists;
- generalization gate exists;
- FRESH/SEALED veto exists;
- train/eval disjointness exists;
- hidden reasoning/oracle leakage veto exists;
- observable-target contract exists;
- regression/negative-transfer requirement exists;
- qualification is not training/certification/deployment;
- authorization defaults to `NOT_AUTHORIZED`;
- Stage-11 handoff remains mandatory;
- Stage-9 source/tests/workflow cannot silently disappear.

## Completion gate

Stage 9 is complete when exact-head CI proves:

- dedicated Stage-9 suite green;
- full capability-ratchet green;
- V2 regression green;
- full Linux repo regression green;
- supported Linux Python matrix + Windows 3.14 green;
- privacy scan zero findings;
- permanent audit zero forgotten/orphan contracts;
- historical zero-call eligibility/plan returns a scientifically valid boundary or ready state;
- `MODEL_CALLS=0` for development/historical completion;
- clean tracked tree;
- completion artifact uploaded.

## Stage 10 / 11 handoff

A conditional routing structure discovered while qualifying fine tuning may be handed to Stage 10. A qualified controlled tuning lane remains untrained and uncertified until separately authorized and evaluated. Any resulting tuned candidate must pass Stage 11 fresh transfer, regression, and sealed confirmation before certification or deployment.

## Non-goals

- no general-purpose fine-tuning platform;
- no trainer transport;
- no API-key handling;
- no live model calls in CI;
- no synthetic example generation;
- no hidden-CoT harvesting;
- no use of protected partitions;
- no retry-until-improvement;
- no Stage-9 certification or deployment.
