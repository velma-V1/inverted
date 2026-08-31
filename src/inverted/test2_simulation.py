from __future__ import annotations

from itertools import combinations, permutations
from typing import Any, Iterable

from .oracle import evaluate_task
from .system_executor import generate_candidate
from .tasks import generate_task
from .test2_analysis import OutcomeSnapshot, classify_transition, failure_kill_matrix, summarize_component_effects


CAUSAL = "CAUSAL_REPLAY"
REQUIRES_NEW_INFERENCE = "REQUIRES_NEW_INFERENCE"

_COMPONENTS = (
    "requirement_validator",
    "retry",
    "targeted_repair",
    "oracle_auditor",
    "final_validator",
)
_PROGRESSIVE_ORDER = _COMPONENTS


def analyze_orderings(
    components: tuple[str, ...],
    prompt_changing_components: set[str] | None = None,
) -> list[dict[str, Any]]:
    prompt_changing_components = set(prompt_changing_components or set())
    out = []
    for order in permutations(components):
        changes_upstream_prompt = any(
            component in prompt_changing_components and index < len(order) - 1
            for index, component in enumerate(order)
        )
        out.append({
            "order": " -> ".join(order),
            "components": list(order),
            "changes_upstream_prompt": changes_upstream_prompt,
            "causal_status": REQUIRES_NEW_INFERENCE if changes_upstream_prompt else CAUSAL,
        })
    return out


def _snapshot(task: Any, candidate: Any, *, blocked: bool = False) -> OutcomeSnapshot:
    oracle = evaluate_task(task, candidate.state, candidate.actions)
    fault = candidate.injected_faults[0] if candidate.injected_faults else None
    return OutcomeSnapshot(
        success=bool(oracle.success and not blocked),
        catastrophic=bool(oracle.catastrophic and not blocked),
        blocked=blocked,
        failure_signature=None if oracle.success else (fault or ",".join(oracle.failed_requirement_ids) or "unknown"),
    )


def _cell(family: str, complexity: int, quality: float, seed: int, epoch: int) -> dict[str, Any]:
    task_seed = seed * 1009 + epoch * 9176 + complexity * 31
    task = generate_task(family, complexity, task_seed)
    candidates = [
        generate_candidate(task, quality, seed * 100000 + epoch * 1000 + complexity * 100 + attempt)
        for attempt in range(3)
    ]
    outcomes = [_snapshot(task, candidate) for candidate in candidates]
    perfect = generate_candidate(task, 1.0, seed * 700001 + epoch * 97 + complexity)
    return {
        "task": task,
        "candidates": candidates,
        "outcomes": outcomes,
        "perfect": perfect,
        "id": f"mf-{family}-L{complexity}-q{quality:.2f}-s{seed}-e{epoch}",
        "family": family,
        "complexity": complexity,
        "quality": quality,
        "seed": seed,
        "epoch": epoch,
    }


def _outcome_for_components(cell: dict[str, Any], components: tuple[str, ...]) -> tuple[OutcomeSnapshot, str | None]:
    outcomes: list[OutcomeSnapshot] = cell["outcomes"]
    current = outcomes[0]
    first_defense: str | None = None

    # Retry without a validator cannot identify correctness. It simply obtains a
    # second draw after a failure, which can recover or displace the failure.
    if "retry" in components and not current.success:
        current = outcomes[1]

    # A requirement validator can reject a bad candidate. If retry is also
    # present it searches the remaining fixed draws for a validator-passing one.
    if "requirement_validator" in components and not current.success:
        first_defense = first_defense or "validator"
        if "retry" in components:
            valid = next((outcome for outcome in outcomes[1:] if outcome.success), None)
            current = valid or OutcomeSnapshot(False, catastrophic=False, blocked=True, failure_signature=current.failure_signature)
        else:
            current = OutcomeSnapshot(False, catastrophic=False, blocked=True, failure_signature=current.failure_signature)

    # Targeted repair is an oracle upper-bound in the model-free atlas. The
    # local campaign measures actual model repair; this branch only quantifies
    # the maximum value available from repair on these deterministic tasks.
    if "targeted_repair" in components and not current.success:
        first_defense = first_defense or "repair"
        current = _snapshot(cell["task"], cell["perfect"])

    # Oracle auditor is another explicit model-free ceiling: it may select only
    # among the already-generated fixed candidates, never generate a new one.
    if "oracle_auditor" in components and not current.success:
        first_defense = first_defense or "auditor"
        good = next((outcome for outcome in outcomes if outcome.success), None)
        current = good or OutcomeSnapshot(False, catastrophic=False, blocked=True, failure_signature=current.failure_signature)

    if "final_validator" in components and not current.success and not current.blocked:
        first_defense = first_defense or "final_validator"
        current = OutcomeSnapshot(False, catastrophic=False, blocked=True, failure_signature=current.failure_signature)

    return current, first_defense


def _effect_row(name: str, before: list[OutcomeSnapshot], after: list[OutcomeSnapshot]) -> dict[str, Any]:
    summary = summarize_component_effects(zip(before, after))
    n = len(after)
    return {
        "component": name,
        "n": n,
        "successes": sum(x.success for x in after),
        "success_rate": sum(x.success for x in after) / n if n else 0.0,
        **{key: value for key, value in summary.items() if key != "transitions"},
    }


