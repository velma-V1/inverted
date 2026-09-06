# HD-NEXT-2A Layered Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete HD-NEXT-2A discovery harness for semantic ingredient discovery, static and progressive layering, recurrence, adaptive coverage, evidence capture, and zero-call saturation auditing without changing frozen HD-NEXT-1 evidence.

**Architecture:** Create a new `inverted.harvest_d.hd_next2` subpackage. Reuse stable lower-level `HarvestCase`, `Disposition`, `stable_hash`, `ModelResponse`, and progress primitives, but keep all NEXT-2 config, treatment construction, budgeting, scheduling, analysis, preregistration, execution, and artifacts isolated from `hd_next1_*`. Each empirical stage `2A-0` through `2A-9` is an independently preregistered campaign; `2A-10` is a zero-inference audit over their preserved evidence.

**Tech Stack:** Python 3.11+, stdlib dataclasses/enums/json/hashlib/random/math/pathlib, existing Ollama HTTP conventions, pytest 8-9.

**Spec:** `docs/superpowers/specs/2026-09-05-hd-next-2-layered-ingredient-discovery-design.md`

## Global Constraints

- Do not modify the scientific behavior of any `hd_next1_*` file.
- Primary models are exactly `qwen2.5:1.5b-instruct-q8_0` and `qwen3.5:9b-q8_0`; Devstral `devstral-small-2:24b` is diagnostic only.
- Every empirical 2A campaign has one combined external/AI action ceiling of 1000 and reserves at least 40 actions for non-model work.
- No blind retries. Repeated calls must be preregistered replications, progressive sequence steps, or explicit recovery interventions.
- Later 2A adaptive stages reserve at least 20% of admissible development capacity for protected exploration.
- A semantic ingredient is not standalone-mapped until it has at least four structurally distinct treatment cells per primary model across at least two operating regions, unless inapplicability is recorded.
- `A -> B -> A` is a legal treatment; exact repeat, refreshed repeat, and compressed re-anchor are distinct recurrence modes.
- Static one-call layering and progressive stateful multi-call layering must remain distinguishable in data and analysis.
- Fresh/sealed cases are not executed anywhere in this plan.
- Runtime can change scheduling order for residency, but may not delete scientifically valuable coverage.
- Every physical call must preserve the raw request, raw provider response, exact rendered layer bytes/hashes, lineage, scheduler rationale, and runtime telemetry required by the spec.

---

## File Structure

Create the following focused package:

```text
src/inverted/harvest_d/hd_next2/
  __init__.py              public NEXT-2A exports only
  types.py                 enums/dataclasses shared by all NEXT-2A modules
  config.py                frozen config loading and validation
  ingredients.py           40-family semantic registry and payload extraction
  cases.py                 operating-region cases and cross-region compounds
  rendering.py             static layers, formulations, dose integrity, hashes
  models.py                message-history Ollama adapter for progressive runs
  progressive.py           transcript forks and stateful recurrence execution
  budget.py                combined-action accounting and runtime profiles
  scheduler.py             residency-safe ordering and protected exploration
  coverage.py              model-specific node/edge coverage ledger
  analysis.py              noise floor, paired effects, interaction-role labels
  stages.py                deterministic planners for 2A-0 through 2A-9
  preregistration.py       immutable per-stage package and SHA-256 manifest
  authorization.py         owner authorization tied to preregistration hash
  artifacts.py             append-only raw/normalized evidence writers
  campaign.py              checkpoint/resume execution of one frozen stage
  audit.py                 zero-call 2A-10 saturation audit
  cli.py                   preregister/execute/resume/audit entry point
configs/harvest-d-hd-next-2a.json
```

Tests mirror responsibilities with `tests/test_harvest_d_hd_next2_*.py`. Do not add a new runtime dependency.

### Task 1: Core contracts and frozen configuration

**Files:**
- Create: `src/inverted/harvest_d/hd_next2/__init__.py`
- Create: `src/inverted/harvest_d/hd_next2/types.py`
- Create: `src/inverted/harvest_d/hd_next2/config.py`
- Create: `configs/harvest-d-hd-next-2a.json`
- Test: `tests/test_harvest_d_hd_next2_config.py`

**Interfaces:**
- Produces: `StageId`, `DeliveryMode`, `RecurrenceMode`, `CoverageState`, `IngredientLayer`, `TreatmentPath`, `StagePlan`, `HDNext2ConfigError`, `load_hd_next2_config(path)`.
- Later tasks consume these exact names; do not rename them.

- [ ] **Step 1: Write the failing config/contract tests**

```python
from inverted.harvest_d.hd_next2.config import load_hd_next2_config
from inverted.harvest_d.hd_next2.types import StageId, DeliveryMode

def test_hd_next2_config_freezes_program_invariants():
    cfg = load_hd_next2_config("configs/harvest-d-hd-next-2a.json")
    assert cfg["experiment_id"] == "HD-NEXT-2A"
    assert cfg["combined_action_ceiling"] == 1000
    assert cfg["non_model_action_reserve"] >= 40
    assert cfg["protected_exploration_fraction"] >= 0.20
    assert cfg["blind_retries_allowed"] is False
    assert set(cfg["models"]) == {"SMALL_A", "QWEN", "DEVSTRAL_24B"}
    assert StageId.A10.value == "2A-10"
    assert DeliveryMode.PROGRESSIVE.value == "PROGRESSIVE"
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m pytest tests/test_harvest_d_hd_next2_config.py -v`
Expected: FAIL because `inverted.harvest_d.hd_next2` does not exist.

