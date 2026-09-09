# V3 Stage-8 Capability Compilation — Design Specification

## Status

Owner-approved continuation of the Universal Capability Ratchet V3 governing design. Stage 7 is closed at exact head `356f60adbbf41641a799ef0f1ccbb7c948d2fe36`; its historical result is `NO_ELIGIBLE_TOMOGRAPHY_STUDIES` with `MODEL_CALLS=0`.

Stage 8 converts already-localized and already-generalized repairs into the cheapest durable capability owner. It does **not** discover new mechanisms, rerun models, certify deployment, or bypass Stages 4–6.

---

## 1. Primary decision

Stage 8 answers D12:

> Can an already-generalized repair be converted into a durable, versioned, rollback-safe capability owned by the cheapest mechanism supported by canonical evidence?

The output is a compiled capability or an explicit non-compilation disposition. Zero eligible historical candidates is a valid scientific boundary.

---

## 2. Non-negotiable laws

1. **Generalization first.** `INSTANCE_PATCH` is never compilable. A normal candidate must reference a canonical Stage-6 `GeneralizationProfile` classified at least `LOCAL_MECHANISM`.
2. **No Stage-7 bypass.** A Stage-7 disposition, outcome, or MOVEMENT event alone is insufficient. New Stage-7 mechanisms must return through Stage 4 → Stage 5 → Stage 6 before normal Stage-8 admission.
3. **Prior generalized evidence is explicit.** A mechanism predating the current Stage-6 store may be admitted only through a separately identified, canonical, auditable prior-generalization reference; never through an unverified metadata flag.
4. **Cheapest supported owner wins.** Select the earliest evidence-supported owner in the governing V3 order unless canonical evidence explicitly rules it out.
5. **No inference.** Scanning, planning, compilation, catalog export, validation, and historical completion are `MODEL_CALLS=0`. Stage 8 constructs no model adapter, HTTP client, socket, MCP transport, tool executor, or replay executor.
6. **Compilation is not certification.** Stage 8 cannot emit `CERTIFIED`, activate a production route, consume FRESH/SEALED evidence for development, or declare fresh transfer.
7. **Trigger required.** A durable artifact must have an observable trigger contract. Hidden family/oracle labels are forbidden.
8. **Negative-transfer boundary required.** The artifact must preserve tested negative-transfer/boundary evidence. If no negative transfer was observed, the artifact must explicitly state the tested region rather than silently claim a global boundary.
9. **Rollback/version required.** Every compiled artifact has a stable capability key, immutable version, previous-version lineage where applicable, and an explicit rollback target or `DISABLE` rollback action for version 1.
10. **Source evidence remains canonical.** Stage 8 stores references/hashes only; it never duplicates raw model payloads or becomes an alternate replay source of truth.
11. **No complexity without rent.** If two owners are evidence-equivalent, the cheaper owner is selected. A more expensive owner requires a canonical exclusion reason for every cheaper viable owner.
12. **Negative evidence terminates cleanly.** Missing trigger, unresolved negative-transfer boundary, conflicting ownership, insufficient generalization, or unavailable source evidence yields an explicit disposition and next requirement; it does not trigger a retry.

---

## 3. Durable owner order

`CompilationKind` follows the governing V3 order exactly:

1. `DETERMINISTIC_RULE`
2. `STATE_REPRESENTATION`
3. `FORMATTER_PARSER_VALIDATOR`
4. `TOOL_POLICY`
5. `SKILL_POLICY`
6. `REASONING_POLICY`
7. `VERIFIER_RECOVERY_POLICY`
8. `FINE_TUNE_CANDIDATE`
9. `ESCALATION_POLICY`
10. `SAFE_STOP_BOUNDARY`

This is a cost/complexity precedence, not a global quality ranking.

`FINE_TUNE_CANDIDATE`, `ESCALATION_POLICY`, and `SAFE_STOP_BOUNDARY` are terminal Stage-8 handoff kinds; they do not mean weight training, escalation execution, or deployment occurs in Stage 8.

---

## 4. Scientific contracts

