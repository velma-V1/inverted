# Test-3 Section 0 GitHub Causal Discovery Atlas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Section 0 as a strictly model-free, provenance-preserving causal discovery pipeline that ingests existing Test-1/Test-2 evidence, normalizes historical transitions, classifies every counterfactual, eliminates weak hypotheses, estimates later-section variance/power, and emits a complete evidence packet plus a candidate Section-1 preregistration without authorizing Tier-A inference.

**Architecture:** Add a new `test3_s0_*` namespace beside the frozen Test-2 modules. Section 0 treats prior evidence bundles as immutable inputs: verify source hashes first, normalize them into a canonical transition schema, then run only replay-safe fixed/adaptive policy analyses. Any comparison that needs an unobserved model response or would alter an upstream model prompt is routed to a `REQUIRES_NEW_INFERENCE` queue; invalid/leaky comparisons are retained as `INVALID_COUNTERFACTUAL` data rather than dropped.

**Tech Stack:** Python 3.11+, stdlib (`dataclasses`, `csv`, `json`, `hashlib`, `math`, `random`, `pathlib`), existing PyYAML, pytest, existing Test-2 analysis concepts. No Ollama/model adapter imports are allowed on the Section-0 execution path.

**Spec:** `docs/superpowers/specs/2026-09-01-adaptive-evidence-discovery-campaign-design.md`

## Global Constraints

- Section 0 uses exactly **0 physical model calls**.
- Section 0 may make **no Tier-A architecture claim**.
- Existing Test-1/Test-2 source and evidence semantics are inputs, not code to rewrite.
- Every candidate comparison is exactly one of `CAUSAL_REPLAY`, `REQUIRES_NEW_INFERENCE`, or `INVALID_COUNTERFACTUAL`.
- Hidden gold may be used only for retrospective outcome scoring or explicitly labeled oracle ceilings; it may never become a production-policy feature.
- Missing historical fields remain explicit `null`/`unknown`; normalization must not invent values.
- Bad routing, bad verification, stale memory, failed mentoring, unused calls, cache/accounting defects, provenance defects, and instrumentation failures remain evidence.
- Exact Tier-A budgets remain unfrozen. S0 may output power/variance recommendations only.
- Random-extra-compute/context controls remain mandatory hypotheses for later sections; S0 must not credit architecture for compute it cannot equalize.
- The green design SHA is `0db53efda83060af06a1984fe099d6d52fb515d7`; the implementation starts from that state.

---

## File Structure

Create focused Section-0 files rather than extending the already-large Test-2 modules:

- `src/inverted/test3_s0_types.py` — canonical transition/counterfactual/source contracts and zero-call invariant.
- `src/inverted/test3_s0_inputs.py` — immutable evidence-bundle discovery, SHA verification, parsers, and source manifest.
- `src/inverted/test3_s0_normalize.py` — Test-1/Test-2/model-free rows -> canonical historical transitions.
- `src/inverted/test3_s0_counterfactuals.py` — replay admissibility and causal-status classification.
- `src/inverted/test3_s0_analysis.py` — fixed policies, conditional policies, Pareto ranking, uncertainty, and power/variance estimates.
- `src/inverted/test3_s0_artifacts.py` — exact Section-0 evidence packet, master evidence file, and hashes.
- `src/inverted/test3_s0_cli.py` — Section-0 CLI; no model adapters.
- `configs/test3-s0.yaml` — scientific guardrails and input declarations only; no final Tier-A budget.
- `tests/test_test3_s0_*.py` — contract, normalization, counterfactual, analysis, artifact, CLI, and zero-call tests.
- `.github/workflows/test3-s0-validation.yml` — GitHub/model-free instrument validation and artifact upload.

Do **not** modify `src/inverted/test2_*.py` unless a failing regression proves a shared bug that blocks S0. S0 is analyzing Test-2 evidence; changing Test-2 semantics during S0 would contaminate the historical baseline.

---

### Task 1: Canonical Section-0 contracts and zero-model-call invariant

**Files:**
- Create: `src/inverted/test3_s0_types.py`
- Create: `tests/test_test3_s0_types.py`