- [ ] **Step 3: Implement the minimal core types and config validator**

```python
# types.py
class StageId(str, Enum):
    A0="2A-0"; A1="2A-1"; A2="2A-2"; A3="2A-3"; A4="2A-4"
    A5="2A-5"; A6="2A-6"; A7="2A-7"; A8="2A-8"; A9="2A-9"; A10="2A-10"
class DeliveryMode(str, Enum): STATIC="STATIC"; PROGRESSIVE="PROGRESSIVE"
class RecurrenceMode(str, Enum): NONE="NONE"; REPEAT_EXACT="REPEAT_EXACT"; REPEAT_REFRESHED="REPEAT_REFRESHED"; REANCHOR_COMPRESSED="REANCHOR_COMPRESSED"
class CoverageState(str, Enum):
    UNTESTED="UNTESTED"; PARTIAL="PARTIAL"; NOISY="NOISY"; POSITIVE="POSITIVE"; NEGATIVE="NEGATIVE"
    CONDITIONAL="CONDITIONAL"; ENABLER="ENABLER"; RECURRENT="RECURRENT"; RECOVERY_ONLY="RECOVERY_ONLY"
    DORMANT="DORMANT"; HARMFUL="HARMFUL"
@dataclass(frozen=True)
class IngredientLayer:
    ingredient_id: str; formulation_id: str; dose_id: str
    recurrence: RecurrenceMode=RecurrenceMode.NONE; spacing: str="ADJACENT"; timing: str="UPFRONT"; placement: str="TASK_CONTEXT"; trigger: str="ALWAYS"
@dataclass(frozen=True)
class TreatmentPath:
    treatment_id: str; delivery_mode: DeliveryMode; layers: tuple[IngredientLayer, ...]
@dataclass(frozen=True)
class StagePlan:
    campaign_id: str; stage: StageId; units: tuple[object, ...]; forecast_combined_actions: int
```

`load_hd_next2_config()` must reject any ceiling >1000, reserve <40, protected exploration <0.20, unknown stage, missing primary model, or `blind_retries_allowed=true`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/test_harvest_d_hd_next2_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/inverted/harvest_d/hd_next2 configs/harvest-d-hd-next-2a.json tests/test_harvest_d_hd_next2_config.py
git commit -m "feat: define HD-NEXT-2A core contracts"
```

### Task 2: Semantic ingredient registry and payload extraction

**Files:**
- Create: `src/inverted/harvest_d/hd_next2/ingredients.py`
- Test: `tests/test_harvest_d_hd_next2_ingredients.py`

**Interfaces:**
- Produces: `SemanticIngredient`, `IngredientPayload`, `initial_ingredient_registry()`, `extract_ingredient_payload(case, ingredient_id, dose_id)`.

- [ ] **Step 1: Write failing registry tests**

```python
def test_initial_registry_has_exactly_40_distinct_semantic_families():
    registry = initial_ingredient_registry()
    assert len(registry) == 40
    assert len(set(registry)) == 40
    assert {"OBJECTIVE","CANONICAL_STATE","EVIDENCE_PROVENANCE","DEPENDENCIES","RECOVERY_OPTIONS","EDGE_CASES"} <= set(registry)

def test_core_and_full_payloads_are_semantically_distinct():
    case = generate_d3_cases(partition="development", seed=20260921, per_family=1)[0]
    core = extract_ingredient_payload(case, "CANONICAL_STATE", "CORE")
    full = extract_ingredient_payload(case, "CANONICAL_STATE", "FULL")
    assert core.semantic_atoms < full.semantic_atoms
    assert core.payload != full.payload
```

- [ ] **Step 2: Run RED**
Run: `python -m pytest tests/test_harvest_d_hd_next2_ingredients.py -v`
Expected: FAIL because registry/extractors are absent.

- [ ] **Step 3: Implement the exact 40-family registry**

```python
INITIAL_IDS = (
 "OBJECTIVE","SUBGOAL","CANONICAL_STATE","STATE_DELTA","AUTHORITY","SCOPE","APPROVAL_STATE",
 "EVIDENCE_SUFFICIENCY","EVIDENCE_PROVENANCE","EVIDENCE_FRESHNESS","EVIDENCE_CONTRADICTION",
 "UNCERTAINTY","MISSING_INFORMATION","RISK","CONSEQUENCE","REVERSIBILITY","PRESERVATION_CONSTRAINTS",
 "INVARIANTS","PREREQUISITES","DEPENDENCIES","CAUSAL_STRUCTURE","ADMISSIBLE_ACTIONS","FORBIDDEN_ACTIONS",
 "ACTION_CONSEQUENCES","PRIOR_VERIFIED_STATE","PRIOR_FAILURES","RECOVERY_OPTIONS","ALTERNATIVES",
 "COUNTEREXAMPLE","POSITIVE_EXAMPLE","NEGATIVE_EXAMPLE","DECOMPOSITION","PLAN","SUCCESS_CRITERIA",
 "FAILURE_CRITERIA","VERIFIER_EXPECTATIONS","TOOL_CONSTRAINTS","LIKELY_FAILURE_MODE","EDGE_CASES",
 "HISTORY_COMPRESSED_MEMORY",
)
@dataclass(frozen=True)
class IngredientPayload:
    ingredient_id: str; dose_id: str; payload: dict[str, object]; semantic_atoms: frozenset[str]; source_lineage: tuple[str, ...]