### 4.1 `CompilationEligibilityStatus`

- `ELIGIBLE`
- `INSTANCE_PATCH`
- `MISSING_GENERALIZATION`
- `MISSING_TRIGGER_CONTRACT`
- `MISSING_NEGATIVE_TRANSFER_CONTRACT`
- `CONFLICTING_OWNERSHIP`
- `PROTECTED_PARTITION`
- `REQUIRES_STAGE456_FEEDBACK`
- `SOURCE_EVIDENCE_INVALID`
- `ALREADY_COMPILED`

### 4.2 `CompilationDisposition`

- `COMPILED`
- `FINE_TUNE_CANDIDATE`
- `ESCALATION_CANDIDATE`
- `SAFE_STOP_BOUNDARY`
- `HARD_BOUNDARY`
- `REQUIRES_MORE_EVIDENCE`
- `INELIGIBLE`

Disposition is separate from V3 `PromotionState`; no Stage-8 disposition equals `MOVEMENT`, `TIER_CANDIDATE`, or `CERTIFIED`.

### 4.3 `CompilationCandidate`

Immutable, content-addressed candidate containing at minimum:

- candidate ID;
- failure snapshot ID;
- mechanism ID;
- generalization profile ID or explicit prior-generalized evidence reference;
- generalization class;
- source mechanism-label IDs;
- source evidence refs;
- evidence-supported compilation kinds;
- explicit excluded cheaper kinds and canonical evidence reasons;
- observable trigger contract;
- compiled payload/procedure/configuration template;
- verifier/postcondition contract where applicable;
- negative-transfer boundary;
- tested region description;
- rollback action/target;
- source partition;
- D12 decision ID.

### 4.4 `CompilationPlan`

Deterministic plan containing:

- candidate ID;
- selected cheapest kind;
- rejected cheaper kinds with reasons;
- source evidence refs;
- zero physical/model calls;
- expected disposition;
- plan ID.

### 4.5 `CompiledCapability`

Immutable versioned artifact containing:

- stable `capability_key` derived from mechanism + trigger identity;
- `capability_id` derived from complete version payload;
- integer version ≥ 1;
- selected `CompilationKind`;
- mechanism/generalization lineage;
- observable trigger contract;
- durable payload/procedure/config;
- verifier/postconditions;
- negative-transfer boundary and tested region;
- source evidence refs and source hashes;
- rollback target/action;
- `deployment_allowed=False` in Stage 8;
- `fresh_validation_required=True` for external compiled capability;
- next-stage handoff.

A version update may not rewrite a prior capability row. It appends a new version referencing the previous capability ID.

---

## 5. Evidence admission

Normal admission requires all of:

1. canonical replay store validates;
2. canonical causal store validates when mechanism labels are required;
3. canonical mutation store validates;
4. source failure is DEVELOPMENT/HISTORICAL, never FRESH/SEALED;
5. generalization profile references the same mechanism/failure lineage;
6. profile classification is one of `LOCAL_MECHANISM`, `REGION_MECHANISM`, `CROSS_REGION_MECHANISM`, `PROMOTION_CANDIDATE`;
7. protected failures are absent;
8. trigger is observable and contains no forbidden oracle/family keys;
9. negative-transfer contract is explicit;
10. at least one compilation kind is supported by canonical evidence.

`INSTANCE_PATCH` and missing Stage-6 profile are non-compilable unless the explicit prior-generalized-evidence lane is used.

The prior-generalized-evidence lane must carry an immutable source reference, source hash, generalization classification/equivalent scope, trigger, tested region, negative-transfer boundary, and mechanism lineage. It cannot be synthesized from a Stage-7 assessment.

---

## 6. Owner derivation

Evidence compilation maps localized mechanisms to supported durable owners without language-model inference.

Default evidence mappings:

