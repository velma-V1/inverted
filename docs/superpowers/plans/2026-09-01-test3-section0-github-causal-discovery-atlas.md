# Test-3 Section 0 GitHub Causal Discovery Atlas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Section 0 as a strictly model-free causal discovery pipeline that ingests existing Test-1/Test-2 evidence, normalizes historical transitions, classifies every counterfactual, eliminates weak hypotheses, estimates later-section variance/power, and emits a complete evidence packet plus a candidate Section-1 preregistration without authorizing Tier-A inference.

**Architecture:** Add a separate `test3_s0_*` namespace beside the frozen Test-2 implementation. Historical evidence bundles are immutable inputs: verify hashes first, normalize observed transitions second, then score only replay-safe fixed/adaptive policies. Any comparison requiring an unobserved model response or changed model input becomes `REQUIRES_NEW_INFERENCE`; impossible, temporally invalid, or hidden-gold-leaking comparisons remain recorded as `INVALID_COUNTERFACTUAL`.

**Tech Stack:** Python 3.11+, stdlib (`dataclasses`, `enum`, `csv`, `json`, `hashlib`, `math`, `random`, `pathlib`), existing PyYAML, pytest. The S0 execution path must not import Ollama or any model adapter.

**Spec:** `docs/superpowers/specs/2026-09-01-adaptive-evidence-discovery-campaign-design.md`

## Global Constraints

- Section 0 uses exactly **0 physical model calls**.
- Section 0 makes **no Tier-A architecture claim**.
- Test-1/Test-2 code and evidence semantics are historical inputs, not targets for refactoring.
- Every counterfactual is exactly one of `CAUSAL_REPLAY`, `REQUIRES_NEW_INFERENCE`, or `INVALID_COUNTERFACTUAL`.
- Hidden gold may be used only for retrospective outcome scoring or explicitly analysis-only oracle ceilings; it is forbidden as a production-policy feature.
- Missing historical fields remain explicit unknowns; normalization never invents values.
- Bad routing, bad verification, stale memory, failed mentoring, unused calls, cache/accounting defects, provenance defects, and instrumentation failures remain evidence.
- Exact Tier-A budgets remain unfrozen. S0 may emit a recommended range, never an automatically frozen budget.
- Random-extra-compute/context controls must be measured where replayable or queued for new inference.
- Approved design baseline: `cf72657037c4d3fb6cc6381c48ab6c4abdc831ce`.

---

## File Structure

- `src/inverted/test3_s0_types.py` — source/state/action/outcome/transition/counterfactual contracts and zero-call guard.
- `src/inverted/test3_s0_inputs.py` — source manifest, bundle discovery, SHA verification, immutable readers.
- `src/inverted/test3_s0_normalize.py` — Test-1/Test-2/model-free evidence adapters.
- `src/inverted/test3_s0_counterfactuals.py` — replay admissibility and three-way classification.
- `src/inverted/test3_s0_analysis.py` — fixed/adaptive policy search, controls, Pareto ranking, uncertainty, power.
- `src/inverted/test3_s0_artifacts.py` — Section-0 packet, master evidence stream, hashes.
- `src/inverted/test3_s0_cli.py` — `build-manifest`, `validate-instrument`, and `run` commands.
- `configs/test3-s0.yaml` — S0 scientific guardrails; no final Tier-A budget.
- `tests/test_test3_s0_*.py` — unit/contract/regression coverage.
- `.github/workflows/test3-s0-validation.yml` — zero-call GitHub instrument validation.

Do **not** modify `src/inverted/test2_*.py` unless a failing regression proves a shared reader defect that prevents S0 from consuming already-emitted evidence.

---

### Task 1: Canonical contracts and zero-model-call invariant

**Files:**
- Create: `src/inverted/test3_s0_types.py`
- Create: `tests/test_test3_s0_types.py`

**Interfaces:**
- Produces: `CounterfactualStatus`, `EvidenceSource`, `EvidenceState`, `ActionRecord`, `OutcomeRecord`, `TransitionRecord`, `CounterfactualRecord`, `ZeroModelCallGuard`.