```

Map historical I1-I10 into these meanings through deterministic extraction from `case.metadata["d3_information"]`. Derived families must use only public/model-visible case data and deterministic transforms; if semantically inapplicable, return `None` and record the exclusion instead of fabricating content.

- [ ] **Step 4: Add lineage/inapplicability tests, run GREEN, then commit**

Run: `python -m pytest tests/test_harvest_d_hd_next2_ingredients.py -v`
Expected: PASS.

```bash
git add src/inverted/harvest_d/hd_next2/ingredients.py tests/test_harvest_d_hd_next2_ingredients.py
git commit -m "feat: add semantic ingredient registry"
```

### Task 3: Operating-region and compound case generation

**Files:**
- Create: `src/inverted/harvest_d/hd_next2/cases.py`
- Test: `tests/test_harvest_d_hd_next2_cases.py`

**Interfaces:**
- Produces: `OPERATING_REGIONS`, `describe_hd_next2_case(case)`, `generate_hd_next2_cases(partition, seed, per_region)`, `generate_cross_region_cases(partition, seed)`.

- [ ] **Step 1: Write failing region/compound tests**

```python
def test_development_cases_cover_all_eight_regions():
    cases = generate_hd_next2_cases("development", seed=20260921, per_region=4)
    assert {describe_hd_next2_case(c)["operating_region"] for c in cases} == set(OPERATING_REGIONS)

def test_cross_region_cases_have_two_distinct_region_labels():
    compounds = generate_cross_region_cases("development", seed=20260921)
    assert compounds
    assert all(len(c.metadata["hd_next2_regions"]) == 2 for c in compounds)
```

- [ ] **Step 2: Run RED**
Run: `python -m pytest tests/test_harvest_d_hd_next2_cases.py -v`
Expected: FAIL because NEXT-2 case generation is absent.

- [ ] **Step 3: Implement region mapping plus new policy-ordering cases**

```python
OPERATING_REGIONS = (
 "GLOBAL_INTERACTION","TRANSACTION","VERIFIER_ORACLE","AUTHORITY_SCOPE",
 "EVIDENCE_TRUST","STATE_PRESERVATION","POLICY_ORDERING","STRUCTURAL_DEPENDENCY_RECOVERY",
)
BASE_MAP = {
 "GLOBAL_INTERACTION":"GLOBAL_INTERACTION", "TRANSACTION":"TRANSACTION", "VERIFIER_ORACLE":"VERIFIER_ORACLE",
 "AUTHORITY":"AUTHORITY_SCOPE", "EVIDENCE":"EVIDENCE_TRUST", "CONTEXT":"EVIDENCE_TRUST", "NOVELTY":"EVIDENCE_TRUST",
 "STATE":"STATE_PRESERVATION", "TOPOLOGY":"STRUCTURAL_DEPENDENCY_RECOVERY",
 "RECOVERY":"STRUCTURAL_DEPENDENCY_RECOVERY", "ROUTING":"STRUCTURAL_DEPENDENCY_RECOVERY",
}
```

Add deterministic `POLICY_ORDERING` cases with an exposed answer vocabulary such as `VERIFY_BEFORE_COMMIT` vs `COMMIT_BEFORE_VERIFY`, plus four compound templates: authority+transaction, evidence+global-interaction, state+dependency/recovery, and policy-ordering+verifier-oracle. Never derive expected answers with an LLM.

- [ ] **Step 4: Run GREEN and commit**
Run: `python -m pytest tests/test_harvest_d_hd_next2_cases.py -v`
Expected: PASS.

```bash
git add src/inverted/harvest_d/hd_next2/cases.py tests/test_harvest_d_hd_next2_cases.py
git commit -m "feat: add HD-NEXT-2A operating cases"
```

### Task 4: Static layered rendering, formulations, and dose integrity

**Files:**
- Create: `src/inverted/harvest_d/hd_next2/rendering.py`
- Test: `tests/test_harvest_d_hd_next2_rendering.py`

**Interfaces:**
- Produces: `RenderedLayer`, `RenderedTreatment`, `render_static_treatment(case, treatment)`, `validate_dose_integrity(core, full)`.

- [ ] **Step 1: Write failing tests for recurrence and the D3 dose bug**

```python
def test_static_a_b_a_preserves_three_independent_layers():
    rendered = render_static_treatment(case, treatment_path("OBJECTIVE","DEPENDENCIES","OBJECTIVE"))
    assert [x.ingredient_id for x in rendered.layers] == ["OBJECTIVE","DEPENDENCIES","OBJECTIVE"]
    assert len({x.layer_position for x in rendered.layers}) == 3

def test_adjacent_dose_levels_cannot_render_identically():
    core = render_one(case, "CANONICAL_STATE", "CORE")
    full = render_one(case, "CANONICAL_STATE", "FULL")
    validate_dose_integrity(core, full)
    assert core.sha256 != full.sha256
    assert core.semantic_atoms < full.semantic_atoms
