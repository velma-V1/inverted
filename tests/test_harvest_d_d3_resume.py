import pytest

from inverted.harvest_d.d3_resume import D3Journal, ProvenanceMismatch, resume_campaign


def test_resume_never_repeats_committed_physical_call(tmp_path):
    journal = D3Journal(tmp_path, provenance={"model_digest": "abc", "config_hash": "cfg"})
    journal.schedule("action-7")
    journal.record_call_received("action-7", "call-7")
    journal.commit_call("action-7", "call-7")
    journal.schedule("action-8")

    state = resume_campaign(tmp_path, current_provenance=journal.provenance)
    assert state.next_action_id == "action-8"
    assert "call-7" in state.completed_call_ids
    assert "action-7" not in state.replayable_action_ids


def test_model_digest_change_requires_segmentation_or_halt(tmp_path):
    journal = D3Journal(tmp_path, provenance={"model_digest": "abc", "config_hash": "cfg"})
    journal.schedule("action-1")
    with pytest.raises(ProvenanceMismatch):
        resume_campaign(
            tmp_path,
            current_provenance={"model_digest": "changed", "config_hash": "cfg"},
        )


def test_received_but_not_committed_call_is_never_silently_replayed(tmp_path):
    journal = D3Journal(tmp_path, provenance={"model_digest": "abc"})
    journal.schedule("action-1")
    journal.record_call_received("action-1", "call-1")

    state = resume_campaign(tmp_path, current_provenance=journal.provenance)
    assert "call-1" in state.incomplete_call_ids
    assert "action-1" not in state.replayable_action_ids
    assert state.requires_reconciliation is True


def test_only_never_started_scheduled_action_is_replayable(tmp_path):
    journal = D3Journal(tmp_path, provenance={"model_digest": "abc"})
    journal.schedule("action-1")
    state = resume_campaign(tmp_path, current_provenance=journal.provenance)
    assert state.replayable_action_ids == ("action-1",)