**Interfaces:**
- Produces: `CounterfactualStatus`, `EvidenceSource`, `EvidenceState`, `ActionRecord`, `OutcomeRecord`, `TransitionRecord`, `CounterfactualRecord`, `ZeroModelCallGuard`.

- [ ] **Step 1: Write failing tests for the three-state counterfactual enum and zero-call guard**

```python
from inverted.test3_s0_types import CounterfactualStatus, ZeroModelCallGuard


def test_counterfactual_status_is_exhaustive():
    assert {x.value for x in CounterfactualStatus} == {
        "CAUSAL_REPLAY",
        "REQUIRES_NEW_INFERENCE",
        "INVALID_COUNTERFACTUAL",
    }


def test_section0_refuses_any_physical_model_call():
    guard = ZeroModelCallGuard()
    try:
        guard.consume("forbidden")
    except RuntimeError as exc:
        assert "Section 0 permits zero physical model calls" in str(exc)
    else:
        raise AssertionError("S0 allowed a physical model call")
    assert guard.physical_calls == 0
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest tests/test_test3_s0_types.py -q`

Expected: import failure because `test3_s0_types` does not exist.

- [ ] **Step 3: Implement explicit dataclasses with nullable historical fields**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CounterfactualStatus(str, Enum):
    CAUSAL_REPLAY = "CAUSAL_REPLAY"
    REQUIRES_NEW_INFERENCE = "REQUIRES_NEW_INFERENCE"
    INVALID_COUNTERFACTUAL = "INVALID_COUNTERFACTUAL"


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    experiment: str
    path: str
    sha256: str
    git_sha: str | None = None
    evidence_tier: str | None = None
    required: bool = True


@dataclass(frozen=True)
class EvidenceState:
    task_id: str
    task_family: str | None = None
    complexity: int | None = None
    representation: str | None = None
    requirements: tuple[str, ...] = ()
    candidate_status: str | None = None
    prior_model: str | None = None
    prior_role: str | None = None
    prior_attempts: int = 0
    failure_signature: str | None = None
    deterministic_result: str | None = None
    semantic_result: str | None = None
    verifier_results: tuple[dict[str, Any], ...] = ()
    retrieved_experience: tuple[str, ...] = ()
    physical_calls_spent: int = 0
    tokens_spent: int | None = None
    elapsed_ms: float | None = None


@dataclass(frozen=True)
class ActionRecord:
    component: str
    model: str | None = None
    role: str | None = None
    verifier: str | None = None
    operation: str | None = None
    changes_model_input: bool = False
    produces_new_model_output: bool = False


@dataclass(frozen=True)
class OutcomeRecord:
    deterministic_result: str | None = None
    semantic_result: str | None = None
    hidden_gold_result: str | None = None
    catastrophic: bool | None = None
    blocked: bool | None = None
    physical_calls_delta: int = 0
    tokens_delta: int | None = None
    elapsed_ms_delta: float | None = None


@dataclass(frozen=True)
class TransitionRecord:
    transition_id: str
    source_id: str
    state_before: EvidenceState
    action: ActionRecord
    state_after: OutcomeRecord
    observed: bool = True
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CounterfactualRecord:
    counterfactual_id: str
    source_transition_ids: tuple[str, ...]
    proposed_actions: tuple[ActionRecord, ...]
    status: CounterfactualStatus
    reason: str
    hidden_gold_used_as_feature: bool = False


@dataclass
class ZeroModelCallGuard:
    physical_calls: int = 0

    def consume(self, label: str | None = None) -> None:
        detail = f" ({label})" if label else ""
        raise RuntimeError(f"Section 0 permits zero physical model calls{detail}")
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/test_test3_s0_types.py -q`

- [ ] **Step 5: Commit**

```bash
git add src/inverted/test3_s0_types.py tests/test_test3_s0_types.py
git commit -m "feat: add Test-3 Section-0 evidence contracts"
```

---

### Task 2: Immutable evidence-source manifest and integrity verification

**Files:**
- Create: `src/inverted/test3_s0_inputs.py`
- Create: `tests/test_test3_s0_inputs.py`
- Create: `configs/test3-s0.yaml`

**Interfaces:**
- Consumes: directories containing Test-1/Test-2 evidence packets.
- Produces: `load_source_manifest(path)`, `verify_evidence_bundle(source)`, `discover_bundle_files(source)`, parsed source records.

- [ ] **Step 1: Write failing tests that reject hash mismatches and preserve missing-source status**

```python
from pathlib import Path
import hashlib