```

- [ ] **Step 2: Run RED**
Run: `python -m pytest tests/test_harvest_d_hd_next2_rendering.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement deterministic renderers**

Support formulation IDs `RAW_PROSE`, `TYPED_FIELDS`, `STRICT_JSON`, `LEDGER`, `MATRIX`, `GRAPH`, `ORDERED_LIST`, `COMPACT_SUMMARY`, and `EXPLICIT_ALTERNATIVES`. `RenderedLayer` stores exact UTF-8 bytes, SHA-256, semantic atom set, approximate token count, start/end byte offsets, approximate start token position, layer position, recurrence mode, spacing, timing, placement, and transform lineage. `RenderedTreatment` stores cumulative context bytes/tokens and critical-information positions. `validate_dose_integrity()` raises if hashes match or FULL is not a strict semantic superset of CORE. An empty-layer `TreatmentPath` renders the true RAW/no-support baseline. Add `render_hd_next1_historical_seed(case)` as a compatibility anchor that delegates to the frozen HD-NEXT-1 renderer with I1/I2/I9/I10 ON, A1/A3 TARGET, ADMISSIBLE_ACTION_MATRIX, DEFAULT ordering, MINIMUM amount, JUST_IN_TIME timing, and SYSTEM_CONTEXT placement.

- [ ] **Step 4: Run GREEN and commit**
Run: `python -m pytest tests/test_harvest_d_hd_next2_rendering.py -v`
Expected: PASS.

```bash
git add src/inverted/harvest_d/hd_next2/rendering.py tests/test_harvest_d_hd_next2_rendering.py
git commit -m "feat: render layered HD-NEXT-2A treatments"
```

### Task 5: Progressive transcript execution and recurrent forks

**Files:**
- Create: `src/inverted/harvest_d/hd_next2/models.py`
- Create: `src/inverted/harvest_d/hd_next2/progressive.py`
- Test: `tests/test_harvest_d_hd_next2_progressive.py`

**Interfaces:**
- Produces: `MessageModelAdapter.complete_messages(messages)`, `HDNext2OllamaAdapter`, `TranscriptState`, `TranscriptBranch`, `fork_transcript(parent)`, `run_progressive_path(...)`.

- [ ] **Step 1: Write failing fork/recurrence tests**

```python
def test_forked_children_share_exact_parent_hash():
    parent = TranscriptState(messages=(msg("user","A"),), outputs=("R1",))
    left = fork_transcript(parent); right = fork_transcript(parent)
    assert left.parent_hash == right.parent_hash == parent.transcript_hash

def test_progressive_a_b_a_makes_three_physical_calls():
    adapter = RecordingMessageAdapter()
    result = run_progressive_path(adapter, case, treatment_path("OBJECTIVE","DEPENDENCIES","OBJECTIVE"))
    assert adapter.calls == 3
    assert [s.layer.ingredient_id for s in result.steps] == ["OBJECTIVE","DEPENDENCIES","OBJECTIVE"]
    assert result.steps[2].parent_transcript_hash == result.steps[1].transcript_hash
```

- [ ] **Step 2: Run RED**
Run: `python -m pytest tests/test_harvest_d_hd_next2_progressive.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement message-history adapter and immutable transcript hashes**

`HDNext2OllamaAdapter.complete_messages()` sends the exact message list to `/api/chat`, stores the full provider payload, and returns existing `ModelResponse`. `TranscriptState` hashes canonical JSON of all messages plus intermediate outputs. `REPEAT_REFRESHED` re-extracts the same semantic ingredient from current observable state; `REANCHOR_COMPRESSED` reuses the same semantic operator with the compressed formulation; `REPEAT_EXACT` reuses identical rendered bytes.

- [ ] **Step 4: Add branch-isolation and no-hidden-state tests, run GREEN, commit**
Run: `python -m pytest tests/test_harvest_d_hd_next2_progressive.py -v`
Expected: PASS.

```bash
git add src/inverted/harvest_d/hd_next2/models.py src/inverted/harvest_d/hd_next2/progressive.py tests/test_harvest_d_hd_next2_progressive.py
git commit -m "feat: add progressive recurrent delivery"
```

### Task 6: Combined-action budget, runtime profiles, and residency-safe scheduling

**Files:**
- Create: `src/inverted/harvest_d/hd_next2/budget.py`
- Create: `src/inverted/harvest_d/hd_next2/scheduler.py`
- Test: `tests/test_harvest_d_hd_next2_budget_scheduler.py`

**Interfaces:**
- Produces: `CombinedActionBudget`, `RuntimeProfile`, `ScheduledUnit`, `schedule_model_blocks(units, seed, protected_fraction)`.

- [ ] **Step 1: Write failing budget/scheduler tests**

```python
def test_budget_counts_model_and_nonmodel_actions_together():
    b = CombinedActionBudget(total_cap=1000, non_model_reserve=40)
    for _ in range(960): b.reserve("model_call")
    with pytest.raises(ValueError): b.reserve("model_call")
    b.reserve("provenance_api_call")
    assert b.total_used == 961

def test_later_stage_keeps_twenty_percent_protected_exploration():
    scheduled = schedule_model_blocks(candidates, seed=7, protected_fraction=.20)
    assert sum(u.protected_exploration for u in scheduled) >= math.ceil(len(scheduled)*.20)
