import ast
import json
from collections import Counter

from inverted.qwen_thinking_tuning import (
    BUDGETS,
    COARSE_TEMPERATURES,
    MAX_PHYSICAL_CALLS,
    REFINEMENT_STEPS,
    TASK_FAMILIES,
    BoundedThinkingClient,
    Observation,
    TuningProfile,
    build_budget_trials,
    build_coarse_temperature_trials,
    canonical_tuning_cases,
    is_usable_gain,
    refinement_candidates,
    score_response,
)


def test_case_bank_covers_twelve_families_with_three_distinct_phases():
    cases = canonical_tuning_cases()
    assert len(TASK_FAMILIES) == 12
    assert len(cases) == 36
    counts = Counter((case.family, case.phase) for case in cases)
    assert set(counts.values()) == {1}
    assert {phase for _, phase in counts} == {"budget", "temperature", "validation"}


def test_budget_stage_is_broad_but_bounded():
    trials = build_budget_trials(canonical_tuning_cases())
    assert BUDGETS == (0, 256, 512, 1024, 2048)
    assert len(trials) == 60
    assert sum(trial.physical_calls for trial in trials) == 108
    assert {trial.case.phase for trial in trials} == {"budget"}


def test_coarse_temperature_stage_skips_families_where_thinking_lost():
    budgets = {family: 512 for family in TASK_FAMILIES}
    budgets[TASK_FAMILIES[0]] = 0
    trials = build_coarse_temperature_trials(canonical_tuning_cases(), budgets)
    assert COARSE_TEMPERATURES == (0.4, 0.6, 0.8, 1.0)
    assert len(trials) == 44
    assert sum(trial.physical_calls for trial in trials) == 88
    assert all(trial.profile.thinking_budget > 0 for trial in trials)


def test_temperature_refinement_reaches_thousandths_without_bruteforce():
    assert REFINEMENT_STEPS == (0.05, 0.01, 0.002, 0.001)
    assert refinement_candidates(0.600, 0.050, {0.600}) == (0.55, 0.65)
    assert refinement_candidates(0.603, 0.001, {0.603}) == (0.602, 0.604)
    assert MAX_PHYSICAL_CALLS == 500


def _obs(*, correct=True, completed=True, latency=10.0, tokens=100, quality=None):
    return Observation(
        trial_id="t", family="LOGIC_CONSTRAINTS", case_id="c", stage="refine",
        profile=TuningProfile(512, 0.6), correct=correct, completed=completed,
        latency_s=latency, output_tokens=tokens, thinking_tokens=80,
        physical_calls=2, response_text="ok", done_reasons=("length", "stop"),
        quality=float(correct) if quality is None else float(quality),
    )


def test_usable_gain_prefers_quality_then_meaningful_efficiency():
    incumbent = _obs()
    assert is_usable_gain(incumbent, _obs(correct=True, latency=8.5, tokens=80))
    assert not is_usable_gain(incumbent, _obs(correct=True, latency=9.8, tokens=99))
    assert is_usable_gain(_obs(correct=False), _obs(correct=True, latency=30, tokens=300))
    assert not is_usable_gain(_obs(correct=True), _obs(correct=False, latency=1, tokens=1))


def test_scoring_handles_json_code_expression_and_constraint_writing():
    cases = {case.case_id: case for case in canonical_tuning_cases()}
    code_case = cases["coding-budget"]
    code_text = json.dumps({"answer": [group[0] for group in code_case.expected]})
    assert score_response(code_case, code_text).correct
    arithmetic_case = cases["arithmetic-budget"]
    assert score_response(arithmetic_case, json.dumps(arithmetic_case.expected)).correct
    synthesis_case = cases["synthesis-budget"]
    synthesis_text = json.dumps({"answer": [" ".join(group) + "." for group in synthesis_case.expected]})
    assert score_response(synthesis_case, synthesis_text).correct


