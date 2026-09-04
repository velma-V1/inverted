# Harvest D R0 Maximum-Value Data Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make D3-Closure model-free mode emit a complete, fail-closed R0 evidence package that maps claim/search space, preserves and values historical small datasets without overstating them, reconstructs actual treatment exposure/pre-state/action-frontier, computes coverage obligations, and keeps physical inference unauthorized.

**Architecture:** Preserve the existing Closure treatment/search/covering/cost/adequacy primitives. Add focused modules for prior-evidence valuation and R0 package construction, extend treatment rendering with exposure descriptors, integrate the package into model-free Closure finalization, and mechanically fail R0 readiness when required artifacts or invariants are missing.

**Tech Stack:** Python 3, dataclasses, pathlib/json/hashlib, pytest, existing Harvest D CLI/campaign/artifact patterns, PowerShell launcher + GitHub Actions Windows validation.

**Spec:** `docs/superpowers/specs/2026-09-04-harvest-d-r0-max-value-data-engine-design.md`

## Global Constraints

- R0 executes zero physical model calls.
- D3-v1 evidence remains immutable.
- Historical/small datasets are preserved as bounded priors, never fresh/sealed confirmation.
- Actual model-visible exposure outranks nominal treatment labels.
- No weak/small prior can directly prune a legal candidate without independent legality/equivalence proof.
- Hidden-oracle leakage fails closed.
- All new artifacts are checksummed.
- `physical_execution_authorized` remains false after R0.
- Do not design Test 5.

---

### Task 1: Historical prior-evidence ledger

**Files:**
- Create: `src/inverted/harvest_d/d3_closure_prior_evidence.py`
- Create: `tests/test_harvest_d_d3_closure_prior_evidence.py`

**Interfaces:**
- Produces: `EvidenceTier`, `PriorValueClass`, `PriorEvidenceRecord`, `inventory_prior_evidence(repo_root: Path) -> tuple[PriorEvidenceRecord, ...]`, `write_prior_evidence_ledger(root: Path, records: Iterable[PriorEvidenceRecord]) -> None`
- Consumes frozen repo artifacts read-only.

- [ ] **Step 1: Write failing tests**

```python
def test_small_historical_dataset_is_preserved_as_prior_not_fresh_confirmation(tmp_path):
    record = PriorEvidenceRecord(
        evidence_source_id="d2-qwen-gain",
        source_path="cases/harvest_d/d2-qwen-gain-v1.jsonl",
        evidence_tier=EvidenceTier.HISTORICAL_PRIOR,
        sample_size=8,
        causal_strength=PriorValueClass.USEFUL_DIRECTIONAL_PRIOR,
        reusable_for=("scheduler_prior", "failure_strata"),
        forbidden_for=("fresh_confirmation", "sealed_confirmation", "global_optimum"),
        scheduler_prior_weight=0.35,
        reason="small matched residual slice",
    )
    assert "fresh_confirmation" in record.forbidden_for
    assert record.evidence_tier is EvidenceTier.HISTORICAL_PRIOR


def test_prior_weight_cannot_be_converted_to_observation_count():
    record = make_prior(sample_size=3, scheduler_prior_weight=0.9)
    assert not hasattr(record, "effective_fresh_n")
```

- [ ] **Step 2: Verify RED in CI/focused test run**

Run: `pytest -q tests/test_harvest_d_d3_closure_prior_evidence.py`
Expected: FAIL because module/types do not exist.

- [ ] **Step 3: Implement immutable prior schema + inventory**

Implement enums:

```python
class EvidenceTier(str, Enum):
    DETERMINISTIC = "E0_DETERMINISTIC"
    HISTORICAL_PRIOR = "E1_HISTORICAL_PRIOR"
    FRESH_DEVELOPMENT = "E2_FRESH_DEVELOPMENT"
    FRESH_SEALED = "E3_FRESH_SEALED"
    NOVELTY_EDGE = "E4_NOVELTY_EDGE"

class PriorValueClass(str, Enum):
    STRONG_CAUSAL_PRIOR = "STRONG_CAUSAL_PRIOR"
    USEFUL_DIRECTIONAL_PRIOR = "USEFUL_DIRECTIONAL_PRIOR"
    FAILURE_ATLAS_PRIOR = "FAILURE_ATLAS_PRIOR"
    COST_RUNTIME_PRIOR = "COST_RUNTIME_PRIOR"
    INSTRUMENTATION_WARNING = "INSTRUMENTATION_WARNING"
    NONTRANSFERABLE = "NONTRANSFERABLE"
```

Inventory known Harvest A/B/C, D2 case slices, frozen D3-v1/posthoc evidence, and D4 when paths exist. Missing optional sources become explicit bounded-unavailable records rather than being silently omitted.

- [ ] **Step 4: Run focused tests and existing D3 regressions**

Run: `pytest -q tests/test_harvest_d_d3_closure_prior_evidence.py tests/test_harvest_d_post_d3_analysis.py`
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -m "feat: preserve historical Closure priors"`

---

### Task 2: Treatment exposure + pre-state/action-frontier descriptors

**Files:**
- Modify: `src/inverted/harvest_d/d3_closure_treatment.py`
- Create: `src/inverted/harvest_d/d3_closure_r0_state.py`
- Modify/Create tests: `tests/test_harvest_d_d3_closure_treatment.py`, `tests/test_harvest_d_d3_closure_r0_state.py`

**Interfaces:**
- Produces: `ExposureSegment`, `TreatmentExposure`, `derive_treatment_exposure(rendered: ClosureRenderedTreatment, case: Any) -> TreatmentExposure`
- Produces: `PreStateDescriptor`, `ActionFrontierDescriptor`, `derive_pre_state(case)`, `derive_action_frontier(case)`.

- [ ] **Step 1: Write failing tests**

```python
def test_exposure_records_channel_order_and_position_for_each_visible_i_field(case):
    rendered = render_treatment(case, ClosureTreatmentPlan(field_ids=("I1", "I2", "I4")))
    exposure = derive_treatment_exposure(rendered, case)
    assert {s.component_id for s in exposure.segments} >= {"I1", "I2", "I4"}
    assert all(s.channel in {"SYSTEM", "TASK", "ASSISTANCE"} for s in exposure.segments)
    assert all(0.0 <= s.position_fraction <= 1.0 for s in exposure.segments)


def test_action_frontier_distinguishes_candidate_and_admissible_actions(case):
    frontier = derive_action_frontier(case)
    assert frontier.action_count == len(frontier.admissible_actions)
    assert frontier.frontier_hash
