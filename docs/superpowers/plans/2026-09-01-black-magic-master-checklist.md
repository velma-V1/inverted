# Black-Magic Master Completion Checklist

Base SHA: `19b45314860f2feb7bb561353220eef8d83ba657`
Branch: `build/black-magic-evidence-tests`
Spec: `docs/superpowers/specs/2026-09-01-black-magic-evidence-and-certification-design.md`

## Progression rule

Each stage is built and tested **as a complete vertical experiment**. Do not begin the next stage until the current stage has: complete implementation, full unit/integration coverage, mock/instrument smoke run, evidence-integrity validation, hard-budget validation, hidden-gold validation, and additive-only branch verification.

## Global gates

- [x] Approved architecture spec committed.
- [x] Isolated branch created from exact validated base SHA.
- [x] Harvest, Forge, Test-5, and Test-6 implementation plans committed.
- [ ] Every diff path versus base SHA remains `added`; zero baseline modification/deletion.
- [ ] No hidden-oracle data enters model-visible or pre-score decision paths.
- [ ] Every physical external attempt is counted exactly once; failures/timeouts count.
- [ ] No adapter-internal retries in real configs.
- [ ] Mock evidence is labeled instrument validation and never used for architecture claims.
- [ ] Every evidence packet passes integrity and SHA-256 verification.

---

# A — DECISION MECHANICS HARVEST + SHARED FOUNDATION

Hard cap: **1,200 external actions**.

### Build whole
- [ ] `src/inverted/black_magic/` package foundation complete.
- [ ] Unified external-action budget complete.
- [ ] Lossless evidence store complete.
- [ ] One-reservation/one-attempt model I/O complete.
- [ ] Counterfactual fork/replay + sham controls complete.
- [ ] Metamorphic primitives complete.
- [ ] t-way + ordered-sequence coverage primitives complete.
- [ ] Decision Mechanics fresh case generator complete.
- [ ] DIRECT/CHECKED/INVERTED-style matched decision roles complete.
- [ ] Externalized-correction probe complete.
- [ ] Error-lifecycle tracing complete.
- [ ] Targeted/sham negative-result conversion complete.
- [ ] Mock and real configs complete.
- [ ] Additive Harvest-A validation workflow complete.

### Required case/data coverage
- [ ] shallow/medium/deep dependencies
- [ ] independent/interacting prerequisites
- [ ] locally-correct/globally-wrong traps
- [ ] stale/delayed state
- [ ] misleading success
- [ ] requirement change
- [ ] recoverable/unrecoverable wrong turn
- [ ] preservation traps
- [ ] excessive/insufficient decomposition
- [ ] irrelevant-history pressure
- [ ] checkpoint restoration
- [ ] ambiguous recovery
- [ ] auditor false accept/reject
- [ ] first meaningful and first unrecovered divergence
- [ ] propagation depth and recovery opportunities
- [ ] local/global conflict
- [ ] auditor override value
- [ ] externalized correction role effect
- [ ] targeted repair vs sham causal lift
- [ ] neighbor generalization and regression

### Test whole
- [ ] All Harvest-A/foundation tests GREEN.
- [ ] Mock Harvest A completes end-to-end.
- [ ] Evidence packet integrity GREEN.
- [ ] Prompt/response/call parity GREEN.
- [ ] 1,201-action plan refuses before first call.
- [ ] Hidden-gold tests GREEN.
- [ ] Zero unresolved high-severity instrumentation failures.
- [ ] Branch remains additive-only.
- [ ] **HARVEST A = GREEN**

**LOCK: Do not build Harvest B until HARVEST A = GREEN.**

---

# B — EPISTEMIC MECHANICS HARVEST

Hard cap: **1,200 external actions**.

### Build whole
- [ ] Fresh epistemic case generator complete.
- [ ] Evidence surgery engine complete.
- [ ] Mandatory invariant/boundary metamorphic campaign complete.
- [ ] Targeted/sham repair conversion complete.
- [ ] Cross-factor interaction slice complete.
- [ ] Mock and real configs complete.