class _Response:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return None
    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_bounded_client_uses_two_calls_and_carries_reasoning_forward():
    payloads = []
    responses = iter([
        {"model": "qwen3.5:9b-q8_0", "message": {"thinking": "reason here", "content": ""},
         "eval_count": 512, "done_reason": "length", "total_duration": 2_000_000_000},
        {"model": "qwen3.5:9b-q8_0", "message": {"content": '{"answer":144}'},
         "eval_count": 8, "done_reason": "stop", "total_duration": 200_000_000},
    ])
    def opener(request, *, timeout):
        payloads.append(json.loads(request.data.decode("utf-8")))
        return _Response(next(responses))
    client = BoundedThinkingClient(opener=opener)
    case = next(case for case in canonical_tuning_cases() if case.case_id == "arithmetic-budget")
    result = client.complete(case, TuningProfile(512, 0.6))
    assert result.physical_calls == 2
    assert payloads[0]["think"] is True
    assert payloads[0]["options"]["num_predict"] == 512
    assert payloads[0]["options"]["temperature"] == 0.6
    assert payloads[1]["think"] is False
    assert any(message.get("thinking") == "reason here" for message in payloads[1]["messages"])
    assert result.text == '{"answer":144}'


def test_nonthinking_profile_is_one_call_with_fixed_instruct_sampling():
    payloads = []
    def opener(request, *, timeout):
        payloads.append(json.loads(request.data.decode("utf-8")))
        return _Response({
            "model": "qwen3.5:9b-q8_0", "message": {"content": '{"answer":"B17"}'},
            "eval_count": 6, "done_reason": "stop", "total_duration": 100_000_000,
        })
    client = BoundedThinkingClient(opener=opener)
    case = next(case for case in canonical_tuning_cases() if case.case_id == "extraction-budget")
    result = client.complete(case, TuningProfile(0, 0.7))
    assert result.physical_calls == 1
    assert payloads[0]["think"] is False
    assert payloads[0]["options"]["temperature"] == 0.7
    assert payloads[0]["options"]["top_p"] == 0.8
    assert payloads[0]["options"]["top_k"] == 20
    assert payloads[0]["options"]["presence_penalty"] == 1.5


def _expected_text(case):
    if case.scorer == "exact_json":
        return json.dumps(case.expected, separators=(",", ":"))
    if case.scorer == "exact_text":
        return case.expected
    if case.scorer == "python_expr":
        return case.expected[0]
    if case.scorer == "contains_all":
        return " ".join(case.expected) + "."
    if case.scorer == "python_expr_batch":
        return json.dumps({"answer": [group[0] for group in case.expected]}, separators=(",", ":"))
    if case.scorer == "contains_all_batch":
        return json.dumps({"answer": [" ".join(group) + "." for group in case.expected]}, separators=(",", ":"))
    raise AssertionError(case.scorer)


class _SyntheticClient:
    def complete(self, case, profile):
        from inverted.qwen_thinking_tuning import CompletionResult
        if case.phase == "budget":
            correct = profile.thinking_budget != 0
            latency = {0: 0.2, 256: 3.0, 512: 2.0, 1024: 4.0, 2048: 8.0}[profile.thinking_budget]
            tokens = {0: 10, 256: 100, 512: 80, 1024: 120, 2048: 200}[profile.thinking_budget]
        elif case.phase == "validation" and profile.thinking_budget == 0:
            correct, latency, tokens = False, 0.2, 10
        else:
            correct = True
            distance = abs(profile.temperature - 0.603)
            latency = 1.0 + distance * 100
            tokens = 100 + round(distance * 20000)
        text = _expected_text(case) if correct else "wrong"
        calls = 1 if profile.thinking_budget == 0 else 2
        return CompletionResult(text, "synthetic", calls, latency, tokens, max(0, tokens - 10), ("stop",) * calls, ({},) * calls)


def test_full_adaptive_campaign_reaches_thousandths_and_stays_under_cap(tmp_path):
    from inverted.qwen_thinking_tuning import run_tuning_campaign
    result = run_tuning_campaign(tmp_path, client=_SyntheticClient())
    assert result["status"] == "COMPLETED"
    assert result["physical_calls"] <= MAX_PHYSICAL_CALLS
    assert result["physical_calls"] == 456
    assert set(result["policy"]) == set(TASK_FAMILIES)
    assert all(item["thinking_budget"] == 512 for item in result["policy"].values())
    assert all(item["temperature"] == 0.603 for item in result["policy"].values())
    assert (tmp_path / "observations.jsonl").exists()
    assert (tmp_path / "qwen_tuning_policy.json").exists()