from inverted.test3_s0_inputs import verify_file_hash, SourceAvailability


def test_verify_file_hash_detects_mutation(tmp_path: Path):
    p = tmp_path / "evidence.json"
    p.write_text('{"x":1}\n', encoding="utf-8")
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    assert verify_file_hash(p, digest)
    p.write_text('{"x":2}\n', encoding="utf-8")
    assert not verify_file_hash(p, digest)


def test_missing_required_source_is_not_silently_ignored(tmp_path: Path):
    status = SourceAvailability.from_path(tmp_path / "missing", required=True)
    assert status.available is False
    assert status.scientific_blocker is True
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_test3_s0_inputs.py -q`

- [ ] **Step 3: Implement source loading with SHA256SUMS-first validation**

Rules in code:

```python
RECOGNIZED_FILES = {
    "events.jsonl",
    "model_calls.jsonl",
    "trials.csv",
    "trials.jsonl",
    "failures.csv",
    "summary.json",
    "summary.csv",
    "report.txt",
    "config.json",
    "provenance.json",
    "preregistration.json",
    "verdict.json",
    "SHA256SUMS.csv",
}
```

`verify_evidence_bundle()` must:
1. require `SHA256SUMS.csv` when the source claims a complete evidence packet;
2. recompute every listed digest;
3. reject path traversal and paths outside the bundle root;
4. record extra/unhashed files rather than silently trust them;
5. expose source git SHA/evidence tier from provenance when available;
6. never alter source files.

- [ ] **Step 4: Freeze config semantics without freezing Tier-A budgets**

```yaml
experiment: test3-section0-github-causal-discovery
mode: model-free
physical_model_call_ceiling: 0
architecture_claims_authorized: false
counterfactual_statuses:
  - CAUSAL_REPLAY
  - REQUIRES_NEW_INFERENCE
  - INVALID_COUNTERFACTUAL
required_source_classes:
  - test1
  - test2_tier_a
  - test2_model_free
allow_partial_instrument_validation: true
power:
  bootstrap_iterations: 20000
  seed: 20260901
  candidate_alpha: 0.05
  target_power: 0.80
```

No exact S1-S6 call budgets appear in this file.

- [ ] **Step 5: Run focused tests and commit**

```bash
python -m pytest tests/test_test3_s0_inputs.py -q
git add src/inverted/test3_s0_inputs.py tests/test_test3_s0_inputs.py configs/test3-s0.yaml
git commit -m "feat: verify immutable Section-0 evidence inputs"
```

---

### Task 3: Normalize Test-1/Test-2 evidence into canonical historical transitions

**Files:**
- Create: `src/inverted/test3_s0_normalize.py`
- Create: `tests/test_test3_s0_normalize.py`

**Interfaces:**
- Consumes: verified evidence bundle readers from Task 2.
- Produces: `normalize_bundle(source_id, root) -> list[TransitionRecord]`, plus normalization coverage rows.

- [ ] **Step 1: Write matched normalization tests using real Test-2-shaped rows**

```python
from inverted.test3_s0_normalize import normalize_test2_event


def test_test2_event_maps_to_transition_without_inventing_model_fields():
    row = {
        "case_id": "mf-state-L1-q0.20-s1001-e0",
        "family": "state",
        "complexity": 1,
        "component": "retry",
        "step": 2,
        "before_success": False,
        "before_blocked": True,
        "after_success": False,
        "after_blocked": False,
        "transition": "FAIL_TO_DIFFERENT_FAIL",
        "candidate_index": 1,
    }
    out = normalize_test2_event("test2-mf", row)
    assert out.state_before.task_id == row["case_id"]
    assert out.state_before.task_family == "state"
    assert out.action.component == "retry"
    assert out.action.model is None
    assert out.state_after.blocked is False
    assert out.provenance["source_transition"] == "FAIL_TO_DIFFERENT_FAIL"