### Required coverage
- [ ] complete/partial/irrelevant/stale/contradictory/adversarial evidence
- [ ] forged authority and source ambiguity
- [ ] provenance conflict
- [ ] majority-wrong/minority-correct
- [ ] plausible unsupported claim
- [ ] relevance change after requirement update
- [ ] no-valid-action and required `INSUFFICIENT`
- [ ] remove/restore item
- [ ] freshness-only/provenance-only surgery
- [ ] reorder/ID rename/irrelevant distractor
- [ ] rationale/confidence removal
- [ ] contradiction resolve/create
- [ ] minimal sufficient evidence
- [ ] unnecessary evidence load
- [ ] marginal evidence value
- [ ] provenance/freshness interaction
- [ ] abstention boundary accuracy
- [ ] invariant violation and boundary sensitivity
- [ ] injection/forged-authority exploitability

### Test whole
- [ ] All Harvest-B tests GREEN.
- [ ] Mock Harvest B completes end-to-end.
- [ ] Evidence packet integrity GREEN.
- [ ] 1,201-action plan refuses before first call.
- [ ] Hidden-gold tests GREEN.
- [ ] Zero unresolved high-severity instrumentation failures.
- [ ] Branch remains additive-only.
- [ ] **HARVEST B = GREEN**

**LOCK: Do not build Harvest C until HARVEST B = GREEN.**

---

# C — ACTION MECHANICS HARVEST

Hard cap: **1,200 external actions**.

### Build whole
- [ ] Fresh action/authority case generator complete.
- [ ] Action-surgery engine complete.
- [ ] Chained/ordered risk campaign complete.
- [ ] Targeted/sham repair conversion complete.
- [ ] Mock and real configs complete.

### Required coverage
- [ ] read/write/delete/send/publish/purchase/configure/credential-like effects
- [ ] explicit/ambiguous/expired/revoked permission
- [ ] scope mismatch and least privilege
- [ ] irreversible actions
- [ ] chained risk and delayed effects
- [ ] deceptive success
- [ ] request/action mismatch
- [ ] legitimate high-impact action
- [ ] overblocking
- [ ] action-before-verification
- [ ] permission change mid-sequence
- [ ] safe rollback vs unsafe retry
- [ ] understanding-correct/action-wrong separation
- [ ] authority/scope/escalation/order errors
- [ ] preventable damage and repair lift

### Test whole
- [ ] All Harvest-C tests GREEN.
- [ ] Mock Harvest C completes end-to-end.
- [ ] Evidence packet integrity GREEN.
- [ ] 1,201-action plan refuses before first call.
- [ ] Hidden-gold tests GREEN.
- [ ] Zero unresolved high-severity instrumentation failures.
- [ ] Branch remains additive-only.
- [ ] **HARVEST C = GREEN**

**LOCK: Do not build Forge until A+B+C are GREEN.**

---

# D — EVIDENCE FORGE

Default external actions: **0**.

### Build whole
- [ ] Read-only ingestion of frozen Tests 0–3 and A/B/C packets.
- [ ] Packet hash/integrity validation.
- [ ] Mock/non-claim separation.
- [ ] Candidate-signal catalog.
- [ ] Predictive/diagnostic/repair/regression/uniqueness/cost scoring.
- [ ] Interaction graph.
- [ ] Repair library.
- [ ] Unresolved registry.
- [ ] Deterministic `black_magic_evidence.jsonl` output.

### Test whole
- [ ] All Forge tests GREEN.
- [ ] Zero external actions consumed.
- [ ] Corrupt packets rejected.
- [ ] Mock-only inputs cannot produce claim-grade findings.
- [ ] High-severity unresolved finding blocks completion.
- [ ] Identical inputs produce identical hashes.
- [ ] Master evidence/repair/interaction hashes frozen.
- [ ] Branch remains additive-only.
- [ ] **FORGE = GREEN**

**LOCK: Do not build Test 5 until FORGE = GREEN.**

---

# E — TEST 5: BLACK-MAGIC FORMULATION

Hard cap: **2,700 external actions**.

