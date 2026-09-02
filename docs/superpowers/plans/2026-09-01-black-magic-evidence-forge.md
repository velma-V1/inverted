# Black-Magic Evidence Forge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a zero-model-call Evidence Forge that ingests immutable prior evidence plus the three harvest packets and emits a deterministic causal evidence vocabulary for Test 5.

**Architecture:** The Forge is offline-only by default. It reads evidence packets by path/hash, never rewrites them, separates mock/instrument-validation evidence from real architecture evidence, computes signal value and interactions, and promotes only findings that can predict, diagnose, repair, regress, or uniquely explain behavior.

**Tech Stack:** Python 3.11+, JSON/JSONL/CSV, deterministic statistics, SHA-256, pytest.

**Spec:** `docs/superpowers/specs/2026-09-01-black-magic-evidence-and-certification-design.md`

## Global Constraints

- Base SHA `19b45314860f2feb7bb561353220eef8d83ba657` remains immutable.
- Forge default execution performs zero external actions.
- Existing evidence packets are read-only and referenced by hashes.
- Mock packets may validate parser/logic paths but cannot support architecture claims.
- Any unresolved high-severity finding blocks Test 5.
- Promotion requires explicit decision value; raw telemetry is not promoted merely because it exists.

---

### Task 1: Freeze Forge contracts with RED tests

**Files:**
- Create: `tests/test_black_magic_forge_ingest.py`
- Create: `tests/test_black_magic_forge_value.py`
- Create: `tests/test_black_magic_forge_integrity.py`

**Interfaces:**
- Expected imports: `discover_packets`, `ingest_packet`, `score_signal_value`, `promote_findings`, `build_interaction_graph`, `forge_master_evidence`.

- [ ] Write RED tests for immutable packet hashing, source-type labeling, mock exclusion from architecture claims, deterministic output ordering, unresolved high-severity blocking, and stable hashes across reruns.
- [ ] Write RED tests proving a raw field with no predictive/diagnostic/repair/regression/uniqueness value is marked `REJECT`.
- [ ] Commit RED tests with message `test: define evidence forge contracts`.

### Task 2: Implement immutable packet ingestion

**Files:**
- Create: `src/inverted/black_magic/forge.py`
- Test: `tests/test_black_magic_forge_ingest.py`

**Interfaces:**
- `discover_packets(paths: list[str | Path]) -> list[dict]`.
- `ingest_packet(path: str | Path) -> dict`.
- Packet descriptor includes path, packet hash, experiment, run ID, provenance, instrument-validation flag, available ledgers, and integrity status.

- [ ] Implement packet discovery without modifying source files.
- [ ] Verify required hash manifests when present and reject corrupt/incomplete packets.
- [ ] Parse frozen Test 0–3 formats and new black-magic packet formats through adapters inside `forge.py`; do not alter old parsers.
- [ ] Run ingest tests GREEN.
- [ ] Commit with message `feat: ingest immutable evidence packets`.

### Task 3: Implement candidate-signal catalog and value scoring

**Files:**
- Create: `src/inverted/black_magic/value.py`
- Test: `tests/test_black_magic_forge_value.py`

**Interfaces:**
- `extract_candidate_signals(packet_records) -> list[dict]`.
- `score_signal_value(signal_rows, outcomes, groups) -> dict`.
- Score fields: prediction, diagnosis, repair, regression, uniqueness, cross-model consistency, collection cost, confidence.

- [ ] Add tests where first-divergence signal ranks above a redundant confidence field.
- [ ] Add tests where two individually weak signals receive `KEEP_AS_COMBINATION` because their interaction predicts a failure class.
- [ ] Implement paired outcome association, conditional failure localization value, verified-repair linkage, redundancy checks, and cross-model direction consistency using deterministic calculations.
- [ ] Ensure no single aggregate score can hide a catastrophic-error increase; severity-weighted regressions remain separate hard fields.
- [ ] Run value tests GREEN.
- [ ] Commit with message `feat: score evidence decision value`.

### Task 4: Build causal repair library and unresolved registry

**Files:**
- Create: `src/inverted/black_magic/repairs.py`
- Create: `tests/test_black_magic_repairs.py`