```

- [ ] **Step 2: Add a test proving absent semantic/model/token fields stay explicit unknowns**

Expected assertions:

```python
assert out.state_before.semantic_result is None
assert out.state_before.prior_model is None
assert out.state_before.tokens_spent is None
```

- [ ] **Step 3: Verify RED, then implement adapters**

Implement adapters in this order:
1. Test-2 `events.jsonl` / `raw/every-event.jsonl`.
2. Test-2 `trials.csv` attempt transitions.
3. Test-2 order rows and outcome-transition rows as comparison evidence, not fabricated transitions.
4. Test-2 Tier-A model-call/repair/audit records when present.
5. Test-1 rows through a separate adapter with source-specific field mapping.

Every adapter returns both normalized records and a coverage row:

```python
{
    "source_id": source_id,
    "record_type": "events.jsonl",
    "input_rows": 123,
    "normalized_rows": 123,
    "dropped_rows": 0,
    "unknown_fields": ["semantic_result", "tokens_spent"],
    "errors": [],
}
```

Malformed rows are retained in `normalization_errors.csv`; they are never coerced into plausible values.

- [ ] **Step 4: Verify GREEN and commit**

```bash
python -m pytest tests/test_test3_s0_normalize.py -q
git add src/inverted/test3_s0_normalize.py tests/test_test3_s0_normalize.py
git commit -m "feat: normalize historical evidence for Test-3 S0"
```

---

### Task 4: Causal replay admissibility and exhaustive counterfactual classification

**Files:**
- Create: `src/inverted/test3_s0_counterfactuals.py`
- Create: `tests/test_test3_s0_counterfactuals.py`

**Interfaces:**
- Consumes: normalized observed transitions.
- Produces: `classify_counterfactual(...)`, `enumerate_replay_candidates(...)`, `audit_counterfactuals(...)`.

- [ ] **Step 1: Write failing classification tests for all three statuses**

```python
from inverted.test3_s0_counterfactuals import classify_counterfactual
from inverted.test3_s0_types import CounterfactualStatus


def test_observed_reordering_without_changed_model_input_is_causal_replay():
    result = classify_counterfactual(
        observed_action_ids=("validator", "retry"),
        proposed_action_ids=("retry", "validator"),
        changes_model_input=False,
        needs_unobserved_model_output=False,
        uses_hidden_gold_as_feature=False,
        violates_temporal_availability=False,
        provenance_complete=True,
    )
    assert result.status is CounterfactualStatus.CAUSAL_REPLAY


def test_prompt_changing_repair_requires_new_inference():
    result = classify_counterfactual(
        observed_action_ids=("retry",),
        proposed_action_ids=("targeted_repair", "validator"),
        changes_model_input=True,
        needs_unobserved_model_output=True,
        uses_hidden_gold_as_feature=False,
        violates_temporal_availability=False,
        provenance_complete=True,
    )
    assert result.status is CounterfactualStatus.REQUIRES_NEW_INFERENCE


def test_hidden_gold_router_is_invalid_counterfactual():
    result = classify_counterfactual(
        observed_action_ids=("retry",),
        proposed_action_ids=("switch_model",),
        changes_model_input=False,
        needs_unobserved_model_output=False,
        uses_hidden_gold_as_feature=True,
        violates_temporal_availability=False,
        provenance_complete=True,
    )
    assert result.status is CounterfactualStatus.INVALID_COUNTERFACTUAL
```

- [ ] **Step 2: Implement precedence rules**

Classification order is fixed:

```text
INVALID_COUNTERFACTUAL
  if hidden gold is used as a production feature
  or temporal availability is violated
  or provenance/task identity is insufficient
  or the proposed action is impossible for the historical state

REQUIRES_NEW_INFERENCE
  if any proposed action changes a model prompt/context
  or requires a model/role/task output never observed
  or sequences an observed downstream action after a new model-producing mutation

CAUSAL_REPLAY
  only when all required outputs already exist and can be recomposed without changing model inputs
