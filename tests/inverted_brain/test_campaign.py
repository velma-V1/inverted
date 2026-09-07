import json
from pathlib import Path
import pytest

from inverted_brain.campaign import CampaignController, run_campaign
from inverted_brain.instrument import instrument_adapters, LABEL
from inverted_brain.audit import audit_run


def config():
    return {"frontier_pool":18,"harvest_cases":4,"fresh_holdout":24,"run_ceiling":120}


def test_controller_crash_resume_preserves_run_count(tmp_path):
    c = CampaignController(tmp_path, run_ceiling=3, resume=True)
    c.reserve_run("t1","Q")
    c.advance("frontier")
    resumed = CampaignController(tmp_path, run_ceiling=3, resume=True)
    assert resumed.state["agent_runs"] == 1
    assert resumed.phase == "frontier"
    resumed.reserve_run("t2","Q")
    resumed.reserve_run("t3","Q")
    with pytest.raises(RuntimeError, match="ceiling"):
        resumed.reserve_run("t4","Q")


def test_invalid_evidence_is_not_in_valid_denominator(tmp_path):
    from inverted_brain.contracts import TrialResult
    c = CampaignController(tmp_path, resume=False)
    c.record_trial(TrialResult("t","Q","ABORTED_INFRASTRUCTURE",False,False))
    assert len(c.state["invalid_trials"]) == 1
    assert c.state["completed_trials"] == []


def test_full_instrument_campaign_reaches_retention_and_valid_manifest(tmp_path):
    run_dir = tmp_path / "instrument"
    summary = run_campaign(config(), run_dir, resume=False, adapters=instrument_adapters())
    assert summary["phase"] == "complete"
    assert summary["agent_runs"] <= 120
    assert summary["candidate"] is not None
    assert summary["retention"] is not None
    audit = audit_run(run_dir, run_ceiling=120)
    assert audit["passed"], audit
    holdout = json.loads((run_dir / "holdout_freeze.json").read_text())
    assert len(holdout["task_roots"]) == 24
    assert (run_dir / "sha256_manifest.json").exists()
