# Test 5 — Causal Architecture Tomography Implementation Plan

**Goal:** Build Test 5 as an evidence-forensics → architecture-discovery → causal-falsification → compression → sealed-certification pipeline without contaminating prior frozen evidence.

**Base evidence commit:** `0d67ba4e5578b4c14225eb83b726fd137dfffecd`

**Design:** `docs/superpowers/specs/2026-09-02-test5-causal-architecture-tomography-design.md`

## Non-negotiable gates

- Never edit prior frozen evidence.
- Never count duplicate/partial runs as independent inferential samples.
- Never tune on sealed certification cases.
- Never let the model under test certify itself.
- Never promote a runtime guard from an unverified model assertion.
- Never preserve a component merely because it is plausible.
- Never expand higher-order interactions by brute force.

## Stage 0 — Provenance and evidence catalog

Create:
- `src/inverted/test5/evidence_catalog.py`
- `src/inverted/test5/schema.py`
- `tests/test_test5_evidence_catalog.py`

Requirements:
- ingest prior manifests, hashes, run ids, completeness markers, provenance, trial/call artifacts;
- classify COMPLETE/PARTIAL/ABORTED/DUPLICATE;
- assign admissible claim classes;
- build duplicate groups from run identity + artifact hashes + manifests;
- preserve source lineage;
- emit unresolved integrity findings.

Gate: architecture generation is blocked when a severe integrity conflict is unresolved.

## Stage 1 — Causal knowledge extraction

Create:
- `src/inverted/test5/causal_knowledge.py`
- `src/inverted/test5/failure_taxonomy.py`
- `tests/test_test5_causal_knowledge.py`

Build normalized objects for:
- observed failure;
- first meaningful divergence;
- causal hypothesis;
- intervention;
- sham/control;
- replay identity;
- outcome delta;
- generalization state;
- regression state;
- architecture instruction.

Do not upgrade correlation to causal verification.

## Stage 2 — Architecture graph representation

Create:
- `src/inverted/test5/architecture_graph.py`
- `tests/test_test5_architecture_graph.py`

Implement hashable node/edge schemas with authority, state, evidence, verification, recovery, invariants, and cost metadata.

Tests must prove:
- cosmetic prompt/model-setting changes do not create material architecture identity;
- control/authority/state/verification changes do;
- graphs serialize canonically and hash reproducibly.

## Stage 3 — Evidence-grounded candidate synthesis

Create:
- `src/inverted/test5/candidates.py`
- `tests/test_test5_candidates.py`

Seed required architecture families A–J plus evidence-supported challengers.

Candidate acceptance requires:
- evidence lineage;
- material structural difference;
- falsification condition;
- predicted weak point;
- model-size sensitivity hypothesis.

Generate 15–20 raw candidates, compress to 10–15 serious candidates.

## Stage 4 — Failure attack library

Create:
- `src/inverted/test5/attacks.py`
- `src/inverted/test5/mutations.py`
- `tests/test_test5_attacks.py`

Encode hidden-label attacks for state, evidence, authority, scope, decomposition, context, verifier, recovery, ordering, stochasticity, and long-horizon propagation.

Mutation metadata must remain private from model prompts.

## Stage 5 — Test 5 runtime harness

Create:
- `src/inverted/test5/runtime.py`
- `src/inverted/test5/journal.py`
- `tests/test_test5_runtime.py`

Reuse the S2 forensic principles:
- append-only durable journal;
- action budget accounting;
- raw model transaction retention;
- exact state snapshots;
- failure-stage telemetry;
- no transport retry loop;
- partial evidence survives abort;
- every replay records exact pre-failure state identity.

## Stage 6 — Broad screening

Create:
- `src/inverted/test5/screen.py`
- `tests/test_test5_screen.py`

Use paired fresh cases with bounded repeats.

Eliminate only for preregistered reasons:
- invariant violation;
- material inferiority;
- causal redundancy;
- dependence on unsupported assumption;
- unsafe control structure.

Screening cannot certify.

## Stage 7 — Single-factor tomography

Create:
- `src/inverted/test5/tomography.py`
- `tests/test_test5_tomography.py`

For each survivor:
- remove/disable/corrupt/reorder live mechanisms;
- replay from same state;
- compare against sham;
- classify causal effect and first divergence.