```

- [ ] **Step 2: Run RED**
Run: `python -m pytest tests/test_harvest_d_hd_next2_budget_scheduler.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement shared action accounting and runtime-aware ordering**

`CombinedActionBudget.reserve(kind)` must fail closed before the 1001st combined action and before model calls consume the frozen non-model reserve. `RuntimeProfile` carries the planning anchors from `docs/LOCAL_RUNTIME_EVIDENCE.md`: Small-A 0.09s, Qwen normal 33.97s, Qwen stress 77.22s, Devstral warm median 8.75s. The scheduler groups by model to preserve residency, then seeded-randomizes/balances case-treatment order inside each model block; it never drops a unit because it is slow.

- [ ] **Step 4: Run GREEN and commit**
Run: `python -m pytest tests/test_harvest_d_hd_next2_budget_scheduler.py -v`
Expected: PASS.

```bash
git add src/inverted/harvest_d/hd_next2/budget.py src/inverted/harvest_d/hd_next2/scheduler.py tests/test_harvest_d_hd_next2_budget_scheduler.py
git commit -m "feat: add NEXT-2A action budget and scheduler"
```

### Task 7: Coverage graph and adaptive candidate selection

**Files:**
- Create: `src/inverted/harvest_d/hd_next2/coverage.py`
- Test: `tests/test_harvest_d_hd_next2_coverage.py`

**Interfaces:**
- Produces: `CoverageLedger`, `CoverageNode`, `CoverageEdge`, `SelectionCandidate`, `rank_gap_candidates(...)`.

- [ ] **Step 1: Write failing graph/selection tests**

```python
def test_weak_standalone_node_is_not_retired_without_role_probes():
    ledger = CoverageLedger()
    ledger.record_node("SMALL_A","OBJECTIVE","STATE_PRESERVATION", CoverageState.NEGATIVE)
    assert ledger.retirement_ready("SMALL_A","OBJECTIVE") is False

def test_gap_ranker_preserves_unexplored_neighbors():
    ranked = rank_gap_candidates(ledger, candidates, protected_fraction=.20, seed=11)
    assert any(row.protected_exploration for row in ranked)
    assert all(row.admissible_unexplored_neighbors for row in ranked)
```

- [ ] **Step 2: Run RED**
Run: `python -m pytest tests/test_harvest_d_hd_next2_coverage.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement append-only node/edge evidence state**

Node keys are `(model_key, ingredient_id, formulation_id, operating_region)`; edge keys add ordered parent/child treatment paths and recurrence mode. Record evidence counts, matched wins/losses, noise-bound flag, last stage, and unresolved roles. `retirement_ready()` returns true only after replicated negative transfer across structurally distinct cells plus standalone, pairwise/enabling, recurrent, recovery, and state-triggered probes have no meaningful compensating role.

- [ ] **Step 4: Run GREEN and commit**
Run: `python -m pytest tests/test_harvest_d_hd_next2_coverage.py -v`
Expected: PASS.

```bash
git add src/inverted/harvest_d/hd_next2/coverage.py tests/test_harvest_d_hd_next2_coverage.py
git commit -m "feat: add NEXT-2A coverage graph"
```

### Task 8: Noise calibration and interaction-role analysis

**Files:**
- Create: `src/inverted/harvest_d/hd_next2/analysis.py`
- Test: `tests/test_harvest_d_hd_next2_analysis.py`

**Interfaces:**
- Produces: `NoiseCalibration`, `calibrate_noise(rows)`, `paired_effect(rows, left, right)`, `classify_interaction(...)`.

- [ ] **Step 1: Write failing calibration/effect tests**

```python
def test_noise_floor_uses_worst_identical_cell_instability():
    rows = repeated_rows(success_patterns=[(1,1,1,1),(1,1,0,1)])
    result = calibrate_noise(rows)
    assert result.correctness_noise_floor == 0.25

def test_recurrence_requires_increment_over_parent_path():
    effect = classify_interaction(parent_rate=.50, child_rate=.75, a_rate=.55, b_rate=.50, noise_floor=.10)
    assert effect.role == "RECURRENT"
```

- [ ] **Step 2: Run RED**
Run: `python -m pytest tests/test_harvest_d_hd_next2_analysis.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement exact, dependency-free statistics**

For each four-repeat identical cell compute `correctness_instability=min(successes, failures)/4` and normalized-answer instability `1 - modal_answer_count/4`; model noise floor is the maximum observed instability across eligible repeated cells. `paired_effect()` reports matched n, left-only wins, right-only wins, net wins, rate delta, latency delta, token delta, and exact two-sided sign-test probability using `math.comb`. `classify_interaction()` uses `meaningful=max(config.minimum_effect_margin, model_noise_floor)` and emits only diagnostic 2A roles; it never promotes a shipping recipe.

- [ ] **Step 4: Run GREEN and commit**
Run: `python -m pytest tests/test_harvest_d_hd_next2_analysis.py -v`
Expected: PASS.

```bash
git add src/inverted/harvest_d/hd_next2/analysis.py tests/test_harvest_d_hd_next2_analysis.py
git commit -m "feat: analyze NEXT-2A noise and interactions"
```

### Task 9: Deterministic stage planners for 2A-0 through 2A-9

**Files:**
- Create: `src/inverted/harvest_d/hd_next2/stages.py`
- Test: `tests/test_harvest_d_hd_next2_stages.py`