**Interfaces:**
- `build_repair_library(records) -> list[dict]`.
- `classify_negative_result(record) -> CONVERTED | COMBINED | UNRESOLVED`.

- [ ] Add RED tests requiring targeted intervention, sham intervention, original/targeted/sham outcomes, neighboring validation, and regression status for `CONVERTED`.
- [ ] Add RED tests where a multi-factor interaction is `COMBINED` and an unexplained severe failure becomes `UNRESOLVED`.
- [ ] Implement repair records with cause, first divergence, error lifecycle, intervention, causal lift, generalization, regression, and architecture instruction.
- [ ] Make high-severity `UNRESOLVED` entries fail the Forge completion gate.
- [ ] Run repair tests GREEN.
- [ ] Commit with message `feat: build causal repair library`.

### Task 5: Build interaction graph

**Files:**
- Create: `src/inverted/black_magic/interaction_graph.py`
- Create: `tests/test_black_magic_interaction_graph.py`

**Interfaces:**
- `build_interaction_graph(findings) -> dict`.
- Nodes represent signals/components; edges/hyperedges record synergy, antagonism, redundancy, conditionality, and supporting cases/models.

- [ ] Add RED tests distinguishing additive effects from synergy and antagonism.
- [ ] Add RED tests ensuring interaction claims require either designed combination coverage or verified multi-factor counterfactual evidence.
- [ ] Implement deterministic edge/hyperedge construction and provenance links back to raw finding IDs.
- [ ] Run graph tests GREEN.
- [ ] Commit with message `feat: build evidence interaction graph`.

### Task 6: Emit master evidence artifacts

**Files:**
- Test: `tests/test_black_magic_forge_integrity.py`

**Interfaces:**
- `forge_master_evidence(packet_paths, output_dir) -> dict`.
- Required outputs: `black_magic_evidence.jsonl`, `evidence_catalog.json`, `interaction_graph.json`, `repair_library.jsonl`, `unresolved.jsonl`, `forge_integrity.json`, `SHA256SUMS.csv`.

- [ ] Implement strict promotion contract: every promoted finding must support outcome prediction, first-error localization, DIRECT/INVERTED discrimination, verified repair guidance, repair-success prediction, meaningful interaction, regression detection, safe self-correction, or unique cheaper-not-available information.
- [ ] Emit `KEEP`, `KEEP_AS_COMBINATION`, `CONDITIONAL`, or `REJECT` for every candidate signal.
- [ ] Make output ordering and hashes deterministic for the same input packet set.
- [ ] Include source packet hashes and raw evidence references for every promoted row.
- [ ] Run all Forge tests GREEN.
- [ ] Commit with message `feat: emit black-magic master evidence`.

### Task 7: Add Forge CLI and smoke validation

**Files:**
- Create: `src/inverted/black_magic/forge_cli.py`
- Create: `.github/workflows/black-magic-forge-validation.yml`
- Create: `tests/test_black_magic_forge_cli.py`

**Interfaces:**
- CLI: `python -m inverted.black_magic.forge_cli --input <packet-dir> [--input <packet-dir> ...] --output-dir <dir>`.

- [ ] Add tests proving CLI performs zero external actions and refuses corrupt packets.
- [ ] Add mock fixtures from new smoke packets plus synthetic adapters representing frozen packet schemas; label all mock-derived findings non-claim evidence.
- [ ] Add an additive workflow that runs Forge tests and verifies deterministic rerun hashes.
- [ ] Compare branch against base SHA and require additions only.
- [ ] Commit with message `ci: validate evidence forge`.

### Task 8: Forge completion gate

**Files:** none.

**Interfaces:** Produces the only permitted evidence vocabulary for Test 5.

- [ ] Run full repository pytest suite on exact final Forge SHA.
- [ ] Verify zero external-action usage in Forge execution.
- [ ] Verify mock-only inputs cannot produce architecture-claim-grade findings.
- [ ] Verify high-severity unresolved evidence blocks completion.
- [ ] Verify `black_magic_evidence.jsonl` is reproducible bit-for-bit from identical inputs.
- [ ] Record final Forge SHA and master evidence hashes before Test-5 implementation/execution.
