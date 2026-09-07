from inverted.system_harvest.backend import (
    BackendObservation,
    BackendResult,
    FakeExecutionBackend,
    FakeExecutionScript,
)
from inverted.system_harvest.execution import AttemptOutcome


def test_fake_backend_emits_ordered_raw_observations_and_success():
    backend = FakeExecutionBackend({
        ("cell-1", 0): FakeExecutionScript(
            observations=(
                BackendObservation("stream", "artifact", "one\n", "stdout", 1, "text"),
                BackendObservation("stream", "artifact", "two\n", "stdout", 2, "text"),
            ),
            result=BackendResult(AttemptOutcome.CORRECT, "session-1", {"exit_code": 0}),
        )
    })
    observations, result = backend.execute("cell-1", "exec-1", 0)
    assert [item.ordinal for item in observations] == [1, 2]
    assert [item.raw_text for item in observations] == ["one\n", "two\n"]
    assert result.outcome is AttemptOutcome.CORRECT
    assert backend.calls == (("START", "cell-1", "exec-1", 0, None),)


def test_fake_backend_preserves_malformed_text_and_supports_all_outcomes():
    malformed = BackendObservation("stream", "artifact", '{"broken":}\n', "stdout", 1, "jsonl")
    scripts = {}
    for level, outcome in enumerate((AttemptOutcome.INCORRECT, AttemptOutcome.STALL, AttemptOutcome.INFRA_INTERRUPTION)):
        scripts[("cell", level)] = FakeExecutionScript((malformed,), BackendResult(outcome, f"session-{level}", {}))
    backend = FakeExecutionBackend(scripts)
    for level in range(3):
        observations, _ = backend.execute("cell", f"exec-{level}", level)
        assert observations[0].raw_text == '{"broken":}\n'


def test_resume_reuses_declared_session_handle_without_new_semantic_level():
    backend = FakeExecutionBackend({
        ("cell-r", 0): FakeExecutionScript(
            (), BackendResult(AttemptOutcome.CORRECT, "session-r", {"exit_code": 0})
        )
    })
    observations, result = backend.resume("cell-r", "exec-r", 0, "session-r")
    assert observations == ()
    assert result.session_handle == "session-r"
    assert backend.calls == (("RESUME", "cell-r", "exec-r", 0, "session-r"),)


def test_recursive_escalation_scripts_are_keyed_by_escalation_level():
    backend = FakeExecutionBackend({
        ("cell-e", 0): FakeExecutionScript((), BackendResult(AttemptOutcome.INCORRECT, "s0", {})),
        ("cell-e", 1): FakeExecutionScript((), BackendResult(AttemptOutcome.STALL, "s1", {})),
        ("cell-e", 2): FakeExecutionScript((), BackendResult(AttemptOutcome.CORRECT, "s2", {})),
    })
    assert backend.execute("cell-e", "e0", 0)[1].outcome is AttemptOutcome.INCORRECT
    assert backend.execute("cell-e", "e1", 1)[1].outcome is AttemptOutcome.STALL
    assert backend.execute("cell-e", "e2", 2)[1].outcome is AttemptOutcome.CORRECT