def run_model_free_atlas(seed_count: int = 10) -> dict[str, Any]:
    if seed_count <= 0:
        raise ValueError("seed_count must be positive")
    qualities = (0.20, 0.40, 0.60, 0.80, 0.95)
    cells = []
    for seed_index in range(seed_count):
        seed = 1001 + seed_index * 997
        for epoch in (0, 1):
            for family in ("state", "policy", "reconciliation"):
                for complexity in (1, 2, 3, 4):
                    for quality in qualities:
                        cells.append(_cell(family, complexity, quality, seed, epoch))

    baseline = [cell["outcomes"][0] for cell in cells]

    standalone_effects = []
    standalone_outcomes: dict[str, list[OutcomeSnapshot]] = {}
    for component in _COMPONENTS:
        after = [_outcome_for_components(cell, (component,))[0] for cell in cells]
        standalone_outcomes[component] = after
        standalone_effects.append(_effect_row(component, baseline, after))

    progressive_effects = []
    progressive_snapshots: dict[int, list[OutcomeSnapshot]] = {0: baseline}
    active: list[str] = []
    previous = baseline
    for step, component in enumerate(_PROGRESSIVE_ORDER, start=1):
        active.append(component)
        after = [_outcome_for_components(cell, tuple(active))[0] for cell in cells]
        row = _effect_row(component, previous, after)
        row.update({"step": step, "stack": " -> ".join(active), "cumulative_success_rate": sum(x.success for x in after) / len(after)})
        progressive_effects.append(row)
        progressive_snapshots[step] = after
        previous = after

    full_components = tuple(_PROGRESSIVE_ORDER)
    full_outcomes = [_outcome_for_components(cell, full_components)[0] for cell in cells]
    ablation_effects = []
    for removed in full_components:
        kept = tuple(component for component in full_components if component != removed)
        after = [_outcome_for_components(cell, kept)[0] for cell in cells]
        row = _effect_row(f"FULL_MINUS_{removed}", full_outcomes, after)
        row.update({"removed": removed, "stack": " -> ".join(kept)})
        ablation_effects.append(row)

    pairwise_interactions = []
    baseline_rate = sum(x.success for x in baseline) / len(baseline)
    standalone_gain = {
        component: (sum(x.success for x in outcomes) / len(outcomes)) - baseline_rate
        for component, outcomes in standalone_outcomes.items()
    }
    for a, b in combinations(_COMPONENTS, 2):
        outcomes = [_outcome_for_components(cell, (a, b))[0] for cell in cells]
        rate = sum(x.success for x in outcomes) / len(outcomes)
        observed_gain = rate - baseline_rate
        expected_additive_gain = standalone_gain[a] + standalone_gain[b]
        interaction = observed_gain - expected_additive_gain
        pairwise_interactions.append({
            "component_a": a,
            "component_b": b,
            "success_rate": rate,
            "observed_gain": observed_gain,
            "expected_additive_gain": expected_additive_gain,
            "interaction": interaction,
            "classification": (
                "SUPER_ADDITIVE" if interaction > 0.01 else
                "ANTAGONISTIC" if interaction < -0.01 else
                "REDUNDANT_OR_ADDITIVE"
            ),
        })

    kill_records = []
    transitions = []
    for cell, before, after in zip(cells, baseline, full_outcomes):
        _, caught_by = _outcome_for_components(cell, full_components)
        fault = before.failure_signature or "none"
        kill_records.append({"fault": fault, "caught_by": caught_by or ("escaped" if not after.success else "none")})
        transitions.append({
            "case_id": cell["id"],
            "family": cell["family"],
            "complexity": cell["complexity"],
            "quality": cell["quality"],
            "transition": classify_transition(before, after),
            "before_success": before.success,
            "after_success": after.success,
            "before_catastrophic": before.catastrophic,
            "after_catastrophic": after.catastrophic,
        })

    saturation = []
    previous_rate = None
    for step in sorted(progressive_snapshots):
        outcomes = progressive_snapshots[step]
        rate = sum(x.success for x in outcomes) / len(outcomes)
        saturation.append({
            "step": step,
            "stack": "BASELINE" if step == 0 else " -> ".join(_PROGRESSIVE_ORDER[:step]),
            "success_rate": rate,
            "marginal_gain": None if previous_rate is None else rate - previous_rate,
        })
        previous_rate = rate

    orderings = analyze_orderings(
        _COMPONENTS,
        prompt_changing_components={"retry", "targeted_repair"},
    )

    # Each base cell is evaluated under baseline plus five standalone/progressive
    # configurations; this is an instrument/model-free unit count, not inference.
    trial_units = len(cells) * 6
    return {
        "evidence_scope": "MODEL_FREE_DETERMINISTIC_ATLAS_NOT_LOCAL_MODEL_EVIDENCE",
        "base_cells": len(cells),
        "trial_units": trial_units,
        "standalone_effects": standalone_effects,
        "progressive_effects": progressive_effects,
        "ablation_effects": ablation_effects,
        "pairwise_interactions": pairwise_interactions,
        "failure_kill_matrix": failure_kill_matrix(kill_records),
        "saturation": saturation,
        "orderings": orderings,
        "outcome_transitions": transitions,
    }