- [ ] **Step 1: Write failing tests**

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

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_test3_s0_types.py -q`

- [ ] **Step 3: Implement the contracts**

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
    source_class: str
    path: str
    required: bool
    bundle_sha256: str | None = None
    git_sha: str | None = None
    run_id: str | None = None
    evidence_tier: str | None = None


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
    analysis_only_oracle: bool = False


@dataclass
class ZeroModelCallGuard:
    physical_calls: int = 0

    def consume(self, label: str | None = None) -> None:
        detail = f" ({label})" if label else ""
        raise RuntimeError(f"Section 0 permits zero physical model calls{detail}")
```

- [ ] **Step 4: Verify GREEN and commit**

```bash
python -m pytest tests/test_test3_s0_types.py -q
git add src/inverted/test3_s0_types.py tests/test_test3_s0_types.py
git commit -m "feat: add Test-3 Section-0 evidence contracts"
```

---

### Task 2: Immutable evidence manifest and source-integrity verification

**Files:**
- Create: `src/inverted/test3_s0_inputs.py`
- Create: `tests/test_test3_s0_inputs.py`
- Create: `configs/test3-s0.yaml`

**Interfaces:**
- Produces: `load_source_manifest`, `write_source_manifest`, `verify_file_hash`, `verify_evidence_bundle`, `discover_bundle_files`, `SourceAvailability`.

- [ ] **Step 1: Write failing integrity tests**

```python
from pathlib import Path
import hashlib

from inverted.test3_s0_inputs import SourceAvailability, verify_file_hash


def test_hash_mutation_is_detected(tmp_path: Path):
    p = tmp_path / "x.json"
    p.write_text("{\"x\":1}\n", encoding="utf-8")
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    assert verify_file_hash(p, digest)
    p.write_text("{\"x\":2}\n", encoding="utf-8")
    assert verify_file_hash(p, digest) is False


def test_missing_required_source_is_scientific_blocker(tmp_path: Path):
    status = SourceAvailability.from_path(tmp_path / "missing", required=True)
    assert status.available is False
    assert status.scientific_blocker is True
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_test3_s0_inputs.py -q`

- [ ] **Step 3: Implement bundle verification**

`verify_evidence_bundle()` must require `SHA256SUMS.csv` for sources claiming completeness, recompute each hash, reject path traversal/out-of-root entries, list unhashed extras, extract git SHA/run ID/evidence tier when available, and never alter source bytes.

Recognize at minimum:

```python
RECOGNIZED_FILES = {
    "events.jsonl", "model_calls.jsonl", "trials.csv", "trials.jsonl",
    "failures.csv", "summary.json", "summary.csv", "report.txt",
    "config.json", "provenance.json", "preregistration.json",
    "verdict.json", "SHA256SUMS.csv",
}
```

- [ ] **Step 4: Add the frozen S0 config**

```yaml
experiment: test3-section0-github-causal-discovery
mode: model-free
physical_model_call_ceiling: 0
architecture_claims_authorized: false
required_source_classes:
  - test1
  - test2_tier_a
  - test2_model_free
allow_partial_instrument_validation: true
counterfactual_statuses:
  - CAUSAL_REPLAY
  - REQUIRES_NEW_INFERENCE
  - INVALID_COUNTERFACTUAL
power:
  bootstrap_iterations: 20000
  seed: 20260901
  candidate_alpha: 0.05
  target_power: 0.80
```

- [ ] **Step 5: Verify GREEN and commit**

```bash
python -m pytest tests/test_test3_s0_inputs.py -q
git add src/inverted/test3_s0_inputs.py tests/test_test3_s0_inputs.py configs/test3-s0.yaml
git commit -m "feat: verify immutable Section-0 evidence sources"
```

---

### Task 3: Normalize historical evidence into canonical transitions

**Files:**
- Create: `src/inverted/test3_s0_normalize.py`
- Create: `tests/test_test3_s0_normalize.py`

**Interfaces:**
- Produces: `normalize_test2_event`, `normalize_test2_trial`, `normalize_test2_tier_a_record`, `normalize_test1_record`, `normalize_bundle`.

