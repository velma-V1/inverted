"""Deterministic V2 failure snapshots for exact replay."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from inverted.universal_tuning.core import AtomicTask, FailureClass, Observation

from .core import FailureFixture, Partition
from .replay_store import ReplayStore

_SENSITIVE_KEYS = frozenset({"authorization", "apikey", "token", "password", "secret"})
_PRIVATE_KEY_MARKERS = (
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN ENCRYPTED PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN EC PRIVATE KEY-----",
    "-----BEGIN DSA PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
)
_MAX_SCAN_DEPTH = 32
_MAX_SCAN_NODES = 20_000


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _json_copy(value: Any, *, name: str) -> Any:
    try:
        return json.loads(_canonical(value))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite JSON data") from exc


def _is_redacted(value: Any) -> bool:
    return isinstance(value, str) and value.strip().upper() == "<REDACTED>"


def _scan_secrets(value: Any, *, label: str) -> None:
    nodes = 0
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > _MAX_SCAN_NODES or depth > _MAX_SCAN_DEPTH:
            raise ValueError(f"{label} exceeds bounded secret scanner limits")
        if isinstance(current, str):
            upper = current.upper()
            if any(marker in upper for marker in _PRIVATE_KEY_MARKERS):
                raise ValueError(f"private key material is forbidden in {label}")
            continue
        if isinstance(current, Mapping):
            for key, item in current.items():
                normalized = "".join(character for character in str(key).strip().lower() if character.isalnum())
                if normalized in _SENSITIVE_KEYS and not _is_redacted(item):
                    raise ValueError(f"sensitive plaintext field {key!r} is forbidden in {label}")
                stack.append((item, depth + 1))
        elif isinstance(current, Sequence) and not isinstance(current, (str, bytes, bytearray)):
            for item in current:
                stack.append((item, depth + 1))


def _observation_trial_id(observation: Observation) -> str:
    metadata = dict(observation.metadata)
    declared = metadata.get("trial_id")
    ref_trials = {
        ref.rsplit(":call:", 1)[0]
        for ref in observation.raw_call_refs
        if isinstance(ref, str) and ":call:" in ref
    }
    if declared is not None:
        if not isinstance(declared, str) or not declared:
            raise ValueError("observation trial_id must be a non-empty string")
        if ref_trials and ref_trials != {declared}:
            raise ValueError("observation raw-call refs disagree with trial_id")
        return declared
    if len(ref_trials) == 1:
        return next(iter(ref_trials))
    raise ValueError("unable to resolve exact source trial from observation")


def _failure_classes(observation: Observation) -> tuple[str, ...]:
    if observation.failure_classes:
        return tuple(
            item.value if isinstance(item, FailureClass) else str(item)
            for item in observation.failure_classes
        )
    if not observation.completed:
        return (FailureClass.COMPLETION_FAIL.value,)
    if not observation.semantic_pass:
        return (FailureClass.SEMANTIC_FAIL.value,)
    if not observation.contract_pass:
        return (FailureClass.CONTRACT_FAIL.value,)
    raise ValueError("observation is not a failure")


def _profile_payload(observation: Observation) -> dict[str, Any]:
    profile = observation.profile
    return {
        "thinking_budget": profile.thinking_budget,
        "temperature": profile.temperature,
        "top_p": profile.top_p,
        "top_k": profile.top_k,
        "min_p": profile.min_p,
        "presence_penalty": profile.presence_penalty,
        "repeat_penalty": profile.repeat_penalty,
    }


def _validate_tasks(observation: Observation, atomic_tasks: tuple[AtomicTask, ...]) -> AtomicTask:
    if len(atomic_tasks) != 5:
        raise ValueError("exact V2 snapshot requires the complete five-task physical batch")
    task_ids = tuple(task.task_id for task in atomic_tasks)
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("batch task IDs must be unique")
    if observation.task_id not in task_ids:
        raise ValueError("focus task is not present in the supplied physical batch")
    families = {task.family for task in atomic_tasks}
    if families != {observation.family}:
        raise ValueError("all batch tasks must match the failed observation family")
    return atomic_tasks[task_ids.index(observation.task_id)]


def _request_envelopes(
    observation: Observation,
    raw_trial: Mapping[str, Any],
    runtime_provenance: Mapping[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    trial_id = _observation_trial_id(observation)
    if raw_trial.get("trial_id") != trial_id:
        raise ValueError("raw trial identity does not match failed observation trial")
    raw_calls = raw_trial.get("raw_calls")
    if not isinstance(raw_calls, list) or not raw_calls:
        raise ValueError("raw trial must contain physical raw_calls")
    physical_calls = raw_trial.get("physical_calls")
    if physical_calls != len(raw_calls) or observation.physical_calls != len(raw_calls):
        raise ValueError("physical call count does not match raw trial evidence")
    if len(observation.raw_call_refs) != len(raw_calls):
        raise ValueError("observation raw-call references do not cover every physical call")

    model = runtime_provenance.get("model")
    if not isinstance(model, str) or not model:
        raise ValueError("runtime provenance requires source model identity")
    envelopes: list[dict[str, Any]] = []
    for index, call in enumerate(raw_calls):
        if not isinstance(call, Mapping) or not isinstance(call.get("request"), Mapping):
            raise ValueError(f"raw call {index} is missing its request envelope")
        request = _json_copy(call["request"], name=f"raw call {index} request")
        if request.get("model") != model:
            raise ValueError("request envelope model does not match runtime provenance")
        expected_ref = f"{trial_id}:call:{index}"
        if observation.raw_call_refs[index] != expected_ref:
            raise ValueError("raw-call reference does not match physical request order")
        envelopes.append(request)
    return trial_id, envelopes


def _ensure_batch_visible(envelopes: list[dict[str, Any]], atomic_tasks: tuple[AtomicTask, ...]) -> None:
    messages = envelopes[0].get("messages")
    if not isinstance(messages, list):
        raise ValueError("first request envelope is missing model-visible messages")
    visible_text = "\n".join(
        message.get("content", "")
        for message in messages
        if isinstance(message, Mapping) and isinstance(message.get("content"), str)
    )
    missing_ids = [task.task_id for task in atomic_tasks if task.task_id not in visible_text]
    missing_prompts = [task.task_id for task in atomic_tasks if task.prompt not in visible_text]
    if missing_ids or missing_prompts:
        raise ValueError(
            f"task-pool batch does not match original request prompt; "
            f"missing_ids={missing_ids}, missing_prompts={missing_prompts}"
        )


def _validate_first_request_profile(observation: Observation, envelopes: list[dict[str, Any]]) -> None:
    request = envelopes[0]
    options = request.get("options")
    if not isinstance(options, Mapping):
        raise ValueError("first request envelope is missing inference options")
    if options.get("seed") != observation.inference_seed:
        raise ValueError("first request seed does not match failed observation")
    if bool(request.get("think")) != observation.profile.thinking:
        raise ValueError("first request thinking profile does not match failed observation")
    if options.get("temperature") != observation.profile.temperature:
        raise ValueError("first request temperature does not match failed observation profile")
    if observation.profile.thinking and options.get("num_predict") != observation.profile.thinking_budget:
        raise ValueError("first request thinking budget does not match failed observation profile")


def build_failure_fixture(
    *,
    failed_observation: Observation,
    atomic_tasks: Sequence[AtomicTask],
    raw_trial: Mapping[str, Any],
    store: ReplayStore,
    source_campaign_id: str,
    runtime_provenance: Mapping[str, Any],
    partition: Partition,
    source_evidence_refs: Sequence[str],
) -> FailureFixture:
    """Freeze one failed V2 atomic observation in its complete physical batch context."""

    if not isinstance(failed_observation, Observation):
        raise TypeError("failed_observation must be an Observation")
    if not isinstance(store, ReplayStore):
        raise TypeError("store must be a ReplayStore")
    if not isinstance(source_campaign_id, str) or not source_campaign_id.strip():
        raise ValueError("source_campaign_id is required")

    batch = tuple(atomic_tasks)
    focus_task = _validate_tasks(failed_observation, batch)
    failure_classes = _failure_classes(failed_observation)
    runtime = _json_copy(runtime_provenance, name="runtime provenance")
    trial_id, envelopes = _request_envelopes(failed_observation, raw_trial, runtime)
    _ensure_batch_visible(envelopes, batch)
    _validate_first_request_profile(failed_observation, envelopes)

    visible = {"request_envelopes": envelopes}
    _scan_secrets(visible, label="model-visible replay payload")
    _scan_secrets(runtime, label="runtime provenance")
    visible_digest = hashlib.sha256(_canonical(visible)).hexdigest()
    model_digest = runtime.get("model_digest")
    if not isinstance(model_digest, str) or not model_digest:
        raise ValueError("runtime provenance requires model_digest")

    metadata = {
        "stage": failed_observation.stage,
        "batch_id": failed_observation.batch_id,
        "decision_reason": failed_observation.decision_reason,
        "difficulty": focus_task.difficulty,
        "scorer": focus_task.scorer,
        "original_response_text": failed_observation.response_text,
        "raw_call_refs": list(failed_observation.raw_call_refs),
        "physical_calls": failed_observation.physical_calls,
    }
    _scan_secrets(metadata, label="snapshot metadata")

    identity = {
        "source_campaign_id": source_campaign_id,
        "source_trial_id": trial_id,
        "focus_observation_id": failed_observation.observation_id,
        "focus_task_id": failed_observation.task_id,
        "model_visible_asset_sha256": visible_digest,
    }
    snapshot_digest = hashlib.sha256(_canonical(identity)).hexdigest()
    failure_snapshot_id = f"failure-v2-{snapshot_digest[:24]}"

    fixture = FailureFixture(
        failure_snapshot_id=failure_snapshot_id,
        source_campaign_id=source_campaign_id,
        source_trial_id=trial_id,
        focus_observation_id=failed_observation.observation_id,
        focus_task_id=failed_observation.task_id,
        batch_task_ids=tuple(task.task_id for task in batch),
        family=failed_observation.family,
        failure_classes=failure_classes,
        source_model_id=str(runtime["model"]),
        source_model_digest=model_digest,
        source_runtime=runtime,
        inference_profile=_profile_payload(failed_observation),
        inference_seed=failed_observation.inference_seed,
        partition=Partition(partition),
        model_visible_asset_sha256=visible_digest,
        state_hash=visible_digest,
        oracle_ref=f"task-pool-v2:{focus_task.task_id}:expected",
        expected_contract=focus_task.contract,
        source_evidence_refs=tuple(source_evidence_refs),
        metadata=metadata,
    )
    stored_digest = store.put_asset(visible)
    if stored_digest != visible_digest:
        raise RuntimeError("replay asset digest changed during storage")
    return fixture