def test_campaign_resume_does_not_repeat_completed_trials(tmp_path):
    from inverted.qwen_thinking_tuning import run_tuning_campaign
    client = _SyntheticClient()
    first = run_tuning_campaign(tmp_path, client=client)
    lines_before = (tmp_path / "observations.jsonl").read_text(encoding="utf-8").splitlines()
    second = run_tuning_campaign(tmp_path, client=client)
    lines_after = (tmp_path / "observations.jsonl").read_text(encoding="utf-8").splitlines()
    assert second["physical_calls"] == first["physical_calls"]
    assert lines_after == lines_before


def test_bounded_client_retains_exact_request_response_envelopes():
    responses = iter([
        {"model": "qwen3.5:9b-q8_0", "message": {"thinking": "r", "content": ""}, "eval_count": 256, "done_reason": "length"},
        {"model": "qwen3.5:9b-q8_0", "message": {"content": '{"answer":144}'}, "eval_count": 3, "done_reason": "stop"},
    ])
    client = BoundedThinkingClient(opener=lambda request, *, timeout: _Response(next(responses)))
    case = next(case for case in canonical_tuning_cases() if case.case_id == "arithmetic-budget")
    result = client.complete(case, TuningProfile(256, 0.8))
    assert result.raw_calls[0]["request"]["think"] is True
    assert result.raw_calls[0]["request"]["options"]["temperature"] == 0.8
    assert result.raw_calls[1]["request"]["think"] is False
    assert result.raw_calls[1]["response"]["message"]["content"] == '{"answer":144}'


def test_campaign_persists_raw_call_evidence(tmp_path):
    from inverted.qwen_thinking_tuning import run_tuning_campaign
    result = run_tuning_campaign(tmp_path, client=_SyntheticClient())
    raw_path = tmp_path / "raw_calls.jsonl"
    assert raw_path.exists()
    rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == result["observation_count"]
    assert sum(len(row["raw_calls"]) for row in rows) == result["physical_calls"]



def test_partial_batch_scoring_exposes_quality_fraction():
    from inverted.qwen_thinking_tuning import TuningCase
    case = TuningCase(
        "batch", "ARITHMETIC", "budget", "x", "exact_json",
        {"answer": [10, 20, 30, 40]},
    )
    result = score_response(case, '{"answer":[10,20,999,40]}')
    assert result.correct is False
    assert result.quality == 0.75


def test_budget_selection_keeps_no_thinking_when_thinking_has_no_usable_gain():
    from inverted.qwen_thinking_tuning import _best_thinking_budget
    baseline = _obs(correct=True, latency=0.5, tokens=20)
    baseline = baseline.__class__(**{**baseline.__dict__, "profile": TuningProfile(0, 0.7)})
    thinking = _obs(correct=True, latency=4.0, tokens=200)
    thinking = thinking.__class__(**{**thinking.__dict__, "profile": TuningProfile(512, 0.6)})
    assert _best_thinking_budget([baseline, thinking]) == 0


def test_every_tuning_case_contains_at_least_three_scored_components():
    cases = canonical_tuning_cases()
    assert len(cases) == 36
    assert all(case.components >= 3 for case in cases)
    assert sum(case.components for case in cases) >= 108


def test_batch_code_scoring_awards_partial_credit_per_expression():
    from inverted.qwen_thinking_tuning import TuningCase
    case = TuningCase(
        "code-batch", "CODING_GENERATION", "budget", "x", "python_expr_batch",
        (("sorted(set(items))",), ("sum(values)",), ("len(values)",)), components=3,
    )
    result = score_response(case, '{"answer":["sorted(set(items))","sum(values)","BAD("]}')
    assert result.correct is False
    assert round(result.quality, 6) == round(2 / 3, 6)


def test_refinement_samples_both_sides_at_each_precision(tmp_path):
    from inverted.qwen_thinking_tuning import run_tuning_campaign
    run_tuning_campaign(tmp_path, client=_SyntheticClient(), max_physical_calls=600)
    rows = [json.loads(line) for line in (tmp_path / "observations.jsonl").read_text(encoding="utf-8").splitlines()]
    refine = [row for row in rows if row["family"] == "LOGIC_CONSTRAINTS" and row["stage"] == "refine"]
    assert len(refine) == 2 * len(REFINEMENT_STEPS)


