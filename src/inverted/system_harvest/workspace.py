from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, replace
from pathlib import Path


class WorkspaceLeaseError(RuntimeError):
    pass


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_inventory(root: str | Path) -> dict[str, str]:
    base = Path(root)
    if not base.is_dir():
        raise WorkspaceLeaseError(f"workspace fixture is not a directory: {base}")
    return {
        path.relative_to(base).as_posix(): _file_hash(path)
        for path in sorted(base.rglob("*")) if path.is_file()
    }


def tree_hash(root: str | Path) -> str:
    raw = json.dumps(tree_inventory(root), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

@dataclass(frozen=True)
class WorkspaceLease:
    lease_id: str
    cell_id: str
    execution_id: str
    fixture_path: str
    fixture_sha256: str
    workspace_path: str
    baseline_tree_sha256: str
    baseline_inventory: tuple[tuple[str, str], ...]
    final_tree_sha256: str | None = None
    changed_paths: tuple[str, ...] = ()
    recovery_uncertain: bool = False
    released: bool = False


class WorkspaceLeaseManager:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._leases: dict[str, WorkspaceLease] = {}

    def _default_id(self, cell_id: str, execution_id: str, fixture_sha256: str) -> str:
        raw = f"{cell_id}\0{execution_id}\0{fixture_sha256}".encode("utf-8")
        return "LEASE-" + hashlib.sha256(raw).hexdigest()[:24]
    def acquire(self, cell_id: str, execution_id: str, fixture: str | Path,
                expected_sha256: str, *, lease_id: str | None = None) -> WorkspaceLease:
        fixture_path = Path(fixture).resolve()
        actual = tree_hash(fixture_path)
        if actual != expected_sha256:
            raise WorkspaceLeaseError("fixture hash mismatch")
        lease_id = lease_id or self._default_id(cell_id, execution_id, expected_sha256)
        if lease_id in self._leases:
            raise WorkspaceLeaseError(f"workspace already leased: {lease_id}")
        destination = self.root / lease_id / "workspace"
        if destination.exists():
            raise WorkspaceLeaseError(f"workspace already leased on disk: {lease_id}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(fixture_path, destination)
        inventory = tree_inventory(destination)
        baseline_hash = tree_hash(destination)
        if baseline_hash != expected_sha256:
            raise WorkspaceLeaseError("materialized workspace hash mismatch")
        lease = WorkspaceLease(
            lease_id, cell_id, execution_id, str(fixture_path), expected_sha256,
            str(destination.resolve()), baseline_hash, tuple(sorted(inventory.items())),
        )
        self._leases[lease_id] = lease
        return lease

    def get(self, lease_id: str) -> WorkspaceLease:
        try:
            return self._leases[lease_id]
        except KeyError as exc:
            raise WorkspaceLeaseError(f"unknown workspace lease: {lease_id}") from exc
    def finalize(self, lease_id: str) -> WorkspaceLease:
        lease = self.get(lease_id)
        current_inventory = tree_inventory(lease.workspace_path)
        baseline = dict(lease.baseline_inventory)
        changed = sorted(
            path for path in set(baseline) | set(current_inventory)
            if baseline.get(path) != current_inventory.get(path)
        )
        updated = replace(
            lease,
            final_tree_sha256=tree_hash(lease.workspace_path),
            changed_paths=tuple(changed),
        )
        self._leases[lease_id] = updated
        return updated

    def mark_recovery_uncertain(self, lease_id: str) -> WorkspaceLease:
        lease = self.get(lease_id)
        updated = replace(lease, recovery_uncertain=True)
        self._leases[lease_id] = updated
        return updated

    def release(self, lease_id: str) -> WorkspaceLease:
        lease = self.get(lease_id)
        if lease.recovery_uncertain:
            raise WorkspaceLeaseError("recovery-uncertain workspace must be preserved")
        updated = replace(lease, released=True)
        self._leases[lease_id] = updated
        return updated
