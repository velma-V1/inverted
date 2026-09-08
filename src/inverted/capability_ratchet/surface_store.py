"""Append-only, integrity-gated metadata store for V3 Stage-5 surface research."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, TypeVar

from .causal_store import CausalEvidenceStore
from .core import MechanismLabel, PromotionEvent, PromotionState, ReplayResult
from .replay_store import ReplayStore
from .surface_core import (
    OperatingSurfaceProfile,
    SurfaceAxis,
    SurfaceBand,
    SurfaceCallGeometry,
    SurfaceDisposition,
    SurfaceEvidenceKind,
    SurfaceObservation,
    SurfacePoint,
    SurfaceStudy,
)


T = TypeVar("T")


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if hasattr(value, "value") and isinstance(getattr(value, "value"), str):
        return value.value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported surface JSON value: {type(value).__name__}")


def _canonical(payload: Any) -> bytes:
    return json.dumps(
        _json_value(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _study_payload(value: SurfaceStudy) -> dict[str, Any]:
    return {
        "study_id": value.study_id,
        "failure_snapshot_id": value.failure_snapshot_id,
        "mechanism_id": value.mechanism_id,
        "parent_state_hash": value.parent_state_hash,
        "partition": value.partition.value,
        "promotion_state": value.promotion_state.value,
        "decision_id": value.decision_id,
        "axes": [item.value for item in value.axes],
        "axis_values": value.axis_values,
        "decision_critical_reason": value.decision_critical_reason,
    }


def _study_from_payload(payload: Mapping[str, Any]) -> SurfaceStudy:
    raw = dict(payload)
    return SurfaceStudy(
        study_id=raw["study_id"],
        failure_snapshot_id=raw["failure_snapshot_id"],
        mechanism_id=raw["mechanism_id"],
        parent_state_hash=raw["parent_state_hash"],
        partition=raw["partition"],
        promotion_state=raw["promotion_state"],
        decision_id=raw["decision_id"],
        axes=tuple(SurfaceAxis(item) for item in raw["axes"]),
        axis_values={key: tuple(values) for key, values in raw["axis_values"].items()},
        decision_critical_reason=raw.get("decision_critical_reason"),
    )


def _observation_payload(value: SurfaceObservation) -> dict[str, Any]:
    return {
        "observation_id": value.observation_id,
        "surface_point_id": value.surface_point_id,
        "study_id": value.study_id,
        "failure_snapshot_id": value.failure_snapshot_id,
        "mechanism_id": value.mechanism_id,
        "parent_state_hash": value.parent_state_hash,
        "axis": value.axis.value,
        "value": value.value,
        "decision_id": value.decision_id,
        "protected_exploration": value.protected_exploration,
        "evidence_kind": value.evidence_kind.value,
        "replay_result_ids": value.replay_result_ids,
        "source_evidence_refs": value.source_evidence_refs,
        "metrics": value.metrics,
    }


def _observation_from_payload(payload: Mapping[str, Any]) -> SurfaceObservation:
    raw = dict(payload)
    return SurfaceObservation(
        observation_id=raw["observation_id"],
        surface_point_id=raw["surface_point_id"],
        study_id=raw["study_id"],
        failure_snapshot_id=raw["failure_snapshot_id"],
        mechanism_id=raw["mechanism_id"],
        parent_state_hash=raw["parent_state_hash"],
        axis=SurfaceAxis(raw["axis"]),
        value=raw["value"],
        decision_id=raw["decision_id"],
        protected_exploration=bool(raw.get("protected_exploration", False)),
        evidence_kind=SurfaceEvidenceKind(raw["evidence_kind"]),
        replay_result_ids=tuple(raw.get("replay_result_ids", ())),
        source_evidence_refs=tuple(raw.get("source_evidence_refs", ())),
        metrics=dict(raw.get("metrics", {})),
    )


def _profile_payload(value: OperatingSurfaceProfile) -> dict[str, Any]:
    return {
        "profile_id": value.profile_id,
        "study_id": value.study_id,
        "failure_snapshot_id": value.failure_snapshot_id,
        "mechanism_id": value.mechanism_id,
        "parent_state_hash": value.parent_state_hash,
        "partition": value.partition.value,
        "axis": value.axis.value,
        "disposition": value.disposition.value,
        "lower_useful": value.lower_useful,
        "upper_useful": value.upper_useful,
        "recommended_region": value.recommended_region,
        "harm_onset": value.harm_onset,
        "evidence_refs": value.evidence_refs,
        "unresolved_edges": value.unresolved_edges,
        "call_geometry": {
            "minimum_physical_calls": value.call_geometry.minimum_physical_calls,
            "expected_physical_calls": value.call_geometry.expected_physical_calls,
            "worst_case_physical_calls": value.call_geometry.worst_case_physical_calls,
            "protected_exploration_calls": value.call_geometry.protected_exploration_calls,
        },
        "promotion_ceiling": value.promotion_ceiling.value,
    }


def _profile_from_payload(payload: Mapping[str, Any]) -> OperatingSurfaceProfile:
    raw = dict(payload)
    geometry = dict(raw["call_geometry"])
    return OperatingSurfaceProfile(
        profile_id=raw["profile_id"],
        study_id=raw["study_id"],
        failure_snapshot_id=raw["failure_snapshot_id"],
        mechanism_id=raw["mechanism_id"],
        parent_state_hash=raw["parent_state_hash"],
        partition=raw["partition"],
        axis=SurfaceAxis(raw["axis"]),
        disposition=SurfaceDisposition(raw["disposition"]),
        lower_useful=raw.get("lower_useful"),
        upper_useful=raw.get("upper_useful"),
        recommended_region=tuple(raw.get("recommended_region", ())),
        harm_onset=raw.get("harm_onset"),
        evidence_refs=tuple(raw["evidence_refs"]),
        unresolved_edges=tuple(raw.get("unresolved_edges", ())),
        call_geometry=SurfaceCallGeometry(**geometry),
        promotion_ceiling=PromotionState(raw["promotion_ceiling"]),
    )


_LOCKS_GUARD = threading.Lock()
_PROCESS_LOCKS: dict[str, threading.RLock] = {}


@dataclass(frozen=True)
class SurfaceStoreValidation:
    ok: bool
    study_count: int
    observation_count: int
    profile_count: int
    hash_mismatches: tuple[str, ...]
    broken_lineage: tuple[str, ...]
    duplicate_ids: tuple[str, ...]


class SurfaceEvidenceStore:
    """Store Stage-5 scientific metadata while replay outcomes stay canonical elsewhere."""

    def __init__(
        self,
        root: Path,
        *,
        replay_store: ReplayStore,
        causal_store: CausalEvidenceStore,
    ) -> None:
        if not isinstance(replay_store, ReplayStore):
            raise TypeError("replay_store must be ReplayStore")
        if not isinstance(causal_store, CausalEvidenceStore):
            raise TypeError("causal_store must be CausalEvidenceStore")
        self.root = Path(root)
        self.replay_store = replay_store
        self.causal_store = causal_store
        self.study_path = self.root / "surface-studies.jsonl"
        self.study_manifest_path = self.root / "surface-studies.sha256"
        self.observation_path = self.root / "surface-observations.jsonl"
        self.observation_manifest_path = self.root / "surface-observations.sha256"
        self.profile_path = self.root / "operating-surface-profiles.jsonl"
        self.profile_manifest_path = self.root / "operating-surface-profiles.sha256"
        self.lock_path = self.root / ".surface-evidence.lock"
        with _LOCKS_GUARD:
            self._lock = _PROCESS_LOCKS.setdefault(str(self.root.resolve()), threading.RLock())

    @contextmanager
    def _transaction_lock(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self.lock_path.open("a+b") as handle:
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    handle.seek(0)
                    if os.name == "nt":
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        if os.name == "nt":
            return
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _write_atomic(self, path: Path, encoded: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        with temporary.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        self._fsync_directory(path.parent)

    def _write_manifest(self, source: Path, manifest: Path) -> None:
        encoded = source.read_bytes() if source.exists() else b""
        self._write_atomic(manifest, hashlib.sha256(encoded).hexdigest().encode("ascii") + b"\n")

    @staticmethod
    def _rows(path: Path, decoder: Callable[[Mapping[str, Any]], T]) -> list[tuple[str, bytes, T]]:
        if not path.exists():
            return []
        encoded = path.read_bytes()
        if encoded and not encoded.endswith(b"\n"):
            raise ValueError(f"{path.name} must end with a newline")
        rows: list[tuple[str, bytes, T]] = []
        for number, line in enumerate(encoded.splitlines(), 1):
            if not line:
                raise ValueError(f"{path.name}:{number} is blank")
            payload = json.loads(line)
            if line != _canonical(payload):
                raise ValueError(f"{path.name}:{number} is not canonical JSON")
            value = decoder(payload)
            logical_id = getattr(value, "study_id", None) if isinstance(value, SurfaceStudy) else (
                getattr(value, "observation_id", None) if isinstance(value, SurfaceObservation)
                else getattr(value, "profile_id")
            )
            rows.append((logical_id, line, value))
        return rows

    def _append(
        self,
        *,
        path: Path,
        manifest: Path,
        logical_id: str,
        payload: Mapping[str, Any],
        decoder: Callable[[Mapping[str, Any]], T],
    ) -> str:
        line = _canonical(payload)
        with self._transaction_lock():
            rows = self._rows(path, decoder)
            matches = [existing for row_id, existing, _ in rows if row_id == logical_id]
            if matches:
                if any(existing != line for existing in matches):
                    raise ValueError("existing logical ID has different canonical content")
                expected = hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii") + b"\n"
                if not manifest.exists() or manifest.read_bytes() != expected:
                    self._write_atomic(manifest, expected)
                return logical_id
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("ab") as handle:
                handle.write(line + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._write_manifest(path, manifest)
        return logical_id

    def _require_study_lineage(self, study: SurfaceStudy) -> None:
        try:
            fixture = self.replay_store.get_failure(study.failure_snapshot_id)
        except KeyError as exc:
            raise ValueError("surface study references an unknown replay failure") from exc
        if fixture.state_hash != study.parent_state_hash or fixture.partition != study.partition:
            raise ValueError("surface study failure state/partition does not match replay lineage")
        labels = [
            record for record in self.replay_store.records()
            if isinstance(record, MechanismLabel)
            and record.failure_snapshot_id == study.failure_snapshot_id
            and record.mechanism_id == study.mechanism_id
            and record.parent_state_hash == study.parent_state_hash
        ]
        if not labels:
            raise ValueError("surface study mechanism is not registered in canonical replay evidence")
        hypothesis_ids = {item.hypothesis_id for item in self.causal_store.hypotheses(study.failure_snapshot_id)}
        if not any(label.hypothesis_id in hypothesis_ids for label in labels):
            raise ValueError("surface study mechanism has no matching causal hypothesis")
        if study.promotion_state is PromotionState.MOVEMENT:
            movements = [
                record for record in self.replay_store.records()
                if isinstance(record, PromotionEvent)
                and record.failure_snapshot_id == study.failure_snapshot_id
                and record.mechanism_id == study.mechanism_id
                and record.to_state is PromotionState.MOVEMENT
            ]
            if not movements:
                raise ValueError("surface study MOVEMENT is not backed by a canonical promotion event")

    def append_study(self, study: SurfaceStudy) -> str:
        if not isinstance(study, SurfaceStudy):
            raise TypeError("study must be SurfaceStudy")
        self._require_study_lineage(study)
        return self._append(
            path=self.study_path,
            manifest=self.study_manifest_path,
            logical_id=study.study_id,
            payload=_study_payload(study),
            decoder=_study_from_payload,
        )

    def studies(self, mechanism_id: str | None = None) -> tuple[SurfaceStudy, ...]:
        with self._transaction_lock():
            values = tuple(row[2] for row in self._rows(self.study_path, _study_from_payload))
        if mechanism_id is None:
            return values
        return tuple(item for item in values if item.mechanism_id == mechanism_id)

    def _require_observation_lineage(self, observation: SurfaceObservation) -> None:
        studies = {item.study_id: item for item in self.studies()}
        study = studies.get(observation.study_id)
        if study is None:
            raise ValueError("surface observation references an unknown study")
        if (
            observation.failure_snapshot_id != study.failure_snapshot_id
            or observation.mechanism_id != study.mechanism_id
            or observation.parent_state_hash != study.parent_state_hash
        ):
            raise ValueError("surface observation lineage differs from its study")
        expected_point = SurfacePoint.create(
            study=study,
            axis=observation.axis,
            value=observation.value,
            decision_id=observation.decision_id,
            protected_exploration=observation.protected_exploration,
        )
        if expected_point.surface_point_id != observation.surface_point_id:
            raise ValueError("surface observation point identity mismatch")
        if observation.evidence_kind is SurfaceEvidenceKind.SAME_STATE_CAUSAL:
            results = {
                record.replay_result_id: record
                for record in self.replay_store.records()
                if isinstance(record, ReplayResult)
            }
            for result_id in observation.replay_result_ids:
                result = results.get(result_id)
                if result is None:
                    raise ValueError(f"surface observation references missing replay result {result_id}")
                if (
                    result.failure_snapshot_id != study.failure_snapshot_id
                    or result.parent_failure_snapshot_id != study.failure_snapshot_id
                    or result.parent_state_hash != study.parent_state_hash
                    or result.partition != study.partition
                ):
                    raise ValueError("surface observation replay result is not same-state causal evidence")

    def append_observation(self, observation: SurfaceObservation) -> str:
        if not isinstance(observation, SurfaceObservation):
            raise TypeError("observation must be SurfaceObservation")
        self._require_observation_lineage(observation)
        return self._append(
            path=self.observation_path,
            manifest=self.observation_manifest_path,
            logical_id=observation.observation_id,
            payload=_observation_payload(observation),
            decoder=_observation_from_payload,
        )

    def observations(self, study_id: str | None = None) -> tuple[SurfaceObservation, ...]:
        with self._transaction_lock():
            values = tuple(row[2] for row in self._rows(self.observation_path, _observation_from_payload))
        if study_id is None:
            return values
        return tuple(item for item in values if item.study_id == study_id)

    def _require_profile_lineage(self, profile: OperatingSurfaceProfile) -> None:
        studies = {item.study_id: item for item in self.studies()}
        study = studies.get(profile.study_id)
        if study is None:
            raise ValueError("surface profile references an unknown study")
        if (
            profile.failure_snapshot_id != study.failure_snapshot_id
            or profile.mechanism_id != study.mechanism_id
            or profile.parent_state_hash != study.parent_state_hash
            or profile.partition != study.partition
        ):
            raise ValueError("surface profile lineage differs from its study")
        observations = {item.observation_id: item for item in self.observations(profile.study_id)}
        for ref in profile.evidence_refs:
            if ref not in observations:
                raise ValueError(f"surface profile references missing observation {ref}")

    def append_profile(self, profile: OperatingSurfaceProfile) -> str:
        if not isinstance(profile, OperatingSurfaceProfile):
            raise TypeError("profile must be OperatingSurfaceProfile")
        self._require_profile_lineage(profile)
        return self._append(
            path=self.profile_path,
            manifest=self.profile_manifest_path,
            logical_id=profile.profile_id,
            payload=_profile_payload(profile),
            decoder=_profile_from_payload,
        )

    def profiles(self, mechanism_id: str | None = None) -> tuple[OperatingSurfaceProfile, ...]:
        with self._transaction_lock():
            values = tuple(row[2] for row in self._rows(self.profile_path, _profile_from_payload))
        if mechanism_id is None:
            return values
        return tuple(item for item in values if item.mechanism_id == mechanism_id)

    @staticmethod
    def _manifest_mismatch(source: Path, manifest: Path) -> bool:
        if not source.exists():
            return manifest.exists()
        expected = hashlib.sha256(source.read_bytes()).hexdigest().encode("ascii") + b"\n"
        try:
            return manifest.read_bytes() != expected
        except OSError:
            return True

    def validate(self) -> SurfaceStoreValidation:
        mismatches: set[str] = set()
        broken: list[str] = []
        duplicates: set[str] = set()
        studies: tuple[SurfaceStudy, ...] = ()
        observations: tuple[SurfaceObservation, ...] = ()
        profiles: tuple[OperatingSurfaceProfile, ...] = ()

        specs = (
            (self.study_path, self.study_manifest_path, _study_from_payload, "study_id"),
            (self.observation_path, self.observation_manifest_path, _observation_from_payload, "observation_id"),
            (self.profile_path, self.profile_manifest_path, _profile_from_payload, "profile_id"),
        )
        decoded: list[tuple[Any, ...]] = []
        with self._transaction_lock():
            for path, manifest, decoder, identity_name in specs:
                if self._manifest_mismatch(path, manifest):
                    mismatches.add(manifest.name)
                try:
                    rows = self._rows(path, decoder)
                except Exception as exc:
                    mismatches.add(path.name)
                    broken.append(f"{path.name}: {type(exc).__name__}")
                    decoded.append(())
                    continue
                seen: set[str] = set()
                values: list[Any] = []
                for logical_id, _, value in rows:
                    if logical_id in seen:
                        duplicates.add(f"{identity_name}:{logical_id}")
                    seen.add(logical_id)
                    values.append(value)
                decoded.append(tuple(values))
        studies, observations, profiles = decoded  # type: ignore[assignment]

        replay_ok = self.replay_store.validate().ok
        causal_ok = self.causal_store.validate().ok
        if not replay_ok:
            broken.append("canonical replay store failed integrity validation")
        if not causal_ok:
            broken.append("causal evidence store failed integrity validation")

        for study in studies:
            try:
                self._require_study_lineage(study)
            except Exception as exc:
                broken.append(f"study {study.study_id}: {exc}")
        for observation in observations:
            try:
                self._require_observation_lineage(observation)
            except Exception as exc:
                broken.append(f"observation {observation.observation_id}: {exc}")
        for profile in profiles:
            try:
                self._require_profile_lineage(profile)
            except Exception as exc:
                broken.append(f"profile {profile.profile_id}: {exc}")

        return SurfaceStoreValidation(
            ok=not mismatches and not broken and not duplicates,
            study_count=len(studies),
            observation_count=len(observations),
            profile_count=len(profiles),
            hash_mismatches=tuple(sorted(mismatches)),
            broken_lineage=tuple(broken),
            duplicate_ids=tuple(sorted(duplicates)),
        )
