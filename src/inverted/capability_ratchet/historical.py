"""Zero-inference import of preserved V2 evidence into TEST_REPLAY."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from inverted.universal_tuning.core import AtomicTask, FailureClass, Observation, Profile

from .core import FailureFixture, Partition
from .replay_store import ReplayStore
from .snapshot import build_failure_fixture

_REQUIRED_FILES = (
    "protocol-v2-manifest.json",
    "task-pool-v2.json",
    "atomic_observations.jsonl",
    "raw_calls.jsonl",
)


@dataclass(frozen=True)
class HistoricalSeedResult:
    total_observations: int
    material_failures: int
    fixtures_added: int
    duplicate_fixtures: int
    skipped_nonfailures: int
    invalid_rows: int


@dataclass(frozen=True)
class _LoadedV2:
    manifest: dict[str, Any]
    tasks: dict[str, AtomicTask]
    observations: tuple[Observation, ...]
    observation_rows: tuple[dict[str, Any], ...]
    raw_trials: dict[str, dict[str, Any]]
    campaign_id: str


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON source file: {path.name}") from exc


def _unwrap_manifest(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("V2 manifest must be a JSON object")
    if "manifest" not in value:
        return value
    inner = value.get("manifest")
    declared = value.get("manifest_sha256")
    if not isinstance(inner, dict) or not isinstance(declared, str):
        raise ValueError("V2 wrapped manifest is malformed")
    encoded = json.dumps(
        inner, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    actual = hashlib.sha256(encoded).hexdigest()
    if declared != actual:
        raise ValueError("V2 wrapped manifest hash mismatch")
    return inner


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid JSONL source file: {path.name}") from exc
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name} row {number} is invalid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path.name} row {number} must be an object")
        rows.append(value)
    return rows


def _task_from_row(row: dict[str, Any]) -> AtomicTask:
    metadata = tuple(tuple(item) for item in row.get("metadata", ()))
    return AtomicTask(
        task_id=str(row["task_id"]), family=str(row["family"]),
        difficulty=int(row["difficulty"]), prompt=str(row["prompt"]),
        expected=row.get("expected"), scorer=str(row["scorer"]),
        contract=str(row.get("contract", "answer_object")), metadata=metadata,
    )


def _profile_from_row(row: dict[str, Any]) -> Profile:
    return Profile(
        thinking_budget=int(row.get("thinking_budget", 0)),
        temperature=float(row.get("temperature", 0.7)),
        top_p=row.get("top_p"), top_k=row.get("top_k"), min_p=row.get("min_p"),
        presence_penalty=row.get("presence_penalty"), repeat_penalty=row.get("repeat_penalty"),
    )


def _failure_class(value: Any) -> Any:
    try:
        return FailureClass(str(value))
    except ValueError:
        return str(value)


def _observation_from_row(row: dict[str, Any]) -> Observation:
    return Observation(
        observation_id=str(row["observation_id"]), batch_id=str(row["batch_id"]),
        task_id=str(row["task_id"]), family=str(row["family"]), stage=str(row["stage"]),
        profile=_profile_from_row(dict(row["profile"])), inference_seed=int(row["inference_seed"]),
        decision_reason=str(row["decision_reason"]), semantic_pass=bool(row["semantic_pass"]),
        contract_pass=bool(row["contract_pass"]), completed=bool(row["completed"]),
        semantic_quality=float(row["semantic_quality"]), contract_quality=float(row["contract_quality"]),
        latency_s=float(row["latency_s"]), output_tokens=int(row["output_tokens"]),
        thinking_tokens=int(row["thinking_tokens"]), physical_calls=int(row["physical_calls"]),
        response_text=str(row.get("response_text", "")),
        failure_classes=tuple(_failure_class(value) for value in row.get("failure_classes", ())),
        raw_call_refs=tuple(str(value) for value in row.get("raw_call_refs", ())),
        metadata=tuple(tuple(item) for item in row.get("metadata", ())),
    )


def _trial_id(observation: Observation, row: dict[str, Any]) -> str:
    top = row.get("trial_id")
    metadata = dict(observation.metadata).get("trial_id")
    if top is not None and metadata is not None and top != metadata:
        raise ValueError("observation trial_id disagrees with metadata")
    trial = top if top is not None else metadata
    if not isinstance(trial, str) or not trial:
        raise ValueError("observation is missing trial_id")
    return trial


def _campaign_id(root: Path) -> str:
    digest = hashlib.sha256()
    for name in _REQUIRED_FILES:
        data = (root / name).read_bytes()
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(data).digest())
    return f"v2-evidence-{digest.hexdigest()[:24]}"


class V2EvidenceSource:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def load(self) -> _LoadedV2:
        missing = [name for name in _REQUIRED_FILES if not (self.root / name).is_file()]
        if missing:
            raise ValueError(f"V2 evidence source is missing required files: {missing}")
        manifest = _unwrap_manifest(_read_json(self.root / "protocol-v2-manifest.json"))
        pool = _read_json(self.root / "task-pool-v2.json")
        if not isinstance(manifest, dict) or manifest.get("protocol_version") != 2:
            raise ValueError("V2 manifest protocol_version must be 2")
        if not isinstance(pool, dict) or pool.get("protocol_version") != 2:
            raise ValueError("V2 task pool protocol_version must be 2")

        canonical_pool = json.dumps(
            pool, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
        actual_pool_hash = hashlib.sha256(canonical_pool).hexdigest()
        if manifest.get("task_pool_sha256") != actual_pool_hash:
            raise ValueError("V2 manifest task-pool hash mismatch")
        rows = pool.get("tasks")
        if not isinstance(rows, list) or not rows:
            raise ValueError("V2 task pool must contain tasks")
        tasks: dict[str, AtomicTask] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("V2 task pool rows must be objects")
            task = _task_from_row(row)
            if task.task_id in tasks:
                raise ValueError(f"duplicate V2 task_id: {task.task_id}")
            tasks[task.task_id] = task

        observation_rows = _read_jsonl(self.root / "atomic_observations.jsonl")
        observations: list[Observation] = []
        seen_observation_ids: set[str] = set()
        for row in observation_rows:
            observation = _observation_from_row(row)
            if observation.observation_id in seen_observation_ids:
                raise ValueError(f"duplicate V2 observation_id: {observation.observation_id}")
            if observation.task_id not in tasks:
                raise ValueError(f"V2 observation references unknown task_id: {observation.task_id}")
            seen_observation_ids.add(observation.observation_id)
            observations.append(observation)

        raw_rows = _read_jsonl(self.root / "raw_calls.jsonl")
        raw_trials: dict[str, dict[str, Any]] = {}
        for row in raw_rows:
            trial_id = row.get("trial_id")
            if not isinstance(trial_id, str) or not trial_id:
                raise ValueError("V2 raw trial is missing trial_id")
            if trial_id in raw_trials:
                raise ValueError(f"duplicate V2 raw trial identity: {trial_id}")
            raw_trials[trial_id] = row
        return _LoadedV2(
            manifest=manifest, tasks=tasks, observations=tuple(observations),
            observation_rows=tuple(observation_rows), raw_trials=raw_trials,
            campaign_id=_campaign_id(self.root),
        )


def _reasoning_cap_exhausted(raw_trial: dict[str, Any]) -> bool:
    raw_calls = raw_trial.get("raw_calls")
    if not isinstance(raw_calls, list) or not raw_calls:
        return False
    first = raw_calls[0]
    if not isinstance(first, dict):
        return False
    request = first.get("request")
    response = first.get("response")
    return (
        isinstance(request, dict)
        and request.get("think") is True
        and isinstance(response, dict)
        and response.get("done_reason") == "length"
    )


def _is_material(observation: Observation, *, cap_exhausted: bool) -> bool:
    return (
        cap_exhausted
        or not observation.completed
        or not observation.semantic_pass
        or not observation.contract_pass
        or bool(observation.failure_classes)
    )


def _with_cap_failure(observation: Observation) -> Observation:
    classes = tuple(observation.failure_classes)
    if "REASONING_CAP_EXHAUSTION" in {str(value) for value in classes}:
        return observation
    return replace(observation, failure_classes=classes + ("REASONING_CAP_EXHAUSTION",))


def seed_v2_failures(source: V2EvidenceSource, replay_store: ReplayStore) -> HistoricalSeedResult:
    """Import material V2 failures without executing a model or network call."""
    if not isinstance(source, V2EvidenceSource):
        raise TypeError("source must be V2EvidenceSource")
    if not isinstance(replay_store, ReplayStore):
        raise TypeError("replay_store must be ReplayStore")
    loaded = source.load()
    existing_by_snapshot = {
        record.failure_snapshot_id: record
        for record in replay_store.records()
        if isinstance(record, FailureFixture)
    }
    runtime = loaded.manifest.get("runtime_provenance")
    if not isinstance(runtime, dict):
        raise ValueError("V2 manifest is missing runtime provenance")

    grouped: dict[str, list[tuple[Observation, dict[str, Any]]]] = defaultdict(list)
    for observation, row in zip(loaded.observations, loaded.observation_rows, strict=True):
        grouped[_trial_id(observation, row)].append((observation, row))

    total = len(loaded.observations)
    material = added = duplicates = skipped = invalid = 0
    for trial_id, members in grouped.items():
        raw_trial = loaded.raw_trials.get(trial_id)
        if raw_trial is None or len(members) != 5:
            invalid += len(members)
            continue
        task_ids = [observation.task_id for observation, _ in members]
        if len(set(task_ids)) != 5:
            invalid += len(members)
            continue
        try:
            batch = tuple(loaded.tasks[task_id] for task_id in task_ids)
        except KeyError:
            invalid += len(members)
            continue
        cap_exhausted = _reasoning_cap_exhausted(raw_trial)
        candidates: list[tuple[Observation, dict[str, Any]]] = []
        for observation, row in members:
            if _is_material(observation, cap_exhausted=cap_exhausted):
                candidate = _with_cap_failure(observation) if cap_exhausted else observation
                candidates.append((candidate, row))
            else:
                skipped += 1

        if not candidates:
            continue
        material += len(candidates)
        fixtures: list[FailureFixture] = []
        try:
            for observation, _ in candidates:
                fixture = build_failure_fixture(
                    failed_observation=observation,
                    atomic_tasks=batch,
                    raw_trial=raw_trial,
                    store=replay_store,
                    source_campaign_id=loaded.campaign_id,
                    runtime_provenance=runtime,
                    partition=Partition.HISTORICAL,
                    source_evidence_refs=(
                        f"raw_calls.jsonl:{trial_id}",
                        f"atomic_observations.jsonl:{observation.observation_id}",
                    ),
                )
                fixtures.append(fixture)
        except (TypeError, ValueError, KeyError):
            invalid += len(members)
            material -= len(candidates)
            skipped -= sum(1 for observation, _ in members if not _is_material(observation, cap_exhausted=cap_exhausted))
            continue
        for fixture in fixtures:
            existing = existing_by_snapshot.get(fixture.failure_snapshot_id)
            if existing is not None:
                if replace(existing, record_id=None) != fixture:
                    raise ValueError(
                        f"existing replay fixture conflicts with historical source: {fixture.failure_snapshot_id}"
                    )
                duplicates += 1
                continue
            record_id = replay_store.append(fixture)
            existing_by_snapshot[fixture.failure_snapshot_id] = replace(fixture, record_id=record_id)
            added += 1

    return HistoricalSeedResult(
        total_observations=total,
        material_failures=material,
        fixtures_added=added,
        duplicate_fixtures=duplicates,
        skipped_nonfailures=skipped,
        invalid_rows=invalid,
    )