**Interfaces:**
- Produces: `build_stage_plans(stage, config, cases, registry, coverage, prior_analysis) -> tuple[StagePlan, ...]`. Each returned `StagePlan` is a separately preregisterable campaign under the 1000-action ceiling; the planner must partition, never truncate, an admissible candidate set.

- [ ] **Step 1: Write failing planner invariants**

```python
def test_a0_has_128_primary_anchor_calls_before_diagnostics():
    plans = build_stage_plans(StageId.A0, cfg, cases, registry, empty_coverage(), {})
    assert len(plans) == 1
    plan = plans[0].units
    primary = [u for u in plan if u.model_key in {"SMALL_A","QWEN"}]
    assert len(primary) == 128

def test_a1_gives_every_ingredient_four_cells_per_primary_model():
    plans = build_stage_plans(StageId.A1, cfg, cases, registry, empty_coverage(), {})
    assert len(plans) == 1
    plan = plans[0].units
    for model in ("SMALL_A","QWEN"):
        for ingredient_id in registry:
            rows = [u for u in plan if u.model_key==model and u.primary_ingredient_id==ingredient_id]
            assert len({u.case_id for u in rows}) >= 4
            assert len({u.operating_region for u in rows}) >= 2
```

- [ ] **Step 2: Run RED**
Run: `python -m pytest tests/test_harvest_d_hd_next2_stages.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the frozen planning rules**

`2A-0`: 8 RAW anchor cells/model ×4 repeats plus 8 historical-seed anchor cells/model ×4 repeats = 128 primary calls; add only the config-declared 24B residency diagnostic block.

`2A-1`: for each of 40 ingredients and each primary model choose four applicable structurally distinct cases spanning >=2 regions with seeded balancing; pair each ingredient observation with its same-case RAW control. This is 640 primary calls before any explicitly frozen diagnostic probes.

`2A-2`: choose active, contradictory, strategically important dormant, and protected-exploration ingredients; compare semantically equivalent formulations only.

`2A-3`: matched RAW/A/B/A->B/B->A cells for selected pairs. `2A-4`: required recurrent templates. `2A-5`: depth >=3 with >=20% protected exploration. `2A-6`: triggered vs unconditional matched delivery. `2A-7`: same-failure recovery comparisons. `2A-8`: edge/negative controls. `2A-9`: rank only explicit coverage gaps.

Every planner must freeze candidate IDs, seed, selection reason, selection probability or deterministic rule, unexplored neighbors, model block, and execution position before inference. Candidate ordering uses the tuple `(high_consequence, contradictory_or_model_disagreement, unresolved_role_count, negative_transfer_signal, uncertainty_score, stable_hash(candidate_id))` descending for exploitation; protected exploration is seeded-random from the remaining admissible pool. If the complete admissible set exceeds one campaign, deterministically partition it into consecutive `StagePlan` campaigns whose forecast is <=1000 combined actions; never discard overflow candidates.

- [ ] **Step 4: Add deterministic replay and ceiling tests, run GREEN, commit**
Run: `python -m pytest tests/test_harvest_d_hd_next2_stages.py -v`
Expected: PASS.

```bash
git add src/inverted/harvest_d/hd_next2/stages.py tests/test_harvest_d_hd_next2_stages.py
git commit -m "feat: plan HD-NEXT-2A discovery stages"
```

### Task 10: Preregistration, authorization, and evidence artifacts

**Files:**
- Create: `src/inverted/harvest_d/hd_next2/preregistration.py`
- Create: `src/inverted/harvest_d/hd_next2/authorization.py`
- Create: `src/inverted/harvest_d/hd_next2/artifacts.py`
- Test: `tests/test_harvest_d_hd_next2_preregistration.py`
- Test: `tests/test_harvest_d_hd_next2_artifacts.py`

**Interfaces:**
- Produces: `build_stage_preregistration(...)`, `authorize_stage_execution(...)`, `validate_stage_authorization(...)`, `EvidenceWriter`.

- [ ] **Step 1: Write failing integrity/artifact tests**

```python
def test_authorization_is_bound_to_exact_stage_manifest(tmp_path):
    summary = build_stage_preregistration(repo, tmp_path, cfg, StageId.A1, plan)
    auth = authorize_stage_execution(tmp_path, owner_approved=True)
    (tmp_path/"frozen_schedule.jsonl").write_text("tampered\n")
    with pytest.raises(ValueError, match="integrity"):
        validate_stage_authorization(tmp_path, auth)

def test_writer_captures_required_progressive_lineage(tmp_path):
    writer = EvidenceWriter(tmp_path)
    writer.write_call(sample_progressive_call())
    row = read_one(tmp_path/"normalized_model_calls.jsonl")
    assert {"parent_transcript_hash","layer_sha256","selection_reason","admissible_unexplored_neighbors"} <= set(row)
```

- [ ] **Step 2: Run RED**
Run: `python -m pytest tests/test_harvest_d_hd_next2_preregistration.py tests/test_harvest_d_hd_next2_artifacts.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement immutable preregistration plus append-only evidence files**

Each stage package contains: `config.json`, `ingredient_registry.json`, `frozen_case_manifest.json`, `frozen_schedule.jsonl`, `selection_rule.json`, `action_budget.json`, `runtime_plan.json`, `statistical_rule.json`, `physical_execution_authorization.json` with execution false, and `SHA256SUMS.csv`. Authorization is a separate payload containing stage ID plus manifest hash.

