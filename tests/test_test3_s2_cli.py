from inverted.test3_s2_artifacts import REQUIRED_S2_FILES
from inverted.test3_s2_cli import S2OllamaAdapter, main


def test_s2_dry_plan_freezes_exact_720_diverse_contract(capsys):
    assert main(["dry-plan", "--config", "configs/test3-s2.yaml"]) == 0
    out = capsys.readouterr().out
    required = (
        "SECTION=S2_ADAPTIVE_ROUTING",
        "PROTOCOL=S2-R1",
        "HOLDOUT=B-R1",
        "EXACT_BUDGET=720",
        "COMBINED_ACTION_BUDGET=732",
        "PROVENANCE_API_CALL_BUDGET=12",
        "ABSOLUTE_ACTION_CEILING=1000",
        "ARM_COUNT=5",
        "MATCHED_CASES=72",
        "CALLS_PER_ARM_TASK=2",
        "PLANNED_PHYSICAL_CALLS=720",
        "QWEN_MODEL=qwen3.5:9b-q8_0",
        "REPAIR_MODEL=cogito:3b-v1-preview-llama-q8_0",
        "LLAMA_MODEL=llama3.1:8b",
        "TIER_A_INFERENCE_AUTHORIZED=false",
    )
    for item in required:
        assert item in out


def test_s2_executor_schema_does_not_cripple_dependency_order_actions():
    allowed = S2OllamaAdapter._EXECUTOR_SCHEMA["properties"]["actions"]["items"]["properties"]["op"]["enum"]
    assert set(allowed) == {"set", "resolve", "delete", "grant", "start"}


def test_s2_real_run_requires_explicit_tier_a_authorization(tmp_path, capsys):
    code = main([
        "run",
        "--config", "configs/test3-s2.yaml",
        "--output-dir", str(tmp_path / "real"),
        "--run-id", "blocked-real",
    ])
    assert code == 2
    assert "TIER_A_AUTHORIZATION_REQUIRED" in capsys.readouterr().err


def test_s2_mock_run_writes_complete_exact_720_evidence(tmp_path):
    output = tmp_path / "mock"
    assert main([
        "mock-run",
        "--config", "configs/test3-s2.yaml",
        "--output-dir", str(output),
        "--run-id", "s2-cli-mock",
    ]) == 0
    assert all((output / name).is_file() for name in REQUIRED_S2_FILES)
    master = (output / "00-MASTER-INDEX.json").read_text(encoding="utf-8")
    assert '"physical_model_calls": 720' in master
    assert '"combined_action_limit": 732' in master
    assert '"combined_external_actions": 720' in master