- [ ] **Step 1: Write a Test-2-shaped normalization test**

```python
from inverted.test3_s0_normalize import normalize_test2_event


def test_model_free_event_normalizes_without_inventing_model_fields():
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
    assert out.state_before.semantic_result is None
    assert out.state_before.tokens_spent is None
    assert out.state_after.blocked is False
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_test3_s0_normalize.py -q`

- [ ] **Step 3: Implement adapters**

Implement in this order: Test-2 `events.jsonl`/`raw/every-event.jsonl`; Test-2 `trials.csv` attempt transitions; Test-2 order/effect rows as comparison evidence rather than fabricated model transitions; Test-2 Tier-A model-call/repair/audit rows; Test-1 source-specific rows.

Each adapter emits coverage:

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

Malformed rows go to `normalization_errors.csv`; they are never coerced.

- [ ] **Step 4: Verify GREEN and commit**

```bash
python -m pytest tests/test_test3_s0_normalize.py -q
git add src/inverted/test3_s0_normalize.py tests/test_test3_s0_normalize.py
git commit -m "feat: normalize Test-3 historical evidence"
```

---

### Task 4: Exhaustive counterfactual classification and replay admissibility

**Files:**
- Create: `src/inverted/test3_s0_counterfactuals.py`
- Create: `tests/test_test3_s0_counterfactuals.py`

**Interfaces:**
- Produces: `classify_counterfactual`, `enumerate_replay_candidates`, `audit_counterfactuals`.

- [ ] **Step 1: Write all three classification tests**

```python
from inverted.test3_s0_counterfactuals import classify_counterfactual
from inverted.test3_s0_types import CounterfactualStatus


def test_recomposition_of_observed_outputs_is_causal_replay():
    result = classify_counterfactual(False, False, False, False, True, True)
    assert result.status is CounterfactualStatus.CAUSAL_REPLAY


def test_prompt_changing_repair_requires_new_inference():
    result = classify_counterfactual(True, True, False, False, True, True)
    assert result.status is CounterfactualStatus.REQUIRES_NEW_INFERENCE


def test_hidden_gold_router_is_invalid():
    result = classify_counterfactual(False, False, True, False, True, True)
    assert result.status is CounterfactualStatus.INVALID_COUNTERFACTUAL
```

The six positional arguments are, in order: `changes_model_input`, `needs_unobserved_model_output`, `uses_hidden_gold_as_feature`, `violates_temporal_availability`, `provenance_complete`, `action_possible`.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_test3_s0_counterfactuals.py -q`

- [ ] **Step 3: Implement fixed precedence**

```text
INVALID_COUNTERFACTUAL
  hidden gold used as production feature
  OR temporal availability violated
  OR provenance/task identity insufficient
  OR action impossible in historical state

REQUIRES_NEW_INFERENCE
  proposed action changes model input/context
  OR requires an unobserved model/role/task output
  OR places an observed downstream step after a new model-producing mutation

CAUSAL_REPLAY
  all required outputs already exist and recomposition does not change model inputs
```

Oracle ceilings require `analysis_only_oracle=True` and are excluded from production-policy rankings.

- [ ] **Step 4: Enumerate all S0 search dimensions**

Enumerate fixed permutations, ablations, model-role assignments, failure-conditioned switching, retry/regenerate/repair, verifier placement/type, cost/success frontiers, and replay-safe conditional policies. Missing required outputs create `REQUIRES_NEW_INFERENCE`; never synthesize model behavior.

- [ ] **Step 5: Verify GREEN and commit**

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
- Produces: `score_fixed_policies`, `choose_failure_conditioned_policy`, `score_grouped_policy`, `score_negative_controls`, `pareto_rank_candidates`.

- [ ] **Step 1: Write a complementary-state test**

```python
from inverted.test3_s0_analysis import choose_failure_conditioned_policy


