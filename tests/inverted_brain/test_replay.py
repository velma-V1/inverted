from pathlib import Path

from inverted_brain.contracts import InterventionSpec, TrialResult
from inverted_brain.replay import replay_from_snapshot, causal_support


class FakeAdapter:
    def run_intervention(self, workspace, task, intervention, seed):
        passed = intervention.kind == "force"
        return TrialResult(task["id"], "FAKE", "COMPLETE", passed, True, workspace=str(workspace))


def test_replay_detects_planted_causal_intervention(tmp_path):
    snap = tmp_path / "snap"; snap.mkdir(); (snap / "a.txt").write_text("x")
    baseline = replay_from_snapshot({"id":"t"}, snap, InterventionSpec("b","remove","x"), FakeAdapter(), repetitions=3)
    forced = replay_from_snapshot({"id":"t"}, snap, InterventionSpec("f","force","x"), FakeAdapter(), repetitions=3)
    assert baseline.passes == 0
    assert forced.passes == 3
    assert causal_support(baseline, forced)


def test_replay_uses_fresh_snapshot_each_repetition(tmp_path):
    class MutatingAdapter:
        def run_intervention(self, workspace, task, intervention, seed):
            p = Path(workspace) / "a.txt"
            assert p.read_text() == "x"
            p.write_text("changed")
            return TrialResult(task["id"], "FAKE", "COMPLETE", True, True, workspace=str(workspace))
    snap = tmp_path / "snap"; snap.mkdir(); (snap / "a.txt").write_text("x")
    result = replay_from_snapshot({"id":"t"}, snap, InterventionSpec("f","force","x"), MutatingAdapter(), repetitions=2)
    assert result.passes == 2
