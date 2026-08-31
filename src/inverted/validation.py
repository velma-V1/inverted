from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .arms import Arm
from .models import MockModelAdapter
from .runner import ExperimentConfig, run_experiment
from .statistics import aggregate_trials
from .verdict import decide_verdict

VALIDATION_SCOPE = "INSTRUMENT VALIDATION — NOT ARCHITECTURE EVIDENCE"


def _runner_case(executor_accuracy: float, auditor_accuracy: float, *, run_id: str, decisive: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    config = ExperimentConfig(
        families=("state", "policy", "reconciliation"),
        complexities=(1, 2),
        qualities=(0.80, 0.95),
        seeds=tuple(range(1, 9)),
        epochs=1,
        arms=tuple(a.value for a in Arm),
        max_candidates=3,
        max_tokens_per_trial=10000,
        decisive=decisive,
        minimum_primary_trials=10,
        bootstrap_samples=500,
        bootstrap_seed=1,
        metadata={"evidence_scope": VALIDATION_SCOPE},
    )
    model = MockModelAdapter(
        model=f"known-answer-{run_id}",
        seed=7,
        executor_accuracy=executor_accuracy,
        auditor_accuracy=auditor_accuracy,
    )
    result = run_experiment(config, [model], run_id=run_id)
    summary = aggregate_trials(result.trials, config.bootstrap_samples, config.bootstrap_seed)
    verdict = decide_verdict(summary, config)
    return verdict, summary


def _base_summary() -> dict[str, Any]:
    return {
        "primary": {
            "d_minus_a": 0.15,
            "ci95": {"lower": 0.08, "upper": 0.22},
            "equal_budget_diff": 0.12,
            "d_minus_b": -0.02,
            "independent_task_clusters": 300,
        },
        "by_arm": {
            "A_DIRECT": {"n": 300, "success_rate": 0.60, "catastrophic_rate": 0.02},
            "B_DIRECT_CHECKED": {"n": 300, "success_rate": 0.77, "catastrophic_rate": 0.02},
            "D_INVERTED": {"n": 300, "success_rate": 0.75, "catastrophic_rate": 0.02},
            "E_RANDOM_AUDITOR": {"n": 300, "success_rate": 0.55, "catastrophic_rate": 0.02},
        },
        "family_advantage": {"state": 0.12, "policy": 0.11, "reconciliation": 0.08},
        "model_advantage": {"m1": 0.10, "m2": 0.20, "m3": -0.01},
        "seed_advantage": {"1": 0.10, "2": 0.20, "3": 0.05, "4": -0.01},
    }


def _fixture_verdict(summary: dict[str, Any], *, decisive: bool = True) -> dict[str, Any]:
    config = SimpleNamespace(decisive=decisive, minimum_primary_trials=180)
    return decide_verdict(summary, config)


def _case(name: str, expected: str, observed: str, *, mode: str, details: dict[str, Any] | None = None, passed: bool | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "expected": expected,
        "observed": observed,
        "mode": mode,
        "passed": (observed == expected) if passed is None else bool(passed),
        "details": details or {},
    }


def run_known_answer_suite(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, Any]] = []

    supported, supported_summary = _runner_case(0.20, 1.00, run_id="validation-supported")
    cases.append(_case(
        "supported", "SUPPORTED", supported["verdict"], mode="runner",
        details={"d_minus_a": supported_summary["primary"]["d_minus_a"], "ci95": supported_summary["primary"]["ci95"]},
    ))

    refuted, refuted_summary = _runner_case(1.00, 0.00, run_id="validation-refuted")
    cases.append(_case(
        "refuted", "REFUTED", refuted["verdict"], mode="runner",
        details={"d_minus_a": refuted_summary["primary"]["d_minus_a"], "ci95": refuted_summary["primary"]["ci95"]},
    ))

    inconclusive_summary = _base_summary()
    inconclusive_summary["primary"]["d_minus_a"] = 0.06
    inconclusive_summary["primary"]["ci95"] = {"lower": -0.01, "upper": 0.13}
    inconclusive_summary["primary"]["equal_budget_diff"] = 0.04
    inconclusive = _fixture_verdict(inconclusive_summary)
    cases.append(_case("inconclusive", "INCONCLUSIVE", inconclusive["verdict"], mode="deterministic-summary"))

    non_decisive = _fixture_verdict(_base_summary(), decisive=False)
    cases.append(_case("non_decisive", "NON-DECISIVE", non_decisive["verdict"], mode="deterministic-summary"))

    null_summary = _base_summary()
    null_summary["primary"]["d_minus_a"] = 0.0
    null_summary["primary"]["ci95"] = {"lower": -0.04, "upper": 0.04}
    null_summary["primary"]["equal_budget_diff"] = 0.0
    null_summary["by_arm"]["D_INVERTED"]["success_rate"] = null_summary["by_arm"]["A_DIRECT"]["success_rate"]
    null_summary["family_advantage"] = {"state": 0.0, "policy": 0.0, "reconciliation": 0.0}
    null_summary["model_advantage"] = {"m1": 0.0, "m2": 0.0, "m3": 0.0}
    null_summary["seed_advantage"] = {"1": 0.0, "2": 0.0, "3": 0.0, "4": 0.0}
    null_verdict = _fixture_verdict(null_summary)
    cases.append(_case(
        "null_effect_not_supported", "NOT_SUPPORTED", null_verdict["verdict"], mode="deterministic-summary",
        passed=null_verdict["verdict"] != "SUPPORTED",
    ))

    positive_summary = _base_summary()
    positive_verdict = _fixture_verdict(positive_summary)
    cases.append(_case(
        "positive_effect_recovered", "SUPPORTED", positive_verdict["verdict"], mode="deterministic-summary",
        passed=positive_verdict["verdict"] == "SUPPORTED",
    ))

    manifest = {
        "evidence_scope": VALIDATION_SCOPE,
        "all_passed": all(case["passed"] for case in cases),
        "cases": cases,
    }
    (output / "known-answer-manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
