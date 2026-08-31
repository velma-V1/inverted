from pathlib import Path
import yaml

from inverted.validation import VALIDATION_SCOPE, run_known_answer_suite


def test_known_answer_suite_covers_all_verdict_classes_and_controls(tmp_path):
    manifest = run_known_answer_suite(tmp_path)
    cases = {case["name"]: case for case in manifest["cases"]}

    assert manifest["evidence_scope"] == VALIDATION_SCOPE
    assert cases["supported"]["expected"] == "SUPPORTED"
    assert cases["supported"]["observed"] == "SUPPORTED"
    assert cases["refuted"]["expected"] == "REFUTED"
    assert cases["refuted"]["observed"] == "REFUTED"
    assert cases["inconclusive"]["expected"] == "INCONCLUSIVE"
    assert cases["inconclusive"]["observed"] == "INCONCLUSIVE"
    assert cases["non_decisive"]["expected"] == "NON-DECISIVE"
    assert cases["non_decisive"]["observed"] == "NON-DECISIVE"
    assert cases["null_effect_not_supported"]["passed"] is True
    assert cases["positive_effect_recovered"]["passed"] is True
    assert all(case["passed"] for case in manifest["cases"])
    assert (tmp_path / "known-answer-manifest.json").exists()


def test_validation_stress_config_covers_full_instrument_matrix():
    raw = yaml.safe_load(Path("configs/validation-stress.yaml").read_text(encoding="utf-8"))
    bench = raw["benchmark"]

    assert set(bench["families"]) == {"state", "policy", "reconciliation"}
    assert set(bench["complexities"]) == {1, 2, 3, 4}
    assert len(set(bench["qualities"])) == 5
    assert len(set(bench["seeds"])) >= 5
    assert bench["epochs"] >= 2
    assert set(bench["arms"]) == {
        "A_DIRECT", "B_DIRECT_CHECKED", "C_SYSTEM", "D_INVERTED", "E_RANDOM_AUDITOR", "F_ORACLE_AUDITOR"
    }
    assert len(raw["models"]) == 3
    assert all(model["provider"] == "mock" for model in raw["models"])
    assert bench["metadata"]["evidence_scope"] == VALIDATION_SCOPE
