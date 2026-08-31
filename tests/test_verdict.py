from types import SimpleNamespace
from inverted.verdict import decide_verdict


def base_summary():
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
        "model_advantage": {"m1": 0.1, "m2": 0.2, "m3": -0.01},
        "seed_advantage": {"1": 0.1, "2": 0.2, "3": 0.05, "4": -0.01},
    }


def cfg(decisive=True, minimum_primary_trials=180):
    return SimpleNamespace(decisive=decisive, minimum_primary_trials=minimum_primary_trials)


def test_supported_requires_all_gates():
    result = decide_verdict(base_summary(), cfg())
    assert result["verdict"] == "SUPPORTED"
    assert all(g["passed"] for g in result["gates"])


def test_non_decisive_never_emits_scientific_verdict():
    result = decide_verdict(base_summary(), cfg(decisive=False))
    assert result["verdict"] == "NON-DECISIVE"


def test_refuted_when_ci_rules_out_meaningful_advantage():
    s = base_summary()
    s["primary"]["d_minus_a"] = -0.02
    s["primary"]["ci95"] = {"lower": -0.07, "upper": 0.01}
    s["primary"]["equal_budget_diff"] = -0.01
    result = decide_verdict(s, cfg())
    assert result["verdict"] == "REFUTED"


def test_inconclusive_for_small_uncertain_effect():
    s = base_summary()
    s["primary"]["d_minus_a"] = 0.06
    s["primary"]["ci95"] = {"lower": -0.01, "upper": 0.13}
    s["primary"]["equal_budget_diff"] = 0.04
    result = decide_verdict(s, cfg())
    assert result["verdict"] == "INCONCLUSIVE"


def test_insufficient_independent_clusters_is_non_decisive_even_with_many_repeated_rows():
    s = base_summary()
    s["by_arm"]["A_DIRECT"]["n"] = 2700
    s["by_arm"]["D_INVERTED"]["n"] = 2700
    s["primary"]["independent_task_clusters"] = 20
    result = decide_verdict(s, cfg())
    assert result["verdict"] == "NON-DECISIVE"
    assert result["observations"]["independent_task_clusters"] == 20


def test_missing_cluster_count_cannot_accidentally_pass_power_gate():
    s = base_summary()
    del s["primary"]["independent_task_clusters"]
    assert decide_verdict(s, cfg())["verdict"] == "NON-DECISIVE"
