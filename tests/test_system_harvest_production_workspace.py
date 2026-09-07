from pathlib import Path

import pytest

from inverted.system_harvest.environment import EnvironmentPolicy
from inverted.system_harvest.workspace import WorkspaceLeaseError, WorkspaceLeaseManager, tree_hash


def _fixture(tmp_path):
    root = tmp_path / "fixture"
    root.mkdir()
    (root / "a.txt").write_text("alpha\n", encoding="utf-8")
    (root / "sub").mkdir()
    (root / "sub" / "b.txt").write_text("beta\n", encoding="utf-8")
    return root


def test_workspace_is_copied_and_fixture_is_never_mutated(tmp_path):
    fixture = _fixture(tmp_path)
    digest = tree_hash(fixture)
    manager = WorkspaceLeaseManager(tmp_path / "leases")
    lease = manager.acquire("cell-1", "exec-1", fixture, digest)
    assert Path(lease.workspace_path) != fixture
    (Path(lease.workspace_path) / "a.txt").write_text("changed\n", encoding="utf-8")
    assert (fixture / "a.txt").read_text(encoding="utf-8") == "alpha\n"
    final = manager.finalize(lease.lease_id)
    assert final.final_tree_sha256 != final.baseline_tree_sha256
    assert "a.txt" in final.changed_paths


def test_workspace_lease_cannot_be_shared_or_released_while_uncertain(tmp_path):
    fixture = _fixture(tmp_path)
    manager = WorkspaceLeaseManager(tmp_path / "leases")
    lease = manager.acquire("cell-1", "exec-1", fixture, tree_hash(fixture))
    with pytest.raises(WorkspaceLeaseError, match="already leased"):
        manager.acquire("cell-2", "exec-2", fixture, tree_hash(fixture), lease_id=lease.lease_id)
    uncertain = manager.mark_recovery_uncertain(lease.lease_id)
    assert uncertain.recovery_uncertain
    with pytest.raises(WorkspaceLeaseError, match="recovery"):
        manager.release(lease.lease_id)


def test_environment_snapshot_never_persists_declared_secret(tmp_path):
    policy = EnvironmentPolicy(secret_names=("API_KEY",), salt="campaign-salt")
    env = {"API_KEY": "super-secret-value", "PATH": "C:/tools"}
    snapshot = policy.snapshot(env)
    assert "super-secret-value" not in snapshot.persistent_json
    assert "API_KEY" in snapshot.persistent_json
    assert snapshot.fingerprints["API_KEY"]
    assert snapshot.redaction_tokens["API_KEY"].startswith("<REDACTED:API_KEY:")


def test_echoed_secret_is_redacted_deterministically_with_lineage():
    policy = EnvironmentPolicy(secret_names=("API_KEY",), salt="campaign-salt")
    env = {"API_KEY": "super-secret-value"}
    snapshot = policy.snapshot(env)
    first = policy.redact_bytes(b"before super-secret-value after", env, source="stdout")
    second = policy.redact_bytes(b"before super-secret-value after", env, source="stdout")
    assert b"super-secret-value" not in first.persisted_bytes
    assert first.persisted_bytes == second.persisted_bytes
    assert first.redactions == second.redactions
    assert first.redactions[0].variable_name == "API_KEY"
    assert first.redactions[0].token == snapshot.redaction_tokens["API_KEY"]