### Build whole
- [ ] Evidence-grounded hashable architecture manifests.
- [ ] Fresh adaptive/diagnostic/sealed-holdout partitions.
- [ ] DIRECT/CHECKED/CURRENT_INVERTED anchor.
- [ ] Evidence-derived challenger formulation.
- [ ] Preregistered adaptive budget allocation.
- [ ] Causal component attribution.
- [ ] Interaction search.
- [ ] Negative-result conversion loop.
- [ ] Externally verified bounded self-correction.
- [ ] Architecture compression/minimality.
- [ ] Final architecture freeze before holdout.
- [ ] Complete Test-5 artifacts/configs/CI.

### Test whole
- [ ] All Test-5 unit/integration tests GREEN.
- [ ] Mock Test 5 completes all phases and is labeled instrument validation.
- [ ] 2,701-action plan refuses before first call.
- [ ] Holdout inaccessible during formulation.
- [ ] Architecture immutable after freeze.
- [ ] Real Test 5 eventually satisfies all acceptance-floor clauses:
  - [ ] >=90% paired correctness overall
  - [ ] beats DIRECT for every tested model
  - [ ] >=95% correct/safe disposition
  - [ ] zero unauthorized irreversible/catastrophic deterministic-policy actions
  - [ ] 100% detected known-correctable failures verified-corrected or safely contained
  - [ ] zero silent known-correctable consequential errors
  - [ ] beats DIRECT across mechanics/epistemics/action families
  - [ ] no new high-severity regression class
  - [ ] correctness/safety/external-action Pareto frontier
  - [ ] <=1.5x DIRECT actions per correct task unless preventing proven high-severity failure
  - [ ] every retained component proves causal or invariant value
  - [ ] integrity/leakage/accounting all GREEN
- [ ] `final_architecture.json` frozen and hashed.
- [ ] **TEST 5 = GREEN**

**LOCK: Do not enable real Test 6 until Test 5 is GREEN and explicitly authorized.**

---

# F — TEST 6: NUCLEAR PROVE / KILL / IMPROVE

Hard cap: **2,700 external actions**.

### Build whole
- [ ] Test-5-PASS prerequisite gate.
- [ ] Vault A/B independent generation and hash commitment.
- [ ] Vault state machine/isolation.
- [ ] PROVE comparison stage.
- [ ] Nuke matrix.
- [ ] 2-way/3-way/targeted 4–6-way coverage.
- [ ] Ordered-sequence coverage.
- [ ] Metamorphic nuke campaign.
- [ ] Architecture mutation attacks.
- [ ] Mutation-label blindness.
- [ ] Diagnostic localization requirements.
- [ ] Vault-A repair conversion.
- [ ] Frozen repaired architecture.
- [ ] One-shot Vault-B generalization.
- [ ] Terminal verdict engine.
- [ ] Real config remains disabled until authorization.

### Test whole
- [ ] All Test-6 unit/integration tests GREEN.
- [ ] Mock Test 6 completes all state transitions and is instrument-validation only.
- [ ] 2,701-action plan refuses before first call.
- [ ] Vault B cannot open before repair freeze.
- [ ] Vault B cannot be reused for tuning.
- [ ] All promised factor/sequence coverage verified before scoring.
- [ ] Planted high-severity defects detected/localized without label leakage.
- [ ] Real final verdict is one of `PROVEN`, `KILLED_CONVERTED`, `IMPROVED`, `KILLED`, `INVALID` with evidence-backed reasons.
- [ ] Any accepted Vault-A repair survives one-shot Vault B without new high-severity regression.
- [ ] Branch remains additive-only.
- [ ] **TEST 6 = COMPLETE**

---

# FINAL PROGRAM GATE

- [ ] Tests 0–3 remain byte-identical to base SHA.
- [ ] Harvest A GREEN.
- [ ] Harvest B GREEN.
- [ ] Harvest C GREEN.
- [ ] Forge GREEN.
- [ ] Test 5 GREEN with frozen best architecture.
- [ ] Test 6 terminal verdict complete.
- [ ] Full repository test workflow GREEN on exact final SHA.
- [ ] Dedicated black-magic workflows GREEN on exact final SHA.
- [ ] Final compare against base SHA contains additions only.
- [ ] Final evidence manifests/hashes recorded.
- [ ] No merge to main without explicit user authorization.
