from pathlib import Path


def test_handoff_script_is_fail_closed_and_runs_resumable_real_campaign():
    path = Path("scripts/wait-for-010-and-run-inverted.ps1")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    lower = text.lower()

    required = [
        "get-ciminstance win32_process",
        "processpattern",
        "refusing to start",
        "powercfg /change standby-timeout-ac 0",
        "qwen3.5:9b-q8_0",
        "gemma3:12b",
        "devstral-small-2:24b",
        "ollama list",
        "inverted_model_1",
        "inverted_model_2",
        "inverted_model_3",
        "--checkpoint",
        "--resume",
        "--progress",
        "$lastexitcode",
    ]
    for marker in required:
        assert marker in lower, marker

    artifacts = [
        "events.jsonl", "model_calls.jsonl", "trials.csv", "trials.jsonl", "failures.csv",
        "summary.json", "summary.csv", "report.txt", "config.json", "provenance.json",
    ]
    for artifact in artifacts:
        assert artifact in lower

    complete = lower.index("inverted benchmark complete")
    exit_check = lower.index("$lastexitcode")
    artifact_check = lower.index("requiredartifacts")
    assert complete > exit_check
    assert complete > artifact_check


def test_handoff_requires_stable_absence_after_observing_010():
    text = Path("scripts/wait-for-010-and-run-inverted.ps1").read_text(encoding="utf-8").lower()
    assert "$seen010" in text
    assert "$clearchecks" in text
    assert "-ge 3" in text
    assert "start-sleep" in text