def test_validation_compares_baseline_with_top_two_tuned_profiles(tmp_path):
    from inverted.qwen_thinking_tuning import run_tuning_campaign
    run_tuning_campaign(tmp_path, client=_SyntheticClient(), max_physical_calls=600)
    rows = [json.loads(line) for line in (tmp_path / "observations.jsonl").read_text(encoding="utf-8").splitlines()]
    validation = [row for row in rows if row["stage"] == "validation"]
    assert len(validation) == len(TASK_FAMILIES) * 3
    assert Counter(row["family"] for row in validation) == {family: 3 for family in TASK_FAMILIES}


def test_runtime_provenance_binds_exact_ollama_version_and_model_digest():
    calls = []
    def opener(request, *, timeout):
        calls.append(request.full_url)
        if request.full_url.endswith('/api/version'):
            return _Response({"version": "0.32.15"})
        if request.full_url.endswith('/api/tags'):
            return _Response({"models": [{"name": "qwen3.5:9b-q8_0", "digest": "sha256:qwen"}]})
        raise AssertionError(request.full_url)
    client = BoundedThinkingClient(opener=opener)
    provenance = client.runtime_provenance()
    assert provenance["model"] == "qwen3.5:9b-q8_0"
    assert provenance["model_digest"] == "sha256:qwen"
    assert provenance["ollama_version"] == "0.32.15"
    assert len(calls) == 2


def test_cli_dry_run_reports_scope_without_model_calls(capsys):
    from inverted.qwen_thinking_tuning import main
    assert main(["--dry-run"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["model"] == "qwen3.5:9b-q8_0"
    assert payload["task_families"] == 12
    assert payload["scored_components"] >= 108
    assert payload["max_physical_calls"] == 500


def test_powershell_launcher_dry_run_executes_repo_local_module():
    import subprocess
    from pathlib import Path
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         "scripts/run-qwen-thinking-tuning.ps1", "--dry-run"],
        cwd=Path.cwd(), capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    assert payload["model"] == "qwen3.5:9b-q8_0"
    assert payload["scored_components"] >= 108


def test_progress_line_resizes_to_terminal_width_without_wrapping():
    from inverted.qwen_thinking_tuning import format_progress_line
    wide = format_progress_line(done=120, total=456, elapsed_s=600, width=120)
    narrow = format_progress_line(done=120, total=456, elapsed_s=600, width=52)
    assert len(wide) <= 120
    assert len(narrow) <= 52
    assert "120 done" in wide and "336 left" in wide
    assert "ETA" in wide and "ETA" in narrow
    assert "[" in wide and "]" in wide


def test_progress_reporter_rechecks_width_on_every_refresh():
    import io
    from inverted.qwen_thinking_tuning import ProgressReporter
    widths = iter((100, 48))
    stream = io.StringIO()
    reporter = ProgressReporter(stream=stream, width_provider=lambda: next(widths), clock=lambda: 10.0)
    reporter.start(done=0, total=456, started_at=0.0)
    reporter.update(done=100, total=456)
    rendered = [part for part in stream.getvalue().split("\r") if part]
    assert len(rendered[0]) <= 100
    assert len(rendered[1]) <= 48
    assert "100" in rendered[1] and "356" in rendered[1]


def test_projected_call_total_accounts_for_adaptive_thinking_families():
    from inverted.qwen_thinking_tuning import projected_physical_calls
    assert projected_physical_calls(12) == 456
    assert projected_physical_calls(0) == 168
    assert projected_physical_calls(6) == 312


def test_campaign_progress_reaches_zero_left_calls(tmp_path):
    import io
    from inverted.qwen_thinking_tuning import ProgressReporter, run_tuning_campaign
    stream = io.StringIO()
    reporter = ProgressReporter(stream=stream, width_provider=lambda: 96)
    result = run_tuning_campaign(tmp_path, client=_SyntheticClient(), progress=reporter)
    rendered = stream.getvalue()
    assert result["physical_calls"] == 456
    assert "456 done" in rendered
    assert "0 left" in rendered
    assert "ETA" in rendered


def test_progress_line_has_tiny_terminal_fallback():
    from inverted.qwen_thinking_tuning import format_progress_line
    tiny = format_progress_line(done=120, total=456, elapsed_s=600, width=24)
    assert len(tiny) <= 24
    assert "120" in tiny and "336" in tiny
