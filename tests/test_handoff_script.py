from pathlib import Path


def _script_text() -> str:
    return Path("scripts/wait-for-010-and-run-inverted.ps1").read_text(encoding="utf-8")


def test_handoff_script_runs_resumable_real_campaign():
    path = Path("scripts/wait-for-010-and-run-inverted.ps1")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    lower = text.lower()

    required = [
        "get-ciminstance win32_process",
        "processpattern",
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
    lower = _script_text().lower()
    assert "$seen010" in lower
    assert "$clearchecks" in lower
    assert "-ge 3" in lower
    assert "start-sleep" in lower


def test_010_results_are_pushed_before_inverted_but_push_failure_is_nonblocking():
    lower = _script_text().lower()
    required = [
        "velma-alien-stack-lab",
        "experiment/010-computational-basis-atlas",
        "live-summary.json",
        "live-manifest.json",
        "git -c",
        "push",
        "010 results push failed",
        "dump-010evidence",
        "starting real-model inverted benchmark",
    ]
    for marker in required:
        assert marker in lower, marker

    push_attempt = lower.index("010 results push failed")
    dump = lower.index("dump-010evidence")
    inverted_start = lower.index("starting real-model inverted benchmark")
    assert push_attempt < inverted_start
    assert dump < inverted_start

    # A failed 010 push must not route through the fatal handoff path.
    failure_window = lower[push_attempt:inverted_start]
    assert "fail \"010 results push failed" not in failure_window
    assert "throw \"010 results push failed" not in failure_window