```

- [ ] **Step 2: Verify RED**

Run focused tests and require missing symbol/module failure.

- [ ] **Step 3: Implement deterministic descriptors**

Use outbound system/user strings from `ClosureRenderedTreatment`; calculate byte ranges and deterministic approximate-token offsets. Hash descriptors using stable canonical JSON. Never infer exact tokenizer offsets in R0.

- [ ] **Step 4: Verify equivalence stability**

Same case + same actual outbound treatment must produce identical exposure/pre-state/frontier IDs even if nominal arm names differ.

- [ ] **Step 5: Run focused + treatment/search regressions**

Expected: PASS.

- [ ] **Step 6: Commit**

`git commit -m "feat: capture Closure treatment exposure state"`

---

### Task 3: R0 claim contract, candidate catalog, pruning ledger, and coverage package

**Files:**
- Create: `src/inverted/harvest_d/d3_closure_r0.py`
- Modify: `src/inverted/harvest_d/d3_closure_search_space.py`
- Modify: `src/inverted/harvest_d/d3_closure_covering.py` only if required for constrained/uncoverable reporting
- Create: `tests/test_harvest_d_d3_closure_r0.py`

**Interfaces:**
- Produces: `R0PackageSummary`, `build_r0_package(repo_root: Path, output_root: Path, config: Mapping[str, Any]) -> R0PackageSummary`

- [ ] **Step 1: Write failing package tests**

Require all artifacts:

```python
REQUIRED = {
    "closure_claim_space_manifest.json",
    "closure_search_space_manifest.json",
    "closure_candidate_equivalence_classes.jsonl",
    "closure_candidate_pruning_ledger.jsonl",
    "closure_prior_evidence_ledger.jsonl",
    "closure_treatment_catalog.jsonl",
    "closure_treatment_exposure.jsonl",
    "closure_pre_state_catalog.jsonl",
    "closure_action_frontier_catalog.jsonl",
    "closure_combinatorial_coverage.json",
    "closure_interaction_coverage.json",
    "closure_uncovered_space.json",
    "closure_r0_readiness_report.json",
    "closure_claim_adequacy_report.json",
}
```

Also assert:

```python
assert summary.physical_model_calls == 0
assert summary.final_state == "R0_MODEL_FREE_COMPLETE"
assert summary.physical_execution_authorized is False
```

- [ ] **Step 2: Verify RED**

Expected: package builder missing.

- [ ] **Step 3: Implement claim manifest**

Encode inferential objectives for information value, amount, representation, ordering, timing/placement, A1-A4, model/family interactions, substitution, robustness, recovery, routing, minimality, and responsibility boundaries. Each claim names required factors/effect modifiers/evidence tiers/controls/confirmation.

- [ ] **Step 4: Implement deterministic candidate generation/reduction**

Do not materialize the entire raw Cartesian space. Generate the actual screenable candidate catalog from legal treatment templates/cases; compute raw theoretical count algebraically; record every applied prune/equivalence reason; do not prune solely from weak historical priors.

- [ ] **Step 5: Generate pairwise + targeted 3-way obligations**

Require explicit uncovered/constrained obligations. Keep a deterministic protected challenger sample from underexplored equivalence classes.

- [ ] **Step 6: Integrate historical prior valuation**

Attach prior metadata to candidate scheduler fields without changing evidence tier or fresh observation counts.

- [ ] **Step 7: Run focused tests**

Expected: PASS and artifacts non-empty where semantically required.

- [ ] **Step 8: Commit**

`git commit -m "feat: build zero-call Closure R0 package"`

---

### Task 4: Harden claim adequacy for R0 artifacts and evidence-tier integrity

**Files:**
- Modify: `src/inverted/harvest_d/d3_closure_adequacy.py`
- Modify: `tests/test_harvest_d_d3_closure_adequacy.py`

**Interfaces:**
- Extend `ClaimAdequacyInputs` with R0 package readiness/evidence-tier integrity/uncovered-obligation state while preserving fail-closed behavior.

- [ ] **Step 1: Write RED tests**

```python
def test_r0_cannot_complete_when_historical_prior_is_counted_as_fresh():
    report = evaluate_claim_adequacy(_complete_inputs(evidence_tier_integrity=False))
    assert report.physical_execution_authorized is False
    assert "evidence tier" in " ".join(report.blockers).lower()


def test_r0_missing_required_artifact_fails_closed():
    report = evaluate_claim_adequacy(_complete_inputs(r0_required_artifacts_complete=False))
    assert report.physical_execution_authorized is False
