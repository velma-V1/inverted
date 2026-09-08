"""Integrity-gated replay planning and execution for V3 failure fixtures."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from .core import FailureFixture, ReplayMode, ReplayRequest, ReplayResult
from .replay_store import ReplayStore


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(
        _json_value(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _json_copy(value: Any, *, name: str) -> Any:
    try:
        return json.loads(_canonical(value))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite JSON data") from exc


class ReplayAdapter(Protocol):
    def runtime_provenance(self) -> Mapping[str, Any]: ...

    def execute_fixture(
        self, fixture: FailureFixture, visible_payload: Mapping[str, Any], request: ReplayRequest
    ) -> "ReplayCompletion": ...


@dataclass(frozen=True)
class ReplayCompletion:
    completed: bool
    semantic_pass: bool
    contract_pass: bool
    output_payload: Any
    raw_calls: tuple[Mapping[str, Any], ...]
    failure_classes: tuple[str, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("completed", "semantic_pass", "contract_pass"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be boolean")
        if isinstance(self.raw_calls, (str, bytes, bytearray)):
            raise TypeError("raw_calls must be a sequence of mappings")
        calls = tuple(self.raw_calls)
        if any(not isinstance(call, Mapping) for call in calls):
            raise TypeError("raw_calls must contain mappings")
        classes = tuple(self.failure_classes)
        if any(not isinstance(item, str) or not item for item in classes):
            raise TypeError("failure_classes must contain non-blank strings")
        object.__setattr__(self, "raw_calls", calls)
        object.__setattr__(self, "failure_classes", classes)


@dataclass(frozen=True)
class ReplayPlan:
    fixture: FailureFixture
    request: ReplayRequest
    visible_payload: Mapping[str, Any]
    adapter: ReplayAdapter
    runtime_provenance: Mapping[str, Any]
    adapter_changes: Mapping[str, Any]
    changed_values: Mapping[str, tuple[Any, Any]]


def _failure_classes(completion: ReplayCompletion) -> tuple[str, ...]:
    if completion.failure_classes:
        return completion.failure_classes
    if not completion.completed:
        return ("COMPLETION_FAIL",)
    if not completion.semantic_pass:
        return ("SEMANTIC_FAIL",)
    if not completion.contract_pass:
        return ("CONTRACT_FAIL",)
    return ()


def _runtime_diff(source: Mapping[str, Any], target: Mapping[str, Any]) -> dict[str, Any]:
    keys = sorted(set(source) | set(target))
    return {
        key: {"source": source.get(key), "target": target.get(key)}
        for key in keys
        if source.get(key) != target.get(key)
    }


def _registered_dimension(parts: list[str]) -> bool:
    if len(parts) < 3 or parts[0] != "request_envelopes" or not parts[1].isdigit():
        return False
    root = parts[2]
    if root == "model" or root == "stream":
        return False
    if root == "think":
        return len(parts) == 3
    if root == "options":
        return len(parts) >= 4
    if root == "messages":
        return len(parts) >= 3
    if root == "tools":
        return len(parts) >= 3
    return False


def _descend(container: Any, token: str) -> tuple[Any, str | int]:
    if isinstance(container, list):
        if not token.isdigit():
            raise ValueError("list replay dimensions require numeric indices")
        index = int(token)
        if index < 0 or index >= len(container):
            raise ValueError("replay dimension index is out of range")
        return container, index
    if isinstance(container, dict):
        return container, token
    raise ValueError("replay dimension traverses a non-container value")


def _set_dimension(payload: Any, path: str, value: Any) -> tuple[Any, Any]:
    parts = path.split(".")
    if not _registered_dimension(parts):
        raise ValueError(f"replay dimension is not registered: {path}")
    current = payload
    for token in parts[:-1]:
        current, key = _descend(current, token)
        if isinstance(current, list):
            current = current[key]
        else:
            if key not in current:
                raise ValueError(f"replay dimension does not exist: {path}")
            current = current[key]
    parent, key = _descend(current, parts[-1])
    if isinstance(parent, list):
        old = parent[key]
        parent[key] = _json_copy(value, name=f"override {path}")
    else:
        if key not in parent:
            raise ValueError(f"replay dimension does not exist: {path}")
        old = parent[key]
        parent[key] = _json_copy(value, name=f"override {path}")
    return old, parent[key]


def _root_failure_id(store: ReplayStore, fixture: FailureFixture) -> str:
    current = fixture
    seen: set[str] = set()
    while current.parent_failure_snapshot_id is not None:
        if current.failure_snapshot_id in seen:
            raise ValueError("failure lineage cycle")
        seen.add(current.failure_snapshot_id)
        try:
            current = store.get_failure(current.parent_failure_snapshot_id)
        except KeyError as exc:
            raise ValueError("failure lineage has missing parent") from exc
    return current.failure_snapshot_id


class ReplayExecutor:
    def __init__(self, store: ReplayStore, adapters: Mapping[str, ReplayAdapter]) -> None:
        if not isinstance(store, ReplayStore):
            raise TypeError("store must be a ReplayStore")
        self.store = store
        self.adapters = dict(adapters)

    def _validated_parent(self, request: ReplayRequest) -> FailureFixture:
        report = self.store.validate()
        if not report.ok:
            raise ValueError("replay store integrity validation failed")
        try:
            parent = self.store.get_failure(request.parent_failure_snapshot_id)
        except KeyError as exc:
            raise ValueError("replay request parent failure is missing") from exc
        if request.parent_state_hash != parent.state_hash:
            raise ValueError("replay request parent state mismatch")
        if request.failure_snapshot_id != _root_failure_id(self.store, parent):
            raise ValueError("replay request root failure identity mismatch")
        if request.partition != parent.partition:
            raise ValueError("replay request partition mismatch")
        if (request.source_model_id, request.source_model_digest) != (
            parent.source_model_id, parent.source_model_digest
        ):
            raise ValueError("replay request source identity mismatch")
        return parent

    def plan(self, request: ReplayRequest) -> ReplayPlan:
        if not isinstance(request, ReplayRequest):
            raise TypeError("request must be a ReplayRequest")
        fixture = self._validated_parent(request)
        try:
            adapter = self.adapters[request.target_model_id]
        except KeyError as exc:
            raise ValueError(f"no replay adapter for target model {request.target_model_id!r}") from exc
        runtime = _json_copy(adapter.runtime_provenance(), name="adapter runtime provenance")
        runtime_model = runtime.get("model")
        runtime_digest = runtime.get("model_digest")
        if (runtime_model, runtime_digest) != (request.target_model_id, request.target_model_digest):
            if request.mode is ReplayMode.EXACT:
                raise ValueError("exact replay provenance mismatch")
            raise ValueError("target replay provenance mismatch")
        visible = self.store.read_asset(fixture.model_visible_asset_sha256)
        if not isinstance(visible, dict) or not isinstance(visible.get("request_envelopes"), list):
            raise ValueError("replay fixture model-visible asset is invalid")
        payload = _json_copy(visible, name="replay model-visible payload")
        changed: dict[str, tuple[Any, Any]] = {}
        if request.mode is ReplayMode.COUNTERFACTUAL:
            for path in request.changed_dimensions:
                if path == "target_model":
                    raise ValueError("counterfactual replay cannot change target model")
                old, new = _set_dimension(payload, path, request.overrides[path])
                changed[path] = (old, new)
        elif request.mode is ReplayMode.EXACT:
            if request.changed_dimensions or request.overrides:
                raise ValueError("exact replay cannot contain changed dimensions")
        elif request.mode is ReplayMode.CROSS_MODEL:
            for path in request.changed_dimensions:
                if path == "target_model":
                    continue
                old, new = _set_dimension(payload, path, request.overrides[path])
                changed[path] = (old, new)
        source_runtime = dict(fixture.source_runtime)
        source_runtime.setdefault("model", fixture.source_model_id)
        source_runtime.setdefault("model_digest", fixture.source_model_digest)
        adapter_changes = _runtime_diff(source_runtime, runtime) if request.mode is ReplayMode.CROSS_MODEL else {}
        return ReplayPlan(
            fixture=fixture, request=request, visible_payload=payload, adapter=adapter,
            runtime_provenance=runtime, adapter_changes=adapter_changes, changed_values=changed,
        )

    def execute(self, request: ReplayRequest) -> ReplayResult:
        plan = self.plan(request)
        self.store.append(request)
        completion = plan.adapter.execute_fixture(
            plan.fixture, plan.visible_payload, request
        )
        if not isinstance(completion, ReplayCompletion):
            raise TypeError("replay adapter must return ReplayCompletion")
        if not completion.raw_calls:
            raise ValueError("replay completion must preserve raw call evidence")
        raw_calls = tuple(_json_copy(call, name="replay raw call") for call in completion.raw_calls)
        if len(raw_calls) != len(plan.visible_payload["request_envelopes"]):
            raise ValueError("replay raw call count does not match planned physical requests")
        actual_requests: list[dict[str, Any]] = []
        for index, call in enumerate(raw_calls):
            if not isinstance(call, dict) or not isinstance(call.get("request"), dict):
                raise ValueError(f"replay raw call {index} is missing request evidence")
            actual_requests.append(call["request"])
        if request.mode is not ReplayMode.CROSS_MODEL:
            if actual_requests != plan.visible_payload["request_envelopes"]:
                raise ValueError("replay adapter changed undeclared request dimensions")
        else:
            for actual in actual_requests:
                if actual.get("model") != request.target_model_id:
                    raise ValueError("cross-model replay raw request does not use target model")

        output_digest = self.store.put_asset(completion.output_payload)
        raw_digest = self.store.put_asset({"raw_calls": raw_calls})
        failures = _failure_classes(completion)
        child_id: str | None = None
        if failures:
            child_id = self._append_child_failure(
                plan, actual_requests, failures, raw_digest
            )
        result_id = self._result_id(request, completion, output_digest, raw_digest, child_id)
        adapter_changes = dict(plan.adapter_changes)
        if request.mode is ReplayMode.CROSS_MODEL:
            adapter_changes.update(_leaf_diff(
                plan.visible_payload["request_envelopes"], actual_requests, path="request_envelopes"
            ))
        result = ReplayResult(
            replay_result_id=result_id, replay_request_id=request.replay_request_id,
            failure_snapshot_id=request.failure_snapshot_id,
            parent_failure_snapshot_id=request.parent_failure_snapshot_id,
            parent_state_hash=request.parent_state_hash, mode=request.mode,
            target_model_id=request.target_model_id, target_model_digest=request.target_model_digest,
            partition=request.partition, completed=completion.completed,
            semantic_pass=completion.semantic_pass, contract_pass=completion.contract_pass,
            output_asset_sha256=output_digest, raw_call_asset_sha256=raw_digest,
            failure_classes=failures, child_failure_snapshot_id=child_id,
            adapter_changes=adapter_changes, metrics=completion.metrics,
            metadata={"intervention_id": request.intervention_id,
                      "counterfactual_group_id": request.counterfactual_group_id},
        )
        self.store.append(result)
        return result

    @staticmethod
    def _result_id(
        request: ReplayRequest, completion: ReplayCompletion,
        output_digest: str, raw_digest: str, child_id: str | None,
    ) -> str:
        payload = {
            "replay_request_id": request.replay_request_id,
            "completed": completion.completed,
            "semantic_pass": completion.semantic_pass,
            "contract_pass": completion.contract_pass,
            "failure_classes": list(_failure_classes(completion)),
            "output_asset_sha256": output_digest,
            "raw_call_asset_sha256": raw_digest,
            "child_failure_snapshot_id": child_id,
        }
        return f"replay-result-{hashlib.sha256(_canonical(payload)).hexdigest()[:24]}"

    def _append_child_failure(
        self, plan: ReplayPlan, actual_requests: Sequence[Mapping[str, Any]],
        failure_classes: tuple[str, ...], raw_digest: str,
    ) -> str:
        visible = {"request_envelopes": list(actual_requests)}
        visible_digest = self.store.put_asset(visible)
        request = plan.request
        parent = plan.fixture
        identity = {
            "root_failure_snapshot_id": request.failure_snapshot_id,
            "parent_failure_snapshot_id": parent.failure_snapshot_id,
            "replay_request_id": request.replay_request_id,
            "state_hash": visible_digest,
            "failure_classes": list(failure_classes),
        }
        child_id = f"failure-replay-{hashlib.sha256(_canonical(identity)).hexdigest()[:24]}"
        first = actual_requests[0]
        options = first.get("options", {}) if isinstance(first, Mapping) else {}
        if not isinstance(options, Mapping):
            options = {}
        thinking = bool(first.get("think")) if isinstance(first, Mapping) else False
        profile = {
            "thinking_budget": options.get("num_predict", 0) if thinking else 0,
            "temperature": options.get("temperature"),
            "top_p": options.get("top_p"),
            "top_k": options.get("top_k"),
            "min_p": options.get("min_p"),
            "presence_penalty": options.get("presence_penalty"),
            "repeat_penalty": options.get("repeat_penalty"),
        }
        seed = options.get("seed", parent.inference_seed)
        if not isinstance(seed, int) or isinstance(seed, bool):
            seed = parent.inference_seed
        child = FailureFixture(
            failure_snapshot_id=child_id,
            source_campaign_id=parent.source_campaign_id,
            source_trial_id=f"replay:{request.replay_request_id}",
            focus_observation_id=f"replay:{request.replay_request_id}:{parent.focus_task_id}",
            focus_task_id=parent.focus_task_id, batch_task_ids=parent.batch_task_ids,
            family=parent.family, failure_classes=failure_classes,
            source_model_id=request.target_model_id, source_model_digest=request.target_model_digest,
            source_runtime=plan.runtime_provenance, inference_profile=profile,
            inference_seed=seed, partition=request.partition,
            model_visible_asset_sha256=visible_digest, state_hash=visible_digest,
            oracle_ref=parent.oracle_ref, expected_contract=parent.expected_contract,
            source_evidence_refs=tuple(parent.source_evidence_refs) + (
                f"replay-request:{request.replay_request_id}", f"raw-call-asset:{raw_digest}",
            ),
            forensic_asset_sha256=raw_digest,
            oracle_asset_sha256=parent.oracle_asset_sha256,
            metadata={"originating_replay_request_id": request.replay_request_id,
                      "intervention_id": request.intervention_id,
                      "counterfactual_group_id": request.counterfactual_group_id},
            parent_failure_snapshot_id=parent.failure_snapshot_id,
            parent_state_hash=parent.state_hash,
        )
        self.store.append(child)
        return child_id


def _leaf_diff(source: Any, target: Any, *, path: str) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    if isinstance(source, Mapping) and isinstance(target, Mapping):
        for key in sorted(set(source) | set(target)):
            child = f"{path}.{key}" if path else str(key)
            if key not in source:
                changes[child] = {"source": "<MISSING>", "target": target[key]}
            elif key not in target:
                changes[child] = {"source": source[key], "target": "<MISSING>"}
            else:
                changes.update(_leaf_diff(source[key], target[key], path=child))
        return changes
    if isinstance(source, list) and isinstance(target, list):
        limit = max(len(source), len(target))
        for index in range(limit):
            child = f"{path}.{index}"
            if index >= len(source):
                changes[child] = {"source": "<MISSING>", "target": target[index]}
            elif index >= len(target):
                changes[child] = {"source": source[index], "target": "<MISSING>"}
            else:
                changes.update(_leaf_diff(source[index], target[index], path=child))
        return changes
    if source != target:
        changes[path] = {"source": source, "target": target}
    return changes