`EvidenceWriter` writes, at minimum: `raw_model_requests.jsonl`, `raw_model_responses.jsonl`, `rendered_layers.jsonl`, `normalized_model_calls.jsonl`, `runtime_telemetry.jsonl`, `physical_call_ledger.jsonl`, `campaign_journal.jsonl`, `scheduler_ledger.jsonl`, `coverage_events.jsonl`, and `action_budget_state.jsonl`. Raw provider telemetry must retain `load_duration`, `prompt_eval_duration`, `eval_duration`, and completion reason when Ollama provides them.

- [ ] **Step 4: Run GREEN and commit**
Run: `python -m pytest tests/test_harvest_d_hd_next2_preregistration.py tests/test_harvest_d_hd_next2_artifacts.py -v`
Expected: PASS.

```bash
git add src/inverted/harvest_d/hd_next2/preregistration.py src/inverted/harvest_d/hd_next2/authorization.py src/inverted/harvest_d/hd_next2/artifacts.py tests/test_harvest_d_hd_next2_preregistration.py tests/test_harvest_d_hd_next2_artifacts.py
git commit -m "feat: preregister and capture NEXT-2A evidence"
```

### Task 11: Stage campaign executor, checkpoint/resume, CLI, and live progress

**Files:**
- Create: `src/inverted/harvest_d/hd_next2/campaign.py`
- Create: `src/inverted/harvest_d/hd_next2/cli.py`
- Test: `tests/test_harvest_d_hd_next2_campaign.py`
- Test: `tests/test_harvest_d_hd_next2_cli.py`

**Interfaces:**
- Produces: `HDNext2StageCampaign.run_authorized(resume=False)`, `main(argv=None)`.

- [ ] **Step 1: Write failing execution/resume tests**

```python
def test_resume_skips_committed_units_without_changing_schedule(tmp_path):
    campaign = fake_stage_campaign(tmp_path, max_units=5)
    campaign.run_authorized(stop_after=2)
    before = (tmp_path/"frozen_schedule.jsonl").read_bytes()
    result = campaign.run_authorized(resume=True)
    assert result.committed_units == 5
    assert (tmp_path/"frozen_schedule.jsonl").read_bytes() == before
    assert len(read_jsonl(tmp_path/"physical_call_ledger.jsonl")) == 5
```

- [ ] **Step 2: Run RED**
Run: `python -m pytest tests/test_harvest_d_hd_next2_campaign.py tests/test_harvest_d_hd_next2_cli.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement one-stage-at-a-time execution**

`HDNext2StageCampaign` loads the frozen schedule and authorization, reconstructs committed unit IDs from the physical ledger, and executes only missing units. Static treatments make one physical call; progressive treatments call once per layer and commit each step with parent transcript lineage. Parse candidate answers separately from system-owned authorization/disposition. On adapter/infra failure, record the failed physical call once and do not retry automatically.

Use existing `InPlaceProgress`, but progress total is the frozen scheduled physical-call count, not the 1000-action ceiling. Also expose `calls_used/calls_available`, current stage/model/case, elapsed time, and runtime-derived ETA. The progress renderer must remain observability-only.

CLI contract:

```text
python -m inverted.harvest_d.hd_next2.cli --stage 2A-1 --campaign-index 0 --config configs/harvest-d-hd-next-2a.json --output <dir>
python -m inverted.harvest_d.hd_next2.cli --stage 2A-1 --campaign-index 0 --config ... --output <dir> --execute --owner-authorization <json>
python -m inverted.harvest_d.hd_next2.cli --stage 2A-1 --campaign-index 0 --config ... --output <dir> --execute --owner-authorization <json> --resume
```

Default invocation preregisters the selected deterministic `StagePlan` with zero inference. `--campaign-index` selects one plan when a stage partitions into multiple campaigns; CLI prints the total available plan count. Execution requires owner authorization before Ollama preflight.

- [ ] **Step 4: Run GREEN and commit**
Run: `python -m pytest tests/test_harvest_d_hd_next2_campaign.py tests/test_harvest_d_hd_next2_cli.py -v`
Expected: PASS.

```bash
git add src/inverted/harvest_d/hd_next2/campaign.py src/inverted/harvest_d/hd_next2/cli.py tests/test_harvest_d_hd_next2_campaign.py tests/test_harvest_d_hd_next2_cli.py
git commit -m "feat: execute resumable NEXT-2A stages"
```

### Task 12: Zero-call 2A-10 saturation audit and next-gap specification

**Files:**
- Create: `src/inverted/harvest_d/hd_next2/audit.py`
- Test: `tests/test_harvest_d_hd_next2_audit.py`

**Interfaces:**
- Produces: `SaturationAudit`, `audit_2a_saturation(evidence_roots, config)`, `write_gap_campaign_spec(audit, output)`.

- [ ] **Step 1: Write failing freeze/gap tests**

```python
def test_a10_refuses_freeze_when_recurrence_gap_is_high_priority():
    audit = audit_2a_saturation([fixture_root("missing-recurrence")], cfg)
    assert audit.discovery_frozen is False
    assert "RECURRENCE_COVERAGE" in audit.blockers

