"""Compile Stage-5 surface points into canonical causal replay interventions."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any

from .causal_core import CausalHypothesis, InterventionDefinition, InterventionKind
from .causal_store import CausalEvidenceStore
from .core import FailureFixture, MechanismLabel
from .interventions import InterventionGenerator
from .replay_store import ReplayStore
from .surface_core import SurfaceAxis, SurfacePoint, SurfaceStudy


SUPPORTED_SURFACE_AXES = frozenset({
    SurfaceAxis.REASONING_BUDGET,
    SurfaceAxis.TEMPERATURE,
    SurfaceAxis.CONTEXT_DOSE,
    SurfaceAxis.REPRESENTATION,
    SurfaceAxis.ORDER,
    SurfaceAxis.RECURRENCE,
    SurfaceAxis.TIMING,
    SurfaceAxis.PLACEMENT,
    SurfaceAxis.CONTEXT_POSITION,
    SurfaceAxis.DELIVERY_MODE,
    SurfaceAxis.TRIGGER_MODE,
})


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _semantic_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value
        if isinstance(parsed, dict) and "semantic_payload" in parsed:
            return _semantic_value(parsed["semantic_payload"])
        return value
    if isinstance(value, Mapping):
        if "semantic_payload" in value:
            return _semantic_value(value["semantic_payload"])
        return {str(key): _semantic_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        items = [_semantic_value(item) for item in value]
        if all(isinstance(item, dict) and "role" in item and "content" in item for item in items):
            return sorted(items, key=lambda item: _canonical(item))
        return items
    return value


def semantic_contract_hash(payload: Any) -> str:
    """Hash semantic payload while ignoring registered representation/order wrappers."""
    return hashlib.sha256(_canonical(_semantic_value(payload))).hexdigest()


def _get_path(payload: Any, path: str) -> Any:
    current = payload
    for token in path.split("."):
        if isinstance(current, list):
            if not token.isdigit():
                raise ValueError(f"list path requires numeric token: {path}")
            current = current[int(token)]
        elif isinstance(current, Mapping):
            if token not in current:
                raise ValueError(f"path does not exist: {path}")
            current = current[token]
        else:
            raise ValueError(f"path traverses non-container: {path}")
    return current


class SurfaceInterventionCompiler:
    """Compile one registered surface point over its proven Plan-2 mechanism."""

    def __init__(self, replay_store: ReplayStore, causal_store: CausalEvidenceStore) -> None:
        if not isinstance(replay_store, ReplayStore):
            raise TypeError("replay_store must be ReplayStore")
        if not isinstance(causal_store, CausalEvidenceStore):
            raise TypeError("causal_store must be CausalEvidenceStore")
        self.replay_store = replay_store
        self.causal_store = causal_store
        self.generator = InterventionGenerator(replay_store, causal_store)

    def _fixture(self, study: SurfaceStudy) -> FailureFixture:
        report = self.replay_store.validate()
        if not report.ok:
            raise ValueError("replay store integrity validation failed")
        fixture = self.replay_store.get_failure(study.failure_snapshot_id)
        if fixture.state_hash != study.parent_state_hash or fixture.partition != study.partition:
            raise ValueError("surface study parent lineage does not match replay fixture")
        return fixture

    def _mechanism_context(
        self, study: SurfaceStudy
    ) -> tuple[MechanismLabel, CausalHypothesis, tuple[InterventionDefinition, ...]]:
        labels = [
            record
            for record in self.replay_store.records()
            if isinstance(record, MechanismLabel)
            and record.failure_snapshot_id == study.failure_snapshot_id
            and record.mechanism_id == study.mechanism_id
            and record.parent_state_hash == study.parent_state_hash
        ]
        if not labels:
            raise ValueError("surface study mechanism is not canonical replay evidence")
        label = labels[-1]
        hypotheses = {
            item.hypothesis_id: item
            for item in self.causal_store.hypotheses(study.failure_snapshot_id)
        }
        hypothesis = hypotheses.get(label.hypothesis_id)
        if hypothesis is None:
            raise ValueError("surface mechanism hypothesis is not registered")
        interventions = tuple(
            self.causal_store.get_intervention(intervention_id)
            for intervention_id in label.intervention_ids
        )
        if not interventions:
            raise ValueError("surface mechanism has no registered intervention")
        return label, hypothesis, interventions

    @staticmethod
    def _compatible_base(
        axis: SurfaceAxis,
        interventions: tuple[InterventionDefinition, ...],
    ) -> InterventionDefinition:
        if axis in {SurfaceAxis.REASONING_BUDGET, SurfaceAxis.TEMPERATURE}:
            kinds = {InterventionKind.COGNITION}
        elif axis in {SurfaceAxis.REPRESENTATION, SurfaceAxis.ORDER, SurfaceAxis.PLACEMENT}:
            kinds = {InterventionKind.REPRESENTATION}
        elif axis in {
            SurfaceAxis.CONTEXT_DOSE,
            SurfaceAxis.CONTEXT_POSITION,
            SurfaceAxis.DELIVERY_MODE,
        }:
            kinds = {InterventionKind.CONTEXT}
        else:
            kinds = {InterventionKind.DELIVERY}
        matches = [item for item in interventions if item.kind in kinds]
        if not matches:
            raise ValueError(f"surface axis {axis.value} is incompatible with mechanism interventions")
        return matches[0]

    def _visible(self, fixture: FailureFixture) -> dict[str, Any]:
        payload = self.replay_store.read_asset(fixture.model_visible_asset_sha256)
        if not isinstance(payload, dict) or not isinstance(payload.get("request_envelopes"), list):
            raise ValueError("surface fixture model-visible asset is invalid")
        return payload

    @staticmethod
    def _merge_dimensions(base: InterventionDefinition) -> tuple[list[str], dict[str, Any]]:
        return list(base.changed_dimensions), dict(base.overrides)

    @staticmethod
    def _ensure_dimension(dimensions: list[str], path: str) -> None:
        if path not in dimensions:
            dimensions.append(path)

    @staticmethod
    def _reduce_to_parent_diff(
        visible: Mapping[str, Any], dimensions: list[str], overrides: Mapping[str, Any]
    ) -> tuple[tuple[str, ...], dict[str, Any]]:
        kept: list[str] = []
        reduced: dict[str, Any] = {}
        for path in dimensions:
            target = overrides[path]
            current = _get_path(visible, path)
            if current == target:
                continue
            kept.append(path)
            reduced[path] = target
        return tuple(kept), reduced

    @staticmethod
    def _budget_paths(visible: Mapping[str, Any], base: InterventionDefinition) -> tuple[str, str]:
        think_path = next(
            (path for path in base.changed_dimensions if path.endswith(".think")),
            "request_envelopes.0.think",
        )
        budget_path = next(
            (path for path in base.changed_dimensions if path.endswith("options.num_predict")),
            "request_envelopes.0.options.num_predict",
        )
        _get_path(visible, think_path)
        _get_path(visible, budget_path)
        return think_path, budget_path

    def _cognition_target(
        self,
        visible: Mapping[str, Any],
        base: InterventionDefinition,
        point: SurfacePoint,
    ) -> tuple[list[str], dict[str, Any], str]:
        dimensions, overrides = self._merge_dimensions(base)
        think_path, budget_path = self._budget_paths(visible, base)
        original_think = bool(_get_path(visible, think_path))

        if point.axis is SurfaceAxis.REASONING_BUDGET:
            if not isinstance(point.value, int) or isinstance(point.value, bool) or point.value < 0:
                raise ValueError("reasoning budget surface values must be non-negative integers")
            self._ensure_dimension(dimensions, think_path)
            self._ensure_dimension(dimensions, budget_path)
            overrides[think_path] = point.value > 0
            overrides[budget_path] = (
                point.value if point.value > 0 else _get_path(visible, budget_path)
            )
            label = f"surface reasoning budget {point.value}"
            if not original_think and point.value > 0:
                label += " direct-to-thinking"
            return dimensions, overrides, label

        if point.axis is SurfaceAxis.TEMPERATURE:
            if not isinstance(point.value, (int, float)) or isinstance(point.value, bool):
                raise ValueError("temperature surface values must be numeric")
            effective_think = bool(overrides.get(think_path, _get_path(visible, think_path)))
            if not effective_think:
                raise ValueError("temperature characterization requires active cognition")
            temp_path = next(
                (path for path in base.changed_dimensions if path.endswith("options.temperature")),
                "request_envelopes.0.options.temperature",
            )
            _get_path(visible, temp_path)
            self._ensure_dimension(dimensions, temp_path)
            overrides[temp_path] = float(point.value)
            return dimensions, overrides, f"surface temperature {float(point.value):.6g}"

        raise ValueError("cognition mechanism does not support this surface axis")

    @staticmethod
    def _effective_messages(
        visible: Mapping[str, Any], base: InterventionDefinition
    ) -> tuple[str, list[dict[str, Any]], int]:
        content_paths = [path for path in base.changed_dimensions if path.endswith(".content")]
        if len(content_paths) != 1:
            raise ValueError("message surface requires exactly one semantic content leaf")
        content_path = content_paths[0]
        parts = content_path.split(".")
        if len(parts) < 5 or parts[-1] != "content" or not parts[-2].isdigit():
            raise ValueError("message surface content path is malformed")
        messages_path = ".".join(parts[:-2])
        rows = json.loads(json.dumps(_get_path(visible, messages_path)))
        index = int(parts[-2])
        rows[index]["content"] = dict(base.overrides).get(
            content_path, rows[index]["content"]
        )
        return messages_path, rows, index

    def _representation_target(
        self,
        visible: Mapping[str, Any],
        base: InterventionDefinition,
        point: SurfacePoint,
    ) -> tuple[list[str], dict[str, Any], str]:
        content_paths = [path for path in base.changed_dimensions if path.endswith(".content")]
        if len(content_paths) != 1:
            raise ValueError("representation surface requires exactly one semantic content leaf")
        path = content_paths[0]
        dimensions, overrides = self._merge_dimensions(base)
        baseline = overrides.get(path, _get_path(visible, path))
        if not isinstance(baseline, str):
            raise ValueError("representation surface requires text semantic payload")
        name = str(point.value).upper()

        if point.axis is SurfaceAxis.REPRESENTATION:
            if name in {"PROSE", "BASE", "ORIGINAL"}:
                represented = baseline
            elif name == "FIELDS":
                represented = json.dumps(
                    {"representation": "FIELDS", "semantic_payload": baseline},
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            else:
                raise ValueError(f"unsupported representation surface value: {point.value!r}")
            if semantic_contract_hash(baseline) != semantic_contract_hash(represented):
                raise ValueError("representation-only treatment changed the semantic contract")
            overrides[path] = represented
            return dimensions, overrides, f"surface representation {name}"

        messages_path, messages, index = self._effective_messages(visible, base)
        if point.axis is SurfaceAxis.ORDER:
            if name in {"BASE", "ORIGINAL"}:
                transformed = messages
            elif name == "REVERSE":
                transformed = list(reversed(messages))
            else:
                raise ValueError(f"unsupported order surface value: {point.value!r}")
        elif point.axis is SurfaceAxis.PLACEMENT:
            if name in {"BASE", "ORIGINAL"}:
                transformed = messages
            elif name in {"FRONT", "END"}:
                target = messages[index]
                transformed = [row for offset, row in enumerate(messages) if offset != index]
                transformed.insert(0 if name == "FRONT" else len(transformed), target)
            else:
                raise ValueError(f"unsupported placement surface value: {point.value!r}")
        else:
            raise ValueError("representation mechanism does not support this surface axis")
        if semantic_contract_hash(messages) != semantic_contract_hash(transformed):
            raise ValueError("order/placement treatment changed the semantic contract")
        return [messages_path], {messages_path: transformed}, f"surface {point.axis.value.lower()} {name}"

    @staticmethod
    def _context_parts(
        visible: Mapping[str, Any], base: InterventionDefinition
    ) -> tuple[str, str, str]:
        content_paths = [path for path in base.changed_dimensions if path.endswith(".content")]
        if len(content_paths) != 1:
            raise ValueError("context surface requires exactly one registered context content leaf")
        path = content_paths[0]
        original = _get_path(visible, path)
        treated = dict(base.overrides).get(path)
        if (
            not isinstance(original, str)
            or not isinstance(treated, str)
            or not treated.startswith(original)
        ):
            raise ValueError("context surface requires an additive registered context treatment")
        delta = treated[len(original):].strip()
        if not delta:
            raise ValueError("registered context treatment adds no measurable context")
        return path, original, delta

    @staticmethod
    def _event_index(fixture: FailureFixture, event: str) -> int:
        raw = fixture.metadata.get("surface_delivery_events", ())
        rows = raw if isinstance(raw, (list, tuple)) else ()
        matches: list[int] = []
        for item in rows:
            if not isinstance(item, Mapping):
                continue
            if str(item.get("event", "")).upper() != event:
                continue
            index = item.get("envelope_index")
            if isinstance(index, int) and not isinstance(index, bool) and index > 0:
                matches.append(index)
        if len(matches) != 1:
            noun = "state transition" if event == "STATE_TRANSITION" else "trigger"
            raise ValueError(
                f"{noun} surface requires exactly one preregistered observable {event} event"
            )
        return matches[0]

    def _context_target(
        self,
        visible: Mapping[str, Any],
        base: InterventionDefinition,
        point: SurfacePoint,
        fixture: FailureFixture,
    ) -> tuple[list[str], dict[str, Any], str]:
        path, original, delta = self._context_parts(visible, base)

        if point.axis is SurfaceAxis.CONTEXT_DOSE:
            if not isinstance(point.value, (int, float)) or isinstance(point.value, bool):
                raise ValueError("context dose must be numeric")
            dose = float(point.value)
            if not 0.0 < dose <= 1.0:
                raise ValueError("context dose must be in (0, 1]")
            words = delta.split()
            keep = max(1, math.ceil(len(words) * dose))
            target = original + "\n\n" + " ".join(words[:keep])
            return [path], {path: target}, f"surface context dose {dose:.6g}"

        if point.axis is SurfaceAxis.CONTEXT_POSITION:
            name = str(point.value).upper()
            if name in {"INLINE", "BASE", "ORIGINAL"}:
                return list(base.changed_dimensions), dict(base.overrides), "surface context position INLINE"
            if name not in {"FRONT", "END"}:
                raise ValueError(f"unsupported context position value: {point.value!r}")
            parts = path.split(".")
            if len(parts) < 5 or not parts[-2].isdigit():
                raise ValueError("context position requires a message content leaf")
            messages_path = ".".join(parts[:-2])
            messages = json.loads(json.dumps(_get_path(visible, messages_path)))
            index = int(parts[-2])
            role = messages[index].get("role", "user")
            messages[index]["content"] = original
            packet = {"role": role, "content": delta}
            messages.insert(0 if name == "FRONT" else len(messages), packet)
            return [messages_path], {messages_path: messages}, f"surface context position {name}"

        if point.axis is SurfaceAxis.DELIVERY_MODE:
            name = str(point.value).upper()
            if name in {"STATIC", "BASE", "ORIGINAL"}:
                return list(base.changed_dimensions), dict(base.overrides), "surface delivery mode STATIC"
            if name != "PROGRESSIVE":
                raise ValueError(f"unsupported delivery mode value: {point.value!r}")
            target_index = self._event_index(fixture, "STATE_TRANSITION")
            envelopes = visible.get("request_envelopes")
            if not isinstance(envelopes, list) or target_index >= len(envelopes):
                raise ValueError("state transition references unavailable request envelope")
            words = delta.split()
            split = max(1, len(words) // 2)
            early = " ".join(words[:split])
            late = " ".join(words[split:])
            if not late:
                raise ValueError(
                    "progressive delivery requires context divisible across a state transition"
                )
            late_messages = envelopes[target_index].get("messages")
            if (
                not isinstance(late_messages, list)
                or not late_messages
                or not isinstance(late_messages[-1], Mapping)
                or not isinstance(late_messages[-1].get("content"), str)
            ):
                raise ValueError("state transition envelope lacks target message")
            late_path = (
                f"request_envelopes.{target_index}.messages.{len(late_messages) - 1}.content"
            )
            late_original = _get_path(visible, late_path)
            return (
                [path, late_path],
                {
                    path: original + "\n\n" + early,
                    late_path: late_original + "\n\n" + late,
                },
                "surface delivery mode PROGRESSIVE",
            )

        raise ValueError("context mechanism does not support this surface axis")

    def _delivery_target(
        self,
        visible: Mapping[str, Any],
        base: InterventionDefinition,
        point: SurfacePoint,
        fixture: FailureFixture,
    ) -> tuple[list[str], dict[str, Any], str]:
        messages_path, messages, index = self._effective_messages(visible, base)
        target = messages[index]

        if point.axis is SurfaceAxis.RECURRENCE:
            if not isinstance(point.value, int) or isinstance(point.value, bool) or point.value < 1:
                raise ValueError("recurrence surface value must be a positive integer")
            transformed = (
                messages[:index]
                + [target for _ in range(point.value)]
                + messages[index + 1:]
            )
            return [messages_path], {messages_path: transformed}, f"surface recurrence {point.value}"

        if point.axis is SurfaceAxis.TIMING:
            name = str(point.value).upper()
            if name in {"EARLY", "UPFRONT", "BASE", "ORIGINAL"}:
                return list(base.changed_dimensions), dict(base.overrides), "surface timing EARLY"
            if name != "LATE":
                raise ValueError(f"unsupported timing surface value: {point.value!r}")
            envelopes = visible.get("request_envelopes")
            if not isinstance(envelopes, list) or len(envelopes) < 2:
                raise ValueError("late timing surface requires multiple frozen request envelopes")
            late_index = len(envelopes) - 1
            late_path = f"request_envelopes.{late_index}.messages"
            late_messages = json.loads(json.dumps(_get_path(visible, late_path)))
            early_messages = messages[:index] + messages[index + 1:]
            late_messages.append(target)
            return (
                [messages_path, late_path],
                {messages_path: early_messages, late_path: late_messages},
                "surface timing LATE",
            )

        if point.axis is SurfaceAxis.TRIGGER_MODE:
            name = str(point.value).upper()
            if name in {"ALWAYS", "BASE", "ORIGINAL"}:
                return list(base.changed_dimensions), dict(base.overrides), "surface trigger mode ALWAYS"
            event = {
                "FAILURE_TRIGGERED": "FAILURE",
                "VERIFIER_TRIGGERED": "VERIFIER",
            }.get(name)
            if event is None:
                raise ValueError(f"unsupported trigger mode value: {point.value!r}")
            target_index = self._event_index(fixture, event)
            envelopes = visible.get("request_envelopes")
            if not isinstance(envelopes, list) or target_index >= len(envelopes):
                raise ValueError("trigger references unavailable request envelope")
            path, original, delta = self._context_parts(visible, base)
            late_messages = envelopes[target_index].get("messages")
            if (
                not isinstance(late_messages, list)
                or not late_messages
                or not isinstance(late_messages[-1], Mapping)
                or not isinstance(late_messages[-1].get("content"), str)
            ):
                raise ValueError("trigger envelope lacks target message")
            late_path = (
                f"request_envelopes.{target_index}.messages.{len(late_messages) - 1}.content"
            )
            late_original = _get_path(visible, late_path)
            return (
                [path, late_path],
                {path: original, late_path: late_original + "\n\n" + delta},
                f"surface trigger mode {name}",
            )

        raise ValueError("delivery mechanism does not support this registered surface axis")

    def compile_point(
        self,
        study: SurfaceStudy,
        point: SurfacePoint,
        *,
        request_id: str,
        decision_id: str,
    ) -> tuple[InterventionDefinition, Any]:
        if not isinstance(study, SurfaceStudy) or not isinstance(point, SurfacePoint):
            raise TypeError("study and point must be surface contracts")
        if point.study_id != study.study_id:
            raise ValueError("surface point belongs to a different study")
        if (
            point.failure_snapshot_id != study.failure_snapshot_id
            or point.mechanism_id != study.mechanism_id
            or point.parent_state_hash != study.parent_state_hash
            or point.partition != study.partition
        ):
            raise ValueError("surface point lineage differs from study")

        fixture = self._fixture(study)
        _, hypothesis, interventions = self._mechanism_context(study)
        base = self._compatible_base(point.axis, interventions)
        visible = self._visible(fixture)

        if base.kind is InterventionKind.COGNITION:
            dimensions, overrides, label = self._cognition_target(visible, base, point)
        elif base.kind is InterventionKind.CONTEXT:
            dimensions, overrides, label = self._context_target(
                visible, base, point, fixture
            )
        elif base.kind is InterventionKind.REPRESENTATION:
            dimensions, overrides, label = self._representation_target(visible, base, point)
        elif base.kind is InterventionKind.DELIVERY:
            dimensions, overrides, label = self._delivery_target(
                visible, base, point, fixture
            )
        else:
            raise ValueError(
                f"surface compilation is unavailable for mechanism kind {base.kind.value}"
            )

        changed_dimensions, reduced = self._reduce_to_parent_diff(
            visible, dimensions, overrides
        )
        if not changed_dimensions:
            raise ValueError("surface point is the parent baseline and must be reused, not replayed")
        envelopes = visible.get("request_envelopes")
        projected_calls = len(envelopes) if isinstance(envelopes, list) else 1
        intervention = InterventionDefinition.create(
            hypothesis_id=hypothesis.hypothesis_id,
            failure_snapshot_id=fixture.failure_snapshot_id,
            parent_state_hash=fixture.state_hash,
            kind=base.kind,
            label=label,
            changed_dimensions=changed_dimensions,
            overrides=reduced,
            expected_causal_implication=(
                f"surface point {point.axis.value}={point.value!r} changes the active mechanism decision"
            ),
            projected_physical_calls=projected_calls,
            protected_exploration=point.protected_exploration,
        )
        self.causal_store.register_intervention(intervention)
        request = self.generator.compile_request(
            fixture,
            intervention,
            request_id=request_id,
            decision_id=decision_id,
        )
        return intervention, request