Every retained component must eventually have either causal value or hard-invariant value.

## Stage 8 — Interaction design

Create:
- `src/inverted/test5/interactions.py`
- `tests/test_test5_interactions.py`

Implement staged search:
1. complete pairwise among live factors;
2. heredity-constrained sparse triples;
3. selected 4–6 factor architecture bundles;
4. ordered stateful sequences.

Include false-discovery control or equivalent conservative discovery discipline.

Do not brute-force the full power set.

## Stage 9 — Failure conversion and bounded repair

Create:
- `src/inverted/test5/repair.py`
- `tests/test_test5_repair.py`

Protocol:
`failure → diagnosis → intervention → sham → exact-state replay → neighboring generalization → fresh-family generalization → regression`.

Default: one bounded repair opportunity. Additional retry-count experiments require explicit preregistration.

## Stage 10 — Compression

Create:
- `src/inverted/test5/compression.py`
- `tests/test_test5_compression.py`

Perform architecture deletion tests.

Delete any component whose removal:
- does not reduce measured value materially; and
- does not violate a hard invariant.

Recompute material architecture identity after compression and merge duplicates.

## Stage 11 — Portfolio freeze

Create:
- `src/inverted/test5/freeze.py`
- `tests/test_test5_freeze.py`

Freeze and hash:
- candidate graphs;
- source commit;
- code commit;
- configs;
- prompts;
- model list;
- case manifests;
- analysis version;
- thresholds/margins;
- seed/repeat policy.

After freeze, sealed evidence cannot mutate the candidate.

## Stage 12 — Sealed certification

Create:
- `src/inverted/test5/certification.py`
- `src/inverted/test5/statistics.py`
- `tests/test_test5_certification.py`

Required outputs:
- paired correctness/safe-disposition effects vs DIRECT;
- uncertainty intervals;
- catastrophic violation count;
- family-level effects;
- repeat disagreement;
- model-size interactions;
- efficiency/Pareto metrics;
- integrity status.

Certification requires all hard invariants plus preregistered target/margin rules.

If fewer than five pass, emit `INSUFFICIENT_CANDIDATES` without synthesizing variants.

## Stage 13 — Model minimization

Create:
- `src/inverted/test5/model_frontier.py`
- `tests/test_test5_model_frontier.py`

Estimate architecture × model-size interactions.

Classify tasks by minimum reliable model class and identify where architecture erases or fails to erase model-size advantage.

## Stage 14 — Promoted failure knowledge

Create:
- `src/inverted/test5/learning.py`
- `tests/test_test5_learning.py`

Only GENERALIZED + regression-safe mechanisms may be promoted.

Promoted record must include source evidence, signature, mechanism, intervention, applicability, contraindications, confidence, version, and rollback.

No autonomous code mutation.

## Stage 15 — Atlas and construction blueprint

Create:
- `src/inverted/test5/artifacts.py`
- `src/inverted/test5/report.py`
- `tests/test_test5_artifacts.py`

Emit all artifacts required by the design spec, including the portfolio leader, specialists, minimal architecture, tiny-model architecture, remaining unknowns, roadmap, and Test 6 handoff.

## Stage 16 — CI and end-to-end validation

Create:
- `.github/workflows/test5-validation.yml`
- `tests/test_test5_end_to_end.py`

CI should run model-free deterministic validation only. Real local-model experiments remain separately authorized and must not be silently triggered by normal pushes.

End-to-end mock must prove:
- evidence lineage preserved;
- duplicate suppression;
- attack labels hidden;
- exact-state replay identity;
- compression removes zero-rent components;
- freeze prevents tuning;
- certification does not pool architectures;
- `INSUFFICIENT_CANDIDATES` works;
- full artifact manifest hashes verify.

## Execution order

`0 provenance → 1 causal extraction → 2 graphs → 3 candidates → 4 attacks → 5 runtime → 6 broad screen → 7 tomography → 8 interactions → 9 conversion → 10 compression → 11 freeze → 12 certification → 13 model frontier → 14 learning → 15 atlas → 16 CI`

Do not begin real Test 5 model calls until Stages 0–12 pass deterministic/mock validation and the sealed-case generation/provenance contract is frozen.