```

- [ ] **Step 2: Verify RED**

- [ ] **Step 3: Implement fields and blocker reasons**

R0 can be complete while physical execution remains false because R1 and later prerequisites remain intentionally false.

- [ ] **Step 4: Run focused adequacy tests**

- [ ] **Step 5: Commit**

`git commit -m "test: fail closed on incomplete R0 evidence"`

---

### Task 5: Integrate R0 into model-free Closure CLI/package

**Files:**
- Modify: `src/inverted/harvest_d/d3_closure_campaign.py`
- Modify: `src/inverted/harvest_d/d3_closure_analysis.py`
- Modify: `src/inverted/harvest_d/d3_closure_cli.py`
- Modify: `tests/test_harvest_d_d3_closure_campaign.py`
- Modify: `tests/test_harvest_d_d3_closure_cli.py`

**Interfaces:**
- `D3ClosureCampaign.run_model_free()` invokes `build_r0_package(...)` before finalizing the package.
- Master/final reports include `r0_state`, `r0_artifact_count`, `r0_readiness`, and `physical_execution_authorized=false`.

- [ ] **Step 1: Add failing integration tests**

```python
def test_model_free_closure_emits_full_r0_package_and_zero_calls(tmp_path, config):
    result = D3ClosureCampaign(tmp_path, config=config).run_model_free()
    assert result.physical_model_calls == 0
    assert json.loads((tmp_path / "closure_r0_readiness_report.json").read_text())["r0_ready"] is True
```

Also require `SHA256SUMS.csv` to contain every R0 artifact.

- [ ] **Step 2: Verify RED**

- [ ] **Step 3: Wire package builder into model-free flow**

No real-mode call path changes beyond loading/failing closed on fresh adequacy state later. Do not remove the existing physical authorization hold.

- [ ] **Step 4: Update finalization/checksums**

- [ ] **Step 5: Run focused Closure suite**

Run:
`pytest -q tests/test_harvest_d_d3_closure_*.py`

- [ ] **Step 6: Commit**

`git commit -m "feat: integrate R0 into Closure model-free gate"`

---

### Task 6: Windows launcher + CI R0 verification

**Files:**
- Modify only if required: `.github/workflows/harvest-d-validation.yml`
- Modify only if required: `tests/test_harvest_d_d3_closure_launcher_windows.py`
- Reuse: `scripts/run-harvest-d-d3-closure-v2.ps1`, `scripts/run-harvest-d-d4-through-closure.ps1`

- [ ] **Step 1: Add/adjust source-validation tests only if current launcher assertions do not verify R0 artifacts**

Require Windows model-free path to validate existence of `closure_r0_readiness_report.json` and zero physical calls.

- [ ] **Step 2: Verify RED if a launcher change is required**

- [ ] **Step 3: Apply minimum launcher/CI change**

Do not alter real inference authorization.

- [ ] **Step 4: Run full focused Harvest D suite**

- [ ] **Step 5: Run full repository suite**

- [ ] **Step 6: Verify GitHub Actions Windows model-free launcher path**

- [ ] **Step 7: Commit**

`git commit -m "ci: verify Closure R0 model-free package"`

---

### Task 7: R0 completion audit

**Files:**
- No production changes unless audit finds a defect.
- Update design/plan only if a proven requirement changed.

- [ ] Confirm no physical model call path was opened.
- [ ] Confirm `configs/harvest-d-d3-closure-v2-execution-authorization.json` remains `physical_execution_authorized=false`.
- [ ] Confirm D3-v1 frozen source hashes are unchanged.
- [ ] Confirm prior/small datasets appear in the prior ledger rather than being skipped.
- [ ] Confirm no historical prior contributes to fresh/sealed N.
- [ ] Confirm required R0 artifacts are checksummed.
- [ ] Confirm pairwise/targeted 3-way obligations and uncovered regions are explicit.
- [ ] Confirm full repository CI is green or document any unrelated pre-existing failures precisely.
- [ ] Stop at R0. Do not begin R1 physical calibration without the next explicit execution decision.

## Completion criterion

R0 is complete when a single model-free Closure invocation generates a deterministic, checksummed R0 package with claim/search-space accounting, historical-prior valuation, treatment exposure, pre-state/action-frontier catalogs, coverage obligations, uncovered-space reporting, and fail-closed adequacy; all focused/full/Windows model-free validations are green; and physical Closure remains unauthorized.
