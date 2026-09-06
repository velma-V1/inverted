import csv
import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from inverted.harvest_d.hd_next2.authorization import (
    authorize_stage_execution,
    validate_stage_authorization,
)
from inverted.harvest_d.hd_next2.config import canonical_a0_planner_config
from inverted.harvest_d.hd_next2.preregistration import FROZEN_INPUT_FILES, build_stage_preregistration, canonical_a0_payloads_for_commit
from inverted.harvest_d.hd_next2.stages import build_canonical_a0_plan
from inverted.harvest_d.hd_next2.types import StageId


FROZEN_FILES = {
    "config.json", "ingredient_registry.json", "frozen_case_manifest.json",
    "frozen_schedule.jsonl", "selection_rule.json", "action_budget.json",
    "runtime_plan.json", "statistical_rule.json",
    "physical_execution_authorization.json", "SHA256SUMS.csv",
}
OWNER_SECRET = b"task10-test-owner-secret-32-bytes!"


def _build(root: Path):
    return build_stage_preregistration(
        Path.cwd(), root, canonical_a0_planner_config(), StageId.A0,
        build_canonical_a0_plan(),
    )


def _rewrite_checksums(root: Path):
    with (root / "SHA256SUMS.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("filename", "sha256"), lineterminator="\n")
        writer.writeheader()
        for filename in FROZEN_INPUT_FILES:
            writer.writerow({
                "filename": filename,
                "sha256": hashlib.sha256((root / filename).read_bytes()).hexdigest(),
            })


def test_preregistration_freezes_exact_deterministic_a0_package(tmp_path):
    first = _build(tmp_path / "first")
    second = _build(tmp_path / "second")
    assert {p.name for p in (tmp_path / "first").iterdir()} == FROZEN_FILES
    assert {p.name: p.read_bytes() for p in (tmp_path / "first").iterdir()} == {
        p.name: p.read_bytes() for p in (tmp_path / "second").iterdir()
    }
    assert first["stage_id"] == "2A-0"
    assert len((tmp_path / "first" / "frozen_schedule.jsonl").read_text().splitlines()) == 192
    assert json.loads((tmp_path / "first" / "physical_execution_authorization.json").read_text())["execution"] is False


def test_checksums_bind_every_frozen_input_without_self_hash(tmp_path):
    _build(tmp_path)
    rows = list(csv.DictReader((tmp_path / "SHA256SUMS.csv").open(newline="", encoding="utf-8")))
    assert {r["filename"] for r in rows} == FROZEN_FILES - {"SHA256SUMS.csv"}
    for row in rows:
        assert row["sha256"] == hashlib.sha256((tmp_path / row["filename"]).read_bytes()).hexdigest()


def test_preregistration_rejects_non_a0_and_noncanonical_plan(tmp_path):
    with pytest.raises(ValueError, match="A0"):
        build_stage_preregistration(Path.cwd(), tmp_path / "wrong-stage", canonical_a0_planner_config(), StageId.A1, build_canonical_a0_plan())
    plan = build_canonical_a0_plan()
    forged = replace(plan, units=plan.units[:-1])
    with pytest.raises(ValueError, match="canonical"):
        build_stage_preregistration(Path.cwd(), tmp_path / "wrong-plan", canonical_a0_planner_config(), StageId.A0, forged)


def test_preregistration_rejects_config_extras_and_requires_repo_commit(tmp_path):
    config = canonical_a0_planner_config()
    config["caller_extra"] = "must-not-enter-frozen-bytes"
    with pytest.raises(ValueError, match="canonical A0 config"):
        build_stage_preregistration(Path.cwd(), tmp_path / "extra", config, StageId.A0, build_canonical_a0_plan())
    with pytest.raises(ValueError, match="commit identity"):
        build_stage_preregistration(tmp_path / "not-a-repo", tmp_path / "missing-commit", canonical_a0_planner_config(), StageId.A0, build_canonical_a0_plan())
    assert not (tmp_path / "missing-commit").exists()


def test_preregistration_refuses_destructive_overwrite(tmp_path):
    target = tmp_path / "package"
    target.mkdir()
    marker = target / "keep.txt"
    marker.write_text("owner data")
    with pytest.raises(FileExistsError, match="exists"):
        _build(target)
    assert marker.read_text() == "owner data"


def test_authorization_requires_true_owner_approval_and_validates_exact_package(tmp_path):
    from inverted.harvest_d.hd_next2.authorization import prepare_stage_authorization
    _build(tmp_path)
    prepared = prepare_stage_authorization(tmp_path)
    assert "owner_hmac_sha256" not in prepared
    false_auth = authorize_stage_execution(prepared, owner_approved=False, owner_secret=OWNER_SECRET)
    with pytest.raises(ValueError, match="approved"):
        validate_stage_authorization(tmp_path, false_auth, owner_secret=OWNER_SECRET)
    forged = {**false_auth, "owner_approved": True}
    with pytest.raises(ValueError, match="forged"):
        validate_stage_authorization(tmp_path, forged, owner_secret=OWNER_SECRET)
    auth = authorize_stage_execution(prepared, owner_approved=True, owner_secret=OWNER_SECRET)
    assert validate_stage_authorization(tmp_path, auth, owner_secret=OWNER_SECRET)["stage_id"] == "2A-0"


def test_authorization_hmac_cannot_be_minted_or_validated_without_owner_secret(tmp_path):
    from inverted.harvest_d.hd_next2.authorization import prepare_stage_authorization
    _build(tmp_path)
    prepared = prepare_stage_authorization(tmp_path)
    with pytest.raises((TypeError, ValueError)):
        authorize_stage_execution(prepared, owner_approved=True, owner_secret=b"public")
    auth = authorize_stage_execution(prepared, owner_approved=True, owner_secret=OWNER_SECRET)
    with pytest.raises(ValueError, match="HMAC"):
        validate_stage_authorization(tmp_path, auth, owner_secret=b"different-owner-secret-32-bytes!!")
    replaced = {**auth, "manifest_sha256": "0" * 64}
    with pytest.raises(ValueError):
        validate_stage_authorization(tmp_path, replaced, owner_secret=OWNER_SECRET)
    with pytest.raises(ValueError, match="malformed"):
        validate_stage_authorization(tmp_path, {**auth, "unsigned_extra": True}, owner_secret=OWNER_SECRET)


@pytest.mark.parametrize("filename", ["frozen_schedule.jsonl", "config.json", "ingredient_registry.json"])
def test_authorization_recomputes_hashes_and_rejects_tampered_frozen_file(tmp_path, filename):
    from inverted.harvest_d.hd_next2.authorization import prepare_stage_authorization
    _build(tmp_path)
    auth = authorize_stage_execution(prepare_stage_authorization(tmp_path), owner_approved=True, owner_secret=OWNER_SECRET)
    (tmp_path / filename).write_bytes((tmp_path / filename).read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="integrity"):
        validate_stage_authorization(tmp_path, auth, owner_secret=OWNER_SECRET)


def test_authorization_rejects_missing_wrong_stage_forged_or_stale_payload(tmp_path):
    from inverted.harvest_d.hd_next2.authorization import prepare_stage_authorization
    _build(tmp_path)
    auth = authorize_stage_execution(prepare_stage_authorization(tmp_path), owner_approved=True, owner_secret=OWNER_SECRET)
    cases = [
        {**auth, "stage_id": "2A-1"},
        {**auth, "owner_approved": False},
        {**auth, "manifest_sha256": "0" * 64},
        {**auth, "checksum_sha256": "0" * 64},
    ]
    for payload in cases:
        with pytest.raises(ValueError):
            validate_stage_authorization(tmp_path, payload, owner_secret=OWNER_SECRET)
    (tmp_path / "runtime_plan.json").unlink()
    with pytest.raises(ValueError, match="integrity"):
        validate_stage_authorization(tmp_path, auth, owner_secret=OWNER_SECRET)


def test_append_only_evidence_files_do_not_invalidate_authorization(tmp_path):
    from inverted.harvest_d.hd_next2.authorization import prepare_stage_authorization
    _build(tmp_path)
    auth = authorize_stage_execution(prepare_stage_authorization(tmp_path), owner_approved=True, owner_secret=OWNER_SECRET)
    (tmp_path / "campaign_journal.jsonl").write_text('{"event":"started"}\n')
    assert validate_stage_authorization(tmp_path, auth, owner_secret=OWNER_SECRET)["owner_approved"] is True



def test_authorization_rejects_rechecksummed_noncanonical_replacement(tmp_path):
    from inverted.harvest_d.hd_next2.authorization import prepare_stage_authorization
    _build(tmp_path)
    runtime = json.loads((tmp_path / "runtime_plan.json").read_text(encoding="utf-8"))
    runtime["physical_execution"] = True
    (tmp_path / "runtime_plan.json").write_text(
        json.dumps(runtime, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    _rewrite_checksums(tmp_path)
    with pytest.raises(ValueError, match="integrity"):
        prepare_stage_authorization(tmp_path)


@pytest.mark.parametrize(
    "payload",
    [
        '{"stage_id":"WRONG","stage_id":"2A-0","cases":[]}\n',
        '{"stage_id":"2A-0","cases":[],"invalid":NaN}\n',
    ],
)
def test_authorization_rejects_noncanonical_json_constants_and_duplicate_keys(tmp_path, payload):
    from inverted.harvest_d.hd_next2.authorization import prepare_stage_authorization
    _build(tmp_path)
    (tmp_path / "frozen_case_manifest.json").write_text(payload, encoding="utf-8")
    _rewrite_checksums(tmp_path)
    with pytest.raises(ValueError, match="integrity"):
        prepare_stage_authorization(tmp_path)



def test_authorization_rejects_package_labeled_with_different_or_nonexistent_commit(tmp_path):
    from inverted.harvest_d.hd_next2.authorization import prepare_stage_authorization
    parent = subprocess.run(
        ["git", "rev-parse", "HEAD^"], cwd=Path.cwd(), check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    for index, commit in enumerate((parent, "0" * 40)):
        package = tmp_path / f"package-{index}"
        _build(package)
        config = json.loads((package / "config.json").read_text(encoding="utf-8"))
        config["repo_commit"] = commit
        (package / "config.json").write_text(
            json.dumps(config, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        _rewrite_checksums(package)
        with pytest.raises(ValueError, match="integrity|source|commit"):
            prepare_stage_authorization(package)



def test_authorization_rejects_dirty_bound_source_against_recorded_commit(tmp_path, monkeypatch):
    from inverted.harvest_d.hd_next2.authorization import prepare_stage_authorization
    _build(tmp_path)
    original = Path.read_bytes

    def dirty_read(path):
        data = original(path)
        if path.name == "stages.py" and "hd_next2" in path.parts:
            return data + b"\n# simulated dirty source\n"
        return data

    monkeypatch.setattr(Path, "read_bytes", dirty_read)
    with pytest.raises(ValueError, match="integrity|source|commit"):
        prepare_stage_authorization(tmp_path)



def test_canonical_payload_reconstruction_rejects_unbound_or_nonexistent_commit():
    parent = subprocess.run(
        ["git", "rev-parse", "HEAD^"], cwd=Path.cwd(), check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    for commit in (parent, "0" * 40):
        with pytest.raises(ValueError, match="source|commit|current"):
            canonical_a0_payloads_for_commit(commit)