- deterministic computation/system transform → `DETERMINISTIC_RULE`;
- representation/context/delivery mechanism with a stable observable trigger → `STATE_REPRESENTATION`;
- contract/interface mechanism whose repair is parser/formatter/validator-owned → `FORMATTER_PARSER_VALIDATOR`;
- tool mechanism → `TOOL_POLICY`;
- reusable procedural mechanism → `SKILL_POLICY`;
- cognition mechanism with bounded operating-surface evidence → `REASONING_POLICY`;
- verifier/recovery mechanism → `VERIFIER_RECOVERY_POLICY`;
- Stage-7 `MODEL_INTERNAL_RESIDUAL` only after Stage-4/5/6 feedback → `FINE_TUNE_CANDIDATE`;
- Stage-7 `ESCALATION_CANDIDATE` only after Stage-4/5/6 feedback or explicit generalized prior evidence → `ESCALATION_POLICY`;
- Stage-7 `SAFE_STOP_BOUNDARY` only after required boundary evidence → `SAFE_STOP_BOUNDARY`.

Prompt/context mechanisms that cannot be expressed as a stable observable representation/skill trigger remain `REQUIRES_MORE_EVIDENCE`; Stage 8 does not invent a prompt policy from prose.

When more than one kind is supported, the planner selects the cheapest unless every cheaper kind is excluded by explicit evidence.

---

## 7. Compilation output semantics

Compilation transforms evidence into a durable artifact; it does not execute the artifact.

Examples:

- deterministic rule: pure rule/transform identifier + parameters + postcondition;
- representation: source state selectors + representation schema + placement/delivery contract;
- formatter/parser/validator: schema/parser/validator identifier + contract;
- tool policy: observable trigger + allowed tool + selection/argument/result/verifier policy;
- skill policy: versioned trigger + procedure + allowed tools + stop/recovery/verifier;
- reasoning policy: observable trigger + bounded reasoning/temperature region + negative-transfer veto;
- verifier/recovery: detection → correction authorization → final verification contract;
- fine-tune candidate: immutable handoff reference, not training;
- escalation: trigger + escalation boundary/reference, not an external model call;
- safe-stop: trigger + stop reason + permitted recovery/escalation boundary.

The compiler rejects payloads containing raw-response/prompt/message duplication, credentials, executable network clients, hidden oracle/family routing keys, or deployment activation flags.

---

## 8. Persistence

Stage-8 metadata store:

```text
compilation/
├── compilation-candidates.jsonl
├── compilation-decisions.jsonl
├── compiled-capabilities.jsonl
└── SHA256SUMS.csv
```

Rules:

- append-only logical records;
- content-addressed IDs;
- immutable prior versions;
- duplicate logical IDs must be byte-identical;
- no silent overwrite;
- source references validated against canonical stores;
- manifest hashes verified;
- FRESH/SEALED contamination rejected;
- raw model payload duplication rejected.

A deterministic export produces the required V3 view:

`compiled-capabilities.json`

The view contains ordered capability versions, source IDs/hashes, catalog hash, and `MODEL_CALLS=0`. It is derived, not a competing source of truth.

---

## 9. Zero-call planning and historical boundary

Required CLI/query surface:

- `scan-compilation-eligibility`
- `plan-compilation --candidate-id <id>`
- `plan-compilation --auto-eligible`
- `show-compiled-capability --capability-id <id>`
- `export-compiled-capabilities --output <path>`

All commands are deterministic and construct no model/tool/replay executor.

Valid historical terminal statuses include:

- `NO_ELIGIBLE_COMPILATION_CANDIDATES`
- `COMPILATION_PLAN_READY`
- `ALL_ELIGIBLE_CAPABILITIES_COMPILED`
- `REQUIRES_STAGE456_FEEDBACK`
- `INSUFFICIENT_GENERALIZATION_EVIDENCE`

The current historical corpus is expected to be capable of returning `NO_ELIGIBLE_COMPILATION_CANDIDATES` because Stage 6 found no eligible historical MOVEMENT mechanism. This expectation is not hardcoded as a PASS condition; the status must be derived from canonical evidence.

---

## 10. Permanent audit invariants

The permanent V3 audit must prove:

1. Stage-8 public contracts/files/CLI/workflow exist;
2. owner order exactly matches the governing V3 order;
3. `INSTANCE_PATCH` cannot compile;
4. Stage-7-only evidence cannot bypass Stage 4/5/6;
5. FRESH/SEALED cannot enter development compilation;
6. scan/plan/compile/export paths are zero-call and construct no executor/transport;
7. owner selection chooses the cheapest supported kind;
8. a more expensive kind requires explicit exclusion evidence for cheaper supported kinds;
9. trigger contract is observable and oracle/family-free;
10. negative-transfer/tested-region contract is mandatory;
11. rollback and version lineage are mandatory;
12. Stage 8 cannot emit CERTIFIED or set `deployment_allowed=True`;
13. compiled catalog is derived deterministically from append-only records;
14. source mechanism/generalization evidence remains canonical and referenced, not copied;
15. Stage-8 source/tests/workflow cannot silently disappear.

---

## 11. Synthetic/preflight matrix

At minimum tests prove:

1. `INSTANCE_PATCH` rejected;
2. LOCAL mechanism with complete trigger/boundary admitted;
3. REGION/CROSS_REGION/PROMOTION candidate admitted;
4. Stage-7 assessment without generalized evidence rejected with `REQUIRES_STAGE456_FEEDBACK`;
5. protected partition rejected;
6. hidden family/oracle trigger key rejected;
7. deterministic + tool both supported → deterministic selected;
8. representation + skill both supported → representation selected;
9. tool selected only when cheaper owners are unsupported/excluded;
10. reasoning policy requires operating-surface evidence reference;
11. fine-tune handoff requires model-internal residual + generalized evidence;
12. escalation/safe-stop are handoffs, never executions;
13. version 1 requires `DISABLE` rollback or explicit rollback target;
14. version 2 references immutable version 1;
15. duplicate logical ID with changed bytes rejected;
16. raw model payload duplication rejected;
17. compiled artifact has `deployment_allowed=False`;
18. catalog export is stable under record-order-independent reads where logical content is identical;
19. zero-call historical bootstrap remains model/network/executor-free;
20. empty eligible set produces a valid empty `compiled-capabilities.json` and scientific boundary status.

---

## 12. Public API

Minimum exports:

- `CompilationKind`
- `CompilationEligibilityStatus`
- `CompilationDisposition`
- `CompilationCandidate`
- `CompilationPlan`
- `CompiledCapability`
- `CompilationPolicy`
- `CompilationEvidenceStore`
- `CompilationEligibilityScanner`
- `CompilationPlanner`
- `CapabilityCompiler`
- `plan_eligible_compilation`

No executor is part of the Stage-8 public API.

---

## 13. Completion gate

Stage 8 is complete when a fresh exact-head workflow proves:

- dedicated Stage-8 suite green;
- full capability-ratchet suite green;
- explicit V2 regression green;
- full Linux repository regression green;
- Linux Python 3.11/3.12/3.14 and Windows 3.14 matrix green;
- privacy scan has 0 matches;
- historical replay corpus reconstructs with `MODEL_CALLS=0`;
- permanent Stage-5/6/7/8 audit has `forgotten_count=0` and `orphan_asset_count=0`;
- historical Stage-8 scan/auto-plan returns a valid evidence-derived status with `MODEL_CALLS=0`;
- deterministic `compiled-capabilities.json` export validates;
- no Stage-8 CERTIFIED event exists;
- clean tracked tree;
- completion artifact uploaded.

If no eligible historical generalized mechanism exists, Stage 8 closes as a **compiler capability boundary**, not as missing research. No synthetic mechanism may be promoted into the historical catalog merely to avoid an empty result.

---

## 14. Stage-9 handoff

Only `FINE_TUNE_CANDIDATE` artifacts with generalized model-internal residual evidence enter Stage 9. External compiled capabilities proceed toward Stage 10/11 routing and fresh validation; escalation/safe-stop artifacts become routing boundaries. An empty Stage-8 historical catalog does not block Stage 9 infrastructure design, but it does mean there is no historical fine-tune candidate to train.