def test_a10_is_zero_inference():
    audit = audit_2a_saturation([fixture_root("complete")], cfg)
    assert audit.physical_model_calls == 0
```

- [ ] **Step 2: Run RED**
Run: `python -m pytest tests/test_harvest_d_hd_next2_audit.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the ten freeze criteria exactly**

The audit must fail closed unless all spec criteria are satisfied: broad standalone coverage, role testing for important weak/dormant ingredients, challenged positive/negative/contradictory pairwise edges, justified recurrence coverage, state/recovery trigger coverage, protected exploration, resolved-or-carried noisy contradictions, no runtime-driven evidence hole, explicit unresolved ledger entries, and evidence that further broad discovery is mostly redundant.

If not frozen, emit `next_gap_campaign.json` containing only evidence-derived gaps: required stage, model(s), ingredient/path, operating region, missing role, minimum matched cells, and why existing evidence is insufficient. It may not invent a winner or spend inference.

- [ ] **Step 4: Run GREEN and commit**
Run: `python -m pytest tests/test_harvest_d_hd_next2_audit.py -v`
Expected: PASS.

```bash
git add src/inverted/harvest_d/hd_next2/audit.py tests/test_harvest_d_hd_next2_audit.py
git commit -m "feat: add NEXT-2A saturation audit"
```

### Task 13: Full fake-campaign contract, regression suite, and operator docs

**Files:**
- Create: `tests/test_harvest_d_hd_next2_full_contract.py`
- Modify: `README.md`
- Modify: `TESTING.md` only if command examples need clarification; do not change scientific rules.

**Interfaces:**
- Validates all prior interfaces together with no real Ollama calls.

- [ ] **Step 1: Write a deterministic fake adapter full-contract test**

```python
def test_fake_a0_and_a1_preserve_budget_lineage_and_coverage(tmp_path):
    run_fake_stage(StageId.A0, tmp_path/"a0")
    run_fake_stage(StageId.A1, tmp_path/"a1", prior=[tmp_path/"a0"])
    assert combined_actions(tmp_path/"a1") <= 1000
    assert no_automatic_retries(tmp_path/"a1")
    assert every_initial_ingredient_has_required_primary_coverage(tmp_path/"a1")
    assert raw_and_normalized_ledgers_join_one_to_one(tmp_path/"a1")
```

Also add a progressive fixture proving `A->B->A` produces three uniquely identified physical calls and a static fixture proving the same symbols in STATIC mode produce one call with three independently hashed layers.

- [ ] **Step 2: Run the new full-contract tests**
Run: `python -m pytest tests/test_harvest_d_hd_next2_full_contract.py -v`
Expected: PASS after Tasks 1-12 are complete.

- [ ] **Step 3: Add concise operator commands to README**

Document the three-stage workflow explicitly: preregister a stage, create owner authorization from the exact manifest, then execute/resume that frozen stage. State that 2A-10 consumes prior evidence only and that 2B-2H are intentionally out of this implementation plan.

- [ ] **Step 4: Run all NEXT-2A tests**

Run: `python -m pytest tests/test_harvest_d_hd_next2_*.py -v`
Expected: all NEXT-2A tests PASS.

- [ ] **Step 5: Run the full repository suite**

Run: `python -m pytest -q`
Expected: no failures; the existing native-Windows `vp` skip may remain.

- [ ] **Step 6: Verify repository hygiene**

Run:
```bash
git diff --check
git status --short
```
Expected: no whitespace errors; only intended NEXT-2A/code/doc changes staged for the final integration commit. Existing local `.tmp_*`, `runs/`, and `__pycache__` artifacts remain untracked and must not be added.

- [ ] **Step 7: Commit final integration/docs**

```bash
git add README.md TESTING.md src/inverted/harvest_d/hd_next2 tests/test_harvest_d_hd_next2_full_contract.py
git commit -m "test: verify HD-NEXT-2A discovery harness"
```

## Execution Boundary After This Plan

Completion of this plan means the **instrument is ready** for owner-authorized HD-NEXT-2A campaigns; it does not mean 2A evidence has been collected or that a recipe has been promoted. Run 2A-0 first, then preregister each later stage from the evidence available at that boundary. Do not implement 2B-2H until 2A-10 either freezes discovery or emits the exact additional gap-closure campaign required.
## Test Helper Contract

The abbreviated test snippets above use local fixtures only; they are not production interfaces. Define them in the test module that first needs them. Use these exact semantics:

```python
def first_case():
    return generate_hd_next2_cases("development", seed=20260921, per_region=4)[0]

def treatment_path(*ingredient_ids, delivery_mode=DeliveryMode.STATIC):
    layers = tuple(IngredientLayer(i, "TYPED_FIELDS", "CORE") for i in ingredient_ids)
    return TreatmentPath(stable_hash([delivery_mode.value, ingredient_ids]), delivery_mode, layers)

def read_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]

def empty_coverage():
    return CoverageLedger()
```

`RecordingMessageAdapter`, fake campaign builders, fixture evidence roots, and synthetic row builders must return the production dataclasses defined by the task under test; they may not bypass budget, lineage, scheduler, or parser code. Fake adapters return deterministic `ModelResponse` objects and increment one counter per physical invocation. Replace shorthand names such as `case`, `cfg`, `registry`, `candidates`, `repo`, and `plan` in each test with explicit pytest fixtures constructed from these production interfaces.