def test_conditional_policy_beats_best_fixed_action_without_extra_calls():
    rows = [
        {"task_id": "a", "failure_signature": "wrong_value", "action": "repair", "success": True, "calls": 1},
        {"task_id": "a", "failure_signature": "wrong_value", "action": "retry", "success": False, "calls": 1},
        {"task_id": "b", "failure_signature": "missing_requirement", "action": "repair", "success": False, "calls": 1},
        {"task_id": "b", "failure_signature": "missing_requirement", "action": "retry", "success": True, "calls": 1},
    ]
    result = choose_failure_conditioned_policy(rows, feature="failure_signature")
    assert result["successes"] == 2
    assert result["best_fixed_successes"] == 1
    assert result["gain_over_best_fixed"] == 1
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_test3_s0_analysis.py -q`

- [ ] **Step 3: Implement grouped evaluation**

Use task/causal-twin groups, never individual transition rows. Deterministic fold assignment:

```python
def grouped_fold(task_id: str, folds: int = 5) -> int:
    digest = hashlib.sha256(task_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % folds
```

Derive conditional mappings on four folds and score on the fifth; aggregate only held-out-fold scores.

- [ ] **Step 4: Score replayable negative controls**

Using seed `20260901`, score random model switch, random verifier, random retry, irrelevant retrieved item where historical retrieval evidence exists, equal-call subsets, and equal-token subsets. Non-replayable controls are retained in `REQUIRES_NEW_INFERENCE`.

- [ ] **Step 5: Implement Pareto ranking**

Objectives, in order: maximize verified success; minimize catastrophic escape; minimize physical calls; minimize tokens; minimize latency. Never impute missing cost dimensions. Emit `cost_completeness` and separate fully-costed from outcome-only frontiers.

- [ ] **Step 6: Verify GREEN and commit**

```bash
python -m pytest tests/test_test3_s0_analysis.py -q
git add src/inverted/test3_s0_analysis.py tests/test_test3_s0_analysis.py
git commit -m "feat: discover replay-safe Section-0 policies"
```

---

### Task 6: Empirical variance/power estimation and candidate S1 preregistration

**Files:**
- Modify: `src/inverted/test3_s0_analysis.py`
- Create: `tests/test_test3_s0_power.py`

**Interfaces:**
- Produces: `bootstrap_effect_ci`, `estimate_required_task_clusters`, `build_candidate_s1_preregistration`.

- [ ] **Step 1: Write variance-sensitive power test**

```python
from inverted.test3_s0_analysis import estimate_required_task_clusters


def test_required_n_rises_with_cluster_variance():
    low = estimate_required_task_clusters(
        [0.10, 0.10, 0.11, 0.09, 0.10, 0.10], 0.10, 0.05, 0.80
    )
    high = estimate_required_task_clusters(
        [0.30, -0.10, 0.25, -0.05, 0.20, 0.00], 0.10, 0.05, 0.80
    )
    assert high["recommended_clusters"] >= low["recommended_clusters"]
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_test3_s0_power.py -q`

- [ ] **Step 3: Implement conservative empirical estimation**

Use task-cluster paired differences and sample SD:

```python
recommended_n = math.ceil(
    ((1.959963984540054 + 0.8416212335729143) * sd / target_effect) ** 2
)
```

Also compute a 20,000-resample task-cluster bootstrap CI. Too few clusters or unusable variance returns `status="INSUFFICIENT_VARIANCE_EVIDENCE"`; no budget is invented.

- [ ] **Step 4: Emit candidate-only S1 preregistration**

```python
candidate = {
    "status": "CANDIDATE_ONLY_NOT_PREREGISTERED",
    "tier_a_inference_authorized": False,
    "question": "Does fixed component order have enough causal value to justify further fixed-stack optimization?",
    "arms": [
        "best_single_model_baseline",
        "current_best_fixed_hybrid",
        "top_replay_fixed_order_1",
        "top_replay_fixed_order_2",
        "random_or_deliberately_poor_order_control",
    ],
    "holdout": "A",
    "budget_basis": "Section-0 empirical variance/power estimate",
    "exact_budget": None,
}
```

A separate `recommended_budget_range` may be emitted; `exact_budget` remains null until S1 is explicitly frozen.

- [ ] **Step 5: Verify GREEN and commit**

```bash
python -m pytest tests/test_test3_s0_power.py tests/test_test3_s0_analysis.py -q
git add src/inverted/test3_s0_analysis.py tests/test_test3_s0_power.py
git commit -m "feat: estimate Test-3 follow-on power from S0"
```

---

### Task 7: Complete Section-0 evidence packet

**Files:**
- Create: `src/inverted/test3_s0_artifacts.py`
- Create: `tests/test_test3_s0_artifacts.py`

**Interfaces:**
- Produces: `Test3S0ArtifactWriter.write_all(evidence)`.

**Required standard files:**

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

**Required S0 additions:**

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

- [ ] **Step 1: Write artifact-contract tests**

Tests assert every required file exists; `model_calls.jsonl` is byte-empty; every counterfactual has exactly one allowed status; `COMPLETE-EVIDENCE.txt` embeds every generated JSON/JSONL/CSV/TXT file in deterministic relative-path order; `SHA256SUMS.csv` hashes every generated artifact except itself; source hashes/provenance are present.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_test3_s0_artifacts.py -q`

- [ ] **Step 3: Implement concrete writer helpers**

```python
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({str(key) for row in rows for key in row}) or ["empty"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fields})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
```

- [ ] **Step 4: Implement `Test3S0ArtifactWriter.write_all` with an explicit file map**

```python
JSON_FILES = {
    "preregistration.json": "preregistration",
    "config.json": "config",
    "provenance.json": "provenance",
    "failure_atlas.json": "failure_atlas",
    "effect_sizes.json": "effect_sizes",
    "verdict.json": "verdict",
    "source_manifest.json": "source_manifest",
    "power_variance.json": "power_variance",
    "candidate_section1_preregistration.json": "candidate_section1_preregistration",
}

JSONL_FILES = {
    "model_calls.jsonl": "model_calls",
    "events.jsonl": "events",
}

CSV_FILES = {
    "trials.csv": "trials",
    "validator_results.csv": "validator_results",
    "failures.csv": "failures",
    "wins.csv": "wins",
    "losses.csv": "losses",
    "transitions.csv": "transitions",
    "counterfactuals.csv": "counterfactuals",
    "costs.csv": "costs",
    "latency.csv": "latency",
    "tokens.csv": "tokens",
    "cache.csv": "cache",
    "source_integrity.csv": "source_integrity",
    "normalization_coverage.csv": "normalization_coverage",
    "normalization_errors.csv": "normalization_errors",
    "fixed_policy_candidates.csv": "fixed_policy_candidates",
    "adaptive_policy_candidates.csv": "adaptive_policy_candidates",
    "control_results.csv": "control_results",
    "pareto_frontier.csv": "pareto_frontier",
    "unresolved_causal_questions.csv": "unresolved_causal_questions",
    "requires_new_inference.csv": "requires_new_inference",
    "invalid_counterfactuals.csv": "invalid_counterfactuals",
}


class Test3S0ArtifactWriter:
    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)

    def write_all(self, evidence: dict[str, Any]) -> dict[str, str]:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        written: dict[str, Path] = {}

        for relative, key in JSON_FILES.items():
            path = self.run_dir / relative
            _write_json(path, evidence.get(key, {}))
            written[relative] = path

        for relative, key in JSONL_FILES.items():
            path = self.run_dir / relative
            _write_jsonl(path, list(evidence.get(key, [])))
            written[relative] = path

        for relative, key in CSV_FILES.items():
            path = self.run_dir / relative
            _write_csv(path, list(evidence.get(key, [])))
            written[relative] = path

        report = self.run_dir / "report.txt"
        report.write_text(str(evidence.get("report", "")), encoding="utf-8")
        written["report.txt"] = report

        master = self.run_dir / "COMPLETE-EVIDENCE.txt"
        source_paths = sorted(written.values(), key=lambda p: p.relative_to(self.run_dir).as_posix())
        with master.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("VELMA TEST 3 SECTION 0 — COMPLETE EVIDENCE\n")
            for path in source_paths:
                rel = path.relative_to(self.run_dir).as_posix()
                handle.write(f"\n===== BEGIN FILE: {rel} =====\n")
                text = path.read_text(encoding="utf-8")
                handle.write(text)
                if text and not text.endswith("\n"):
                    handle.write("\n")
                handle.write(f"===== END FILE: {rel} =====\n")
        written["COMPLETE-EVIDENCE.txt"] = master

        hashes = self.run_dir / "SHA256SUMS.csv"
        with hashes.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"])
            writer.writeheader()
            for path in sorted(written.values(), key=lambda p: p.relative_to(self.run_dir).as_posix()):
                writer.writerow({
                    "path": path.relative_to(self.run_dir).as_posix(),
                    "sha256": _sha256(path),
                    "bytes": path.stat().st_size,
                })
        written["SHA256SUMS.csv"] = hashes
        return {key: str(path) for key, path in written.items()}
```

The production implementation must also serialize nested CSV values deterministically, matching Test-2's existing behavior, before this task is considered GREEN.

Allowed S0 verdicts are exactly `DISCOVERY_COMPLETE_MODEL_FREE`, `PARTIAL_INPUT_EVIDENCE`, `INSTRUMENTATION_FAILURE`, and `SOURCE_INTEGRITY_FAILURE`.

- [ ] **Step 5: Verify GREEN and commit**

```bash
python -m pytest tests/test_test3_s0_artifacts.py -q
git add src/inverted/test3_s0_artifacts.py tests/test_test3_s0_artifacts.py
git commit -m "feat: write complete Test-3 Section-0 evidence"
```

---

### Task 8: Section-0 CLI and GitHub validation workflow

**Files:**
- Create: `src/inverted/test3_s0_cli.py`
- Create: `tests/test_test3_s0_cli.py`
- Create: `.github/workflows/test3-s0-validation.yml`
- Create: `tests/test_test3_s0_workflow_contract.py`

**Interfaces:**
- `python -m inverted.test3_s0_cli build-manifest`
- `python -m inverted.test3_s0_cli validate-instrument`
- `python -m inverted.test3_s0_cli run`

- [ ] **Step 1: Write CLI zero-model test**

```python
def test_s0_cli_has_no_model_execution_dependency():
    import inverted.test3_s0_cli as cli
    assert "OllamaAdapter" not in cli.__dict__
    assert "run_local_campaign" not in cli.__dict__
```

Also assert emitted master metadata contains `physical_model_calls == 0`.

- [ ] **Step 2: Implement command semantics**

`build-manifest` writes source entries and marks each required source class available/missing. `validate-instrument` accepts partial inputs, exercises the entire S0 pipeline, and emits `PARTIAL_INPUT_EVIDENCE` unless all required source classes are verified. `run` requires all declared source classes to pass integrity and normalization; failures still emit a forensic packet but never `DISCOVERY_COMPLETE_MODEL_FREE`.

- [ ] **Step 3: Write workflow-contract test**

Assert the workflow runs full pytest; generates fresh Test-2 model-free evidence; builds the S0 manifest through the CLI; runs `validate-instrument`, not scientific `run`; contains no Ollama setup/API key/model download/Tier-A command; and uploads the S0 packet.

- [ ] **Step 4: Implement workflow**

```yaml
name: test3-s0-validation

on:
  push:
  pull_request:

jobs:
  test3-s0-model-free:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: "3.14"
      - run: python -m pip install --upgrade pip
      - run: python -m pip install -e ".[test]"
      - name: Full pytest suite
        run: python -m pytest -q
      - name: Generate fresh Test2 model-free predecessor evidence
        run: >-
          python -m inverted.test2_cli model-free
          --config configs/test2-model-free.yaml
          --output-dir test3-s0-inputs
          --run-id test2-model-free
      - name: Build S0 instrument manifest
        run: >-
          python -m inverted.test3_s0_cli build-manifest
          --config configs/test3-s0.yaml
          --test2-model-free test3-s0-inputs/test2-model-free
          --output test3-s0-inputs/source-manifest.json
      - name: Validate Test3 Section 0 instrument
        run: >-
          python -m inverted.test3_s0_cli validate-instrument
          --config configs/test3-s0.yaml
          --source-manifest test3-s0-inputs/source-manifest.json
          --output-dir test3-s0-ci
          --run-id test3-s0-validation
      - name: Upload Test3 S0 validation evidence
        uses: actions/upload-artifact@v4
        with:
          name: test3-s0-instrument-validation-evidence
          path: test3-s0-ci/test3-s0-validation
          if-no-files-found: error
```

- [ ] **Step 5: Verify GREEN and commit**

```bash
python -m pytest tests/test_test3_s0_cli.py tests/test_test3_s0_workflow_contract.py -q
git add src/inverted/test3_s0_cli.py tests/test_test3_s0_cli.py .github/workflows/test3-s0-validation.yml tests/test_test3_s0_workflow_contract.py
git commit -m "ci: add zero-call Test-3 Section-0 validation"
```

---

### Task 9: Full regression, historical-source audit, and scientific S0 execution gate

**Files:**
- No planned production changes.

- [ ] **Step 1: Run the entire repository test suite**

Run: `python -m pytest -q`

Expected: all Test-1/Test-2 tests and all new S0 tests pass.

- [ ] **Step 2: Run local instrument validation**

```bash
python -m inverted.test2_cli model-free \
  --config configs/test2-model-free.yaml \
  --output-dir test3-s0-inputs \
  --run-id test2-model-free

python -m inverted.test3_s0_cli build-manifest \
  --config configs/test3-s0.yaml \
  --test2-model-free test3-s0-inputs/test2-model-free \
  --output test3-s0-inputs/source-manifest.json

python -m inverted.test3_s0_cli validate-instrument \
  --config configs/test3-s0.yaml \
  --source-manifest test3-s0-inputs/source-manifest.json \
  --output-dir test3-s0-ci \
  --run-id test3-s0-validation
```

Expected: zero model calls, complete artifact contract, and `PARTIAL_INPUT_EVIDENCE` until Test-1 and Test-2 Tier-A bundles are also verified in the manifest.

- [ ] **Step 3: Audit required historical sources**

For each source class (`test1`, `test2_tier_a`, `test2_model_free`), record exact source location, run ID, git SHA, bundle digest, evidence tier, completeness, and historical evidence-contract verification. Missing Tier-A evidence is a blocker; never replace it with model-free evidence and never infer missing outcomes.

- [ ] **Step 4: Add the verified Test-1/Test-2 Tier-A sources to the manifest**

Use `write_source_manifest` from Task 2 with the exact locations and digests found in Step 3. No synthetic source entry is permitted.

- [ ] **Step 5: Run scientific S0 only when the manifest is complete**

```bash
python -m inverted.test3_s0_cli run \
  --config configs/test3-s0.yaml \
  --source-manifest test3-s0-inputs/source-manifest.json \
  --output-dir test3-section0 \
  --run-id test3-s0-discovery
```

A complete S0 may nominate S1 arms and a recommended budget range. It may not execute Tier-A inference or freeze S1's exact budget automatically.

- [ ] **Step 6: Run GitHub workflows**

Required green workflows: existing `test`, existing `test2-validation`, and new `test3-s0-validation`.

- [ ] **Step 7: Final forensic review before Section 1**

Confirm every comparison has exactly one counterfactual status; `REQUIRES_NEW_INFERENCE` and `INVALID_COUNTERFACTUAL` rows are preserved; production-policy candidates contain no hidden-gold feature leakage; random/equal-compute controls are measured or queued; conditional gains use task/causal-twin grouping rather than row leakage; power estimates report uncertainty and refuse unsupported exact budgets; candidate S1 preregistration remains `CANDIDATE_ONLY_NOT_PREREGISTERED`; `model_calls.jsonl` is byte-empty and physical-call count is zero; and all generated/source hashes verify.

Do not begin Section 1 or authorize Tier-A calls until the S0 evidence packet has been reviewed as its own experimental result.