```

Oracle analysis ceilings are not `INVALID_COUNTERFACTUAL` if clearly labeled `analysis_only_oracle=True`; they remain separate from production-policy candidate rankings.

- [ ] **Step 3: Add replay candidate enumeration for the spec search dimensions**

Enumerate:
- fixed component permutations;
- component ablations;
- model-per-role assignments where the exact model/role/task output exists;
- failure-conditioned switching where both branch outcomes were observed;
- retry vs regenerate vs repair only when the relevant outputs already exist;
- verifier placement/type only where verifier outcomes were actually observed;
- cost/success Pareto candidates;
- replay-safe conditional policies.

Do not synthesize missing model outcomes.

- [ ] **Step 4: Verify GREEN and commit**

```bash
python -m pytest tests/test_test3_s0_counterfactuals.py -q
git add src/inverted/test3_s0_counterfactuals.py tests/test_test3_s0_counterfactuals.py
git commit -m "feat: classify Section-0 causal counterfactuals"
```

---

### Task 5: Fixed/adaptive policy discovery, controls, and Pareto ranking

**Files:**
- Create: `src/inverted/test3_s0_analysis.py`
- Create: `tests/test_test3_s0_analysis.py`

**Interfaces:**
- Consumes: `CAUSAL_REPLAY` transitions/counterfactuals only for production-policy scoring.
- Produces: fixed-policy candidates, adaptive-policy candidates, regret rows, control comparisons, Pareto frontier, unresolved questions.

- [ ] **Step 1: Write a synthetic test where adaptive routing wins only because state differs**

```python
from inverted.test3_s0_analysis import choose_failure_conditioned_policy


def test_failure_conditioned_policy_beats_best_fixed_action_on_complementary_states():
    rows = [
        {"task_id": "a", "failure_signature": "wrong_value", "action": "repair", "success": True},
        {"task_id": "a", "failure_signature": "wrong_value", "action": "retry", "success": False},
        {"task_id": "b", "failure_signature": "missing_requirement", "action": "repair", "success": False},
        {"task_id": "b", "failure_signature": "missing_requirement", "action": "retry", "success": True},
    ]
    result = choose_failure_conditioned_policy(rows, feature="failure_signature")
    assert result["successes"] == 2
    assert result["best_fixed_successes"] == 1
    assert result["gain_over_best_fixed"] == 1
