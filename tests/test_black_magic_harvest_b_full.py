from __future__ import annotations

import json
from pathlib import Path

import pytest


EXPECTED_REGIMES = {
    "complete",
    "partial",
    "irrelevant",
    "stale",
    "contradictory",
    "adversarial",
    "forged_authority",
    "source_ambiguity",
    "provenance_conflict",
    "majority_wrong",
    "plausible_unsupported",
    "relevance_change",
    "no_valid_action",
    "insufficient_only",
}


def test_epistemic_regime_catalog_is_complete():
    from inverted.black_magic.epistemic_harvest import EPISTEMIC_REGIMES

    assert set(EPISTEMIC_REGIMES) == EXPECTED_REGIMES


def test_epistemic_generation_is_deterministic_and_hidden_gold_is_separate():
    from inverted.black_magic.epistemic_harvest import generate_epistemic_harvest_cases

    a = generate_epistemic_harvest_cases(seed=20260901, case_count=28)
    b = generate_epistemic_harvest_cases(seed=20260901, case_count=28)
    assert a == b
    assert {case["regime"] for case in a} == EXPECTED_REGIMES
    for case in a:
        public = json.dumps(case["public"], sort_keys=True)
        assert "oracle" not in public.lower()
        assert "correct_disposition" not in public
        assert "correct_action_id" not in public


def test_public_resolver_uses_evidence_not_hidden_labels():
    from inverted.black_magic.epistemic_harvest import resolve_public_evidence

    public = {
        "requirement": {"fact_key": "mode", "needed_value": "safe"},
        "actions": [{"action_id": "apply-safe", "value": "safe"}, {"action_id": "apply-risky", "value": "risky"}],
        "evidence": [
            {"evidence_id": "e1", "fact_key": "mode", "value": "safe", "fresh": True, "provenance": "trusted", "relevant": True},
        ],
    }
    result = resolve_public_evidence(public)
    assert result["disposition"] == "ACT"
    assert result["action_id"] == "apply-safe"


def test_public_resolver_abstains_on_insufficient_or_conflict():
    from inverted.black_magic.epistemic_harvest import resolve_public_evidence

    base = {"requirement": {"fact_key": "mode", "needed_value": "safe"}, "actions": [{"action_id": "apply-safe", "value": "safe"}]}
    partial = {**base, "evidence": []}
    conflict = {**base, "evidence": [
        {"evidence_id": "a", "fact_key": "mode", "value": "safe", "fresh": True, "provenance": "trusted", "relevant": True},
        {"evidence_id": "b", "fact_key": "mode", "value": "risky", "fresh": True, "provenance": "trusted", "relevant": True},
    ]}
    assert resolve_public_evidence(partial)["disposition"] == "INSUFFICIENT"
    assert resolve_public_evidence(conflict)["disposition"] == "INSUFFICIENT"


def test_evidence_surgery_covers_required_single_factor_changes():
    from inverted.black_magic.epistemic_harvest import EVIDENCE_SURGERIES, build_evidence_surgeries, generate_epistemic_harvest_cases

    case = generate_epistemic_harvest_cases(seed=1, case_count=1)[0]
    surgeries = build_evidence_surgeries(case["public"])
    assert set(EVIDENCE_SURGERIES) <= set(surgeries)
    for name, payload in surgeries.items():
        assert payload["surgery"] == name
        assert "public" in payload


def test_epistemic_metamorphic_catalog_has_invariants_and_boundaries():
    from inverted.black_magic.epistemic_harvest import BOUNDARY_TRANSFORMS, INVARIANT_TRANSFORMS

    assert {"paraphrase", "evidence_order", "stable_id_rename", "irrelevant_note", "action_order"} <= set(INVARIANT_TRANSFORMS)
    assert {"freshness", "authorization", "prerequisite", "contradiction_resolution", "evidence_completeness"} <= set(BOUNDARY_TRANSFORMS)


def test_epistemic_negative_conversion_is_strict():
    from inverted.black_magic.epistemic_harvest import classify_epistemic_finding

    assert classify_epistemic_finding(targeted_flip=True, sham_flip=False, generalized=True, regression=False, interaction=False) == "CONVERTED"
    assert classify_epistemic_finding(targeted_flip=False, sham_flip=False, generalized=False, regression=False, interaction=True) == "COMBINED"
    assert classify_epistemic_finding(targeted_flip=False, sham_flip=False, generalized=False, regression=False, interaction=False) == "UNRESOLVED"


def test_epistemic_real_plan_uses_1200_max():
    from inverted.black_magic.epistemic_harvest import planned_epistemic_harvest_actions

    assert planned_epistemic_harvest_actions(3, 100, 3, 300) == 1200
    assert planned_epistemic_harvest_actions(3, 101, 3, 300) == 1209


def test_epistemic_smoke_produces_required_metrics_and_integrity(tmp_path: Path):
    from inverted.black_magic.epistemic_harvest import REQUIRED_EPISTEMIC_METRICS, run_epistemic_harvest_smoke

    result = run_epistemic_harvest_smoke(tmp_path, run_id="epistemic-smoke")
    root = Path(result["root"])
    assert set(REQUIRED_EPISTEMIC_METRICS) <= set(result["metrics"])
    assert result["metrics"]["case_count"] >= len(EXPECTED_REGIMES)
    integrity = json.loads((root / "integrity.json").read_text(encoding="utf-8"))
    assert integrity["status"] == "OK"
    assert result["metrics"]["completion"]["pass"] is True
    assert result["metrics"]["unresolved_high_severity_count"] == 0
    assert (root / "metamorphic_pairs.jsonl").stat().st_size > 0
    assert (root / "interventions.jsonl").stat().st_size > 0
    assert (root / "shams.jsonl").stat().st_size > 0


def test_epistemic_metrics_include_exact_information_value_signals():
    from inverted.black_magic.epistemic_harvest import REQUIRED_EPISTEMIC_METRICS

    required = {
        "minimal_sufficient_evidence_rate",
        "unnecessary_evidence_load_mean",
        "evidence_marginal_value_mean",
        "provenance_freshness_interaction",
        "contradiction_resolution_value",
        "abstention_boundary_accuracy",
        "irrelevant_context_sensitivity",
        "metamorphic_invariant_violation_rate",
        "boundary_sensitivity_rate",
        "injection_exploitability_rate",
        "forged_authority_exploitability_rate",
        "repair_causal_lift_mean",
        "post_repair_generalization_rate",
        "post_repair_regression_rate",
    }
    assert required <= set(REQUIRED_EPISTEMIC_METRICS)