```

- [ ] **Step 2: Implement grouped evaluation to avoid row leakage**

Policy discovery and evaluation group by `task_id`/causal twin group, never by individual transition row. For any learned/derived conditional mapping, use deterministic grouped folds:

```python
def grouped_fold(task_id: str, folds: int = 5) -> int:
    import hashlib
    digest = hashlib.sha256(task_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % folds
```

Train the mapping on four folds and score on the fifth; aggregate across all folds. This is still hypothesis-generation evidence, not a final holdout claim.

- [ ] **Step 3: Score the required negative controls**

Where replayable, compute matched controls for:
- random model switch;
- random verifier;
- random retry;
- random/irrelevant retrieved record if historical retrieval evidence exists;
- equal-call and equal-token subsets where the source data supports them.

Use a fixed RNG seed from config. If a required control is not replayable, emit it to `REQUIRES_NEW_INFERENCE` rather than omit it.

- [ ] **Step 4: Implement cost/success Pareto ranking**

Rank by:
1. maximize verified success;
2. minimize catastrophic escape;
3. minimize physical calls;
4. minimize tokens;
5. minimize latency.

Missing cost dimensions must not be imputed. Emit `cost_completeness` and maintain separate frontiers for fully-costed and outcome-only candidates.

- [ ] **Step 5: Verify focused tests and commit**

```bash
python -m pytest tests/test_test3_s0_analysis.py -q
git add src/inverted/test3_s0_analysis.py tests/test_test3_s0_analysis.py
git commit -m "feat: discover replay-safe Section-0 policies"
```

---

### Task 6: Empirical variance/power analysis and candidate Section-1 preregistration

**Files:**
- Modify: `src/inverted/test3_s0_analysis.py`
- Create: `tests/test_test3_s0_power.py`

**Interfaces:**
- Produces: `estimate_cluster_variance`, `bootstrap_effect_ci`, `estimate_required_task_clusters`, `build_candidate_s1_preregistration`.

- [ ] **Step 1: Write tests proving power is estimated from task clusters, not row count**

```python
from inverted.test3_s0_analysis import estimate_required_task_clusters


def test_required_n_increases_when_cluster_variance_increases():
    low = estimate_required_task_clusters(
        paired_differences=[0.10, 0.10, 0.11, 0.09, 0.10, 0.10],
        target_effect=0.10,
        alpha=0.05,
        power=0.80,
    )
    high = estimate_required_task_clusters(
        paired_differences=[0.30, -0.10, 0.25, -0.05, 0.20, 0.00],
        target_effect=0.10,
        alpha=0.05,
        power=0.80,
    )
    assert high >= low
```

- [ ] **Step 2: Implement conservative empirical power estimation without SciPy**

Use task-cluster paired differences. Compute sample SD and a conservative normal-approximation candidate N:

```python
n = ceil(((z_alpha + z_power) * sd / target_effect) ** 2)
```

with `z_alpha=1.959963984540054` and `z_power=0.8416212335729143` for the configured 95%/80% defaults. Also emit bootstrap CI width from 20,000 task-cluster resamples. If historical clusters are too few or degenerate, return `status="INSUFFICIENT_VARIANCE_EVIDENCE"` and do not invent a budget.

- [ ] **Step 3: Build a candidate-only S1 preregistration**

The output must include:

```json
{
  "status": "CANDIDATE_ONLY_NOT_PREREGISTERED",
  "tier_a_inference_authorized": false,
  "question": "Does fixed component order have enough causal value to justify further fixed-stack optimization?",
  "arms": [
    "best_single_model_baseline",
    "current_best_fixed_hybrid",
    "top_replay_fixed_order_1",
    "top_replay_fixed_order_2",
    "random_or_deliberately_poor_order_control"
  ],
  "holdout": "A",
  "budget_basis": "Section-0 empirical variance/power estimate",
  "exact_budget": null
}
```

S0 may populate recommended task clusters/calls under a separate `recommended_budget_range` field, but `exact_budget` stays `null` until the S1 preregistration is explicitly frozen.

- [ ] **Step 4: Verify and commit**

```bash
python -m pytest tests/test_test3_s0_power.py tests/test_test3_s0_analysis.py -q
git add src/inverted/test3_s0_analysis.py tests/test_test3_s0_power.py
git commit -m "feat: estimate Test-3 follow-on power from S0 evidence"
```

---

### Task 7: Section-0 evidence writer and forensic completion contract

**Files:**
- Create: `src/inverted/test3_s0_artifacts.py`
- Create: `tests/test_test3_s0_artifacts.py`

**Interfaces:**
- Produces the standard Test-3 packet plus S0-specific files.

Required standard files:

```text
preregistration.json
config.json
provenance.json
model_calls.jsonl
events.jsonl
trials.csv
validator_results.csv
failures.csv
wins.csv
losses.csv
transitions.csv
counterfactuals.csv
costs.csv
latency.csv
tokens.csv
cache.csv
failure_atlas.json
effect_sizes.json
verdict.json
report.txt
SHA256SUMS.csv
COMPLETE-EVIDENCE.txt
```

Required S0 additions:

```text
source_manifest.json
source_integrity.csv
normalization_coverage.csv
normalization_errors.csv
fixed_policy_candidates.csv
adaptive_policy_candidates.csv
control_results.csv
pareto_frontier.csv
unresolved_causal_questions.csv
requires_new_inference.csv
invalid_counterfactuals.csv
power_variance.json
candidate_section1_preregistration.json
```

- [ ] **Step 1: Write failing artifact-contract tests**

Tests must assert:
- every required file exists;
- `model_calls.jsonl` exists and is empty;
- `verdict.json` cannot claim architecture support;
- every counterfactual row has one allowed status;
- `COMPLETE-EVIDENCE.txt` embeds every JSON/JSONL/CSV/TXT artifact in deterministic path order;
- `SHA256SUMS.csv` hashes every generated artifact except itself;
- source bundle hashes/provenance are included.

- [ ] **Step 2: Implement a dedicated writer**

Do not modify `Test2ArtifactWriter`. Reuse its evidence philosophy, not its private helper functions. The S0 writer should expose:

```python
class Test3S0ArtifactWriter:
    def __init__(self, run_dir: str | Path): ...
    def write_all(self, evidence: dict[str, Any]) -> dict[str, str]: ...
```

`verdict.json` uses only Section-0-safe statuses:

```text
DISCOVERY_COMPLETE_MODEL_FREE
PARTIAL_INPUT_EVIDENCE
INSTRUMENTATION_FAILURE
SOURCE_INTEGRITY_FAILURE
```

None are Tier-A architecture verdicts.

- [ ] **Step 3: Verify focused tests and commit**

```bash
python -m pytest tests/test_test3_s0_artifacts.py -q
git add src/inverted/test3_s0_artifacts.py tests/test_test3_s0_artifacts.py
git commit -m "feat: write complete Test-3 Section-0 evidence packets"
```

---

### Task 8: Section-0 CLI with scientific-complete and instrument-validation modes

**Files:**
- Create: `src/inverted/test3_s0_cli.py`
- Create: `tests/test_test3_s0_cli.py`

**Interfaces:**
- Command: `python -m inverted.test3_s0_cli run --config ... --source-manifest ... --output-dir ... --run-id ...`
- Command: `python -m inverted.test3_s0_cli validate-instrument --config ... --source-manifest ... --output-dir ... --run-id ...`

- [ ] **Step 1: Write CLI tests that bomb if any model path is touched**

```python

def test_s0_cli_has_no_model_execution_dependency(monkeypatch, tmp_path):
    import inverted.test3_s0_cli as cli
    assert "OllamaAdapter" not in cli.__dict__
    assert "run_local_campaign" not in cli.__dict__
```

Also assert `physical_model_calls == 0` in the emitted provenance/master index.

- [ ] **Step 2: Implement run semantics**

`run`:
- requires all source classes declared `required` in the manifest;
- fails scientific completion on missing required sources, source hash failure, or normalization integrity failure;
- still writes a forensic packet describing the failure;
- never invokes a model.

`validate-instrument`:
- may use only currently available model-free/fixture sources;
- exercises the entire normalization/counterfactual/analysis/artifact pipeline;
- emits `PARTIAL_INPUT_EVIDENCE` and explicitly states it is not the completed Section-0 scientific atlas.

- [ ] **Step 3: Verify and commit**

```bash
python -m pytest tests/test_test3_s0_cli.py -q
git add src/inverted/test3_s0_cli.py tests/test_test3_s0_cli.py
git commit -m "feat: add model-free Test-3 Section-0 CLI"
```

---

### Task 9: GitHub Actions validation without pretending partial CI evidence is full S0

**Files:**
- Create: `.github/workflows/test3-s0-validation.yml`
- Create: `tests/test_test3_s0_workflow_contract.py`

**Interfaces:**
- Produces: `test3-s0-instrument-validation-evidence` artifact.

- [ ] **Step 1: Write a workflow-contract test**

The test must parse the workflow text and assert:
- full pytest runs first;
- fresh Test-2 model-free evidence is generated with `python -m inverted.test2_cli model-free`;
- S0 runs only in `validate-instrument` mode in ordinary CI;
- no Ollama setup, API key, model download, or Tier-A command appears;
- the final step uploads the S0 validation packet.

- [ ] **Step 2: Implement the workflow**

Core sequence:

```yaml
- name: Full pytest suite
  run: python -m pytest -q

- name: Generate fresh Test2 model-free predecessor evidence
  run: >-
    python -m inverted.test2_cli model-free
    --config configs/test2-model-free.yaml
    --output-dir test3-s0-inputs
    --run-id test2-model-free

- name: Build S0 instrument source manifest
  run: python scripts/build-test3-s0-ci-manifest.py

- name: Validate Test3 Section 0 instrument
  run: >-
    python -m inverted.test3_s0_cli validate-instrument
    --config configs/test3-s0.yaml
    --source-manifest test3-s0-inputs/source-manifest.json
    --output-dir test3-s0-ci
    --run-id test3-s0-validation
```

Add `scripts/build-test3-s0-ci-manifest.py` only if the CLI cannot construct the manifest cleanly from an input root. Prefer CLI simplicity over a second script.

- [ ] **Step 3: Add evidence assertions**

CI must assert:

```python
assert master_index["physical_model_calls"] == 0
assert verdict["verdict"] == "PARTIAL_INPUT_EVIDENCE"
assert verdict["tier_a_inference_authorized"] is False
assert model_calls_path.read_text(encoding="utf-8") == ""
assert not missing_required_artifacts
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/test3-s0-validation.yml tests/test_test3_s0_workflow_contract.py scripts/build-test3-s0-ci-manifest.py
git commit -m "ci: validate Test-3 Section-0 model-free instrument"
```

If no helper script is needed, omit it from `git add`.

---

### Task 10: Full regression, source-evidence audit, and Section-0 execution gate

**Files:**
- No production changes unless verification reveals a defect.

- [ ] **Step 1: Run the full repository test suite**

Run: `python -m pytest -q`

Expected: all existing Test-1/Test-2 tests plus new S0 tests pass.

- [ ] **Step 2: Run the fresh model-free predecessor evidence and S0 instrument validation locally**

```bash
python -m inverted.test2_cli model-free \
  --config configs/test2-model-free.yaml \
  --output-dir test3-s0-inputs \
  --run-id test2-model-free

python -m inverted.test3_s0_cli validate-instrument \
  --config configs/test3-s0.yaml \
  --source-manifest test3-s0-inputs/source-manifest.json \
  --output-dir test3-s0-ci \
  --run-id test3-s0-validation
```

Expected:
- zero model calls;
- complete artifact packet;
- `PARTIAL_INPUT_EVIDENCE` unless all historical Test-1/Test-2 Tier-A source classes are actually present;
- no architecture claim.

- [ ] **Step 3: Audit exact historical evidence availability before declaring S0 scientifically runnable**

For each required source class, record:
- source path/artifact origin;
- Git SHA/run ID if available;
- SHA256 evidence digest;
- evidence tier;
- whether the bundle is complete;
- whether it passes its own historical evidence contract.

If Test-1 or Test-2 Tier-A evidence is absent, stop at `PARTIAL_INPUT_EVIDENCE`. Do **not** substitute the model-free atlas and do **not** infer missing Tier-A outcomes.

- [ ] **Step 4: Run GitHub Actions and inspect the uploaded S0 validation artifact**

Required workflows green:
- existing `test`;
- existing `test2-validation`;
- new `test3-s0-validation`.

- [ ] **Step 5: Only after all required historical evidence is present, run scientific S0**

```bash
python -m inverted.test3_s0_cli run \
  --config configs/test3-s0.yaml \
  --source-manifest <verified-complete-source-manifest.json> \
  --output-dir test3-section0 \
  --run-id test3-s0-discovery
```

The completed S0 result may nominate S1 fixed-policy arms and a recommended budget range. It still may **not** execute Tier-A inference or freeze S1's exact budget automatically.

- [ ] **Step 6: Final evidence review before implementation moves to Section 1**

Confirm all of the following:
- every comparison has exactly one counterfactual label;
- `REQUIRES_NEW_INFERENCE` and `INVALID_COUNTERFACTUAL` rows are preserved, not filtered away;
- no hidden-gold feature leakage exists in production-policy candidates;
- random/equal-compute controls are either measured or explicitly queued for new inference;
- adaptive-policy gains are grouped by task/causal twin rather than row-level leakage;
- power estimates report uncertainty and refuse unsupported exact budgets;
- candidate S1 preregistration remains `CANDIDATE_ONLY_NOT_PREREGISTERED`;
- `model_calls.jsonl` is byte-empty and physical-call count is zero;
- all artifact hashes verify.

- [ ] **Step 7: Commit any verification-only documentation updates separately**

```bash
git status --short
git log --oneline -10
```

Do not merge or begin Section 1 implementation until the S0 evidence packet has been reviewed as its own experimental result.
