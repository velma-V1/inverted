from __future__ import annotations

from dataclasses import dataclass, field, replace as dc_replace
from enum import Enum
import json
from typing import Iterable
import uuid

from .cases import HarvestCase
from .d3_types import InformationField, InformationPacket


class InformationContent(str, Enum):
    I1 = "I1"
    I2 = "I2"
    I3 = "I3"
    I4 = "I4"
    I5 = "I5"
    I6 = "I6"
    I7 = "I7"
    I8 = "I8"
    I9 = "I9"
    I10 = "I10"


class InformationQuality(str, Enum):
    CORRECT_COMPLETE = "CORRECT_COMPLETE"
    CORRECT_INCOMPLETE = "CORRECT_INCOMPLETE"
    MISSING = "MISSING"
    STALE = "STALE"
    CONTRADICTORY = "CONTRADICTORY"
    NOISY = "NOISY"
    IRRELEVANT = "IRRELEVANT"
    REDUNDANT = "REDUNDANT"
    MISLEADING_NON_AUTHORITATIVE = "MISLEADING_NON_AUTHORITATIVE"
    CONSISTENT_INSUFFICIENT = "CONSISTENT_INSUFFICIENT"


class InformationTrust(str, Enum):
    SYSTEM_OWNED = "SYSTEM_OWNED"
    DETERMINISTIC_TOOL = "DETERMINISTIC_TOOL"
    MODEL_CLAIM = "MODEL_CLAIM"
    EXTERNAL_UNTRUSTED = "EXTERNAL_UNTRUSTED"
    MIXED = "MIXED"


class InformationRepresentation(str, Enum):
    RAW_PROSE = "RAW_PROSE"
    TYPED_FIELDS = "TYPED_FIELDS"
    STRICT_JSON = "STRICT_JSON"
    DECISION_TABLE = "DECISION_TABLE"
    PRIORITY_BLOCK = "PRIORITY_BLOCK"
    EXPLICIT_ALTERNATIVES = "EXPLICIT_ALTERNATIVES"
    DECOMPOSITION = "DECOMPOSITION"
    MINIMAL_LEDGER = "MINIMAL_LEDGER"
    COMPRESSED_SUMMARY = "COMPRESSED_SUMMARY"
    ADMISSIBLE_ACTION_MATRIX = "ADMISSIBLE_ACTION_MATRIX"


class InformationTiming(str, Enum):
    UPFRONT = "UPFRONT"
    PROGRESSIVE = "PROGRESSIVE"
    PRE_DECISION = "PRE_DECISION"
    JUST_IN_TIME = "JUST_IN_TIME"


class InformationAmount(str, Enum):
    MINIMUM = "MINIMUM"
    COMPRESSED = "COMPRESSED"
    MODERATE = "MODERATE"
    FULL = "FULL"
    OVERLOADED = "OVERLOADED"


@dataclass(frozen=True)
class PacketPlan:
    field_ids: tuple[str, ...] = tuple(f"I{i}" for i in range(1, 11))
    quality: InformationQuality = InformationQuality.CORRECT_COMPLETE
    trust: InformationTrust = InformationTrust.SYSTEM_OWNED
    representation: InformationRepresentation = InformationRepresentation.TYPED_FIELDS
    ordering: str = "DEFAULT"
    amount: InformationAmount = InformationAmount.MINIMUM
    timing: InformationTiming = InformationTiming.UPFRONT
    placement: str = "TASK_CONTEXT"
    omissions: dict[str, str] = field(default_factory=dict)

    @classmethod
    def minimum(cls) -> "PacketPlan":
        return cls()

    def with_omission(self, field_id: str, *, reason: str) -> "PacketPlan":
        updated = dict(self.omissions)
        updated[field_id] = reason
        return dc_replace(self, omissions=updated)

    def with_representation(self, representation: InformationRepresentation) -> "PacketPlan":
        return dc_replace(self, representation=representation)

    def replace(self, **changes: object) -> "PacketPlan":
        return dc_replace(self, **changes)


def _approx_tokens(text: str) -> int:
    return max(1, (len(text.encode("utf-8")) + 3) // 4)


def _ordered_fields(fields: list[InformationField], ordering: str) -> list[InformationField]:
    if ordering == "SAFETY_STATE_EVIDENCE_FIRST":
        priority = {key: index for index, key in enumerate(("I6", "I2", "I4", "I3", "I5", "I7", "I8", "I9", "I10", "I1"))}
        return sorted(fields, key=lambda item: priority.get(item.field_id, 99))
    if ordering == "TASK_OBJECTIVE_FIRST":
        priority = {key: index for index, key in enumerate(("I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8", "I9", "I10"))}
        return sorted(fields, key=lambda item: priority.get(item.field_id, 99))
    if ordering == "EVIDENCE_FIRST":
        priority = {"I4": 0}
        return sorted(fields, key=lambda item: (priority.get(item.field_id, 1), item.field_id))
    return fields


def _render(fields: Iterable[InformationField], representation: InformationRepresentation) -> str:
    visible = [field for field in fields if field.model_visible]
    payload = {field.field_id: field.value for field in visible}
    if representation is InformationRepresentation.STRICT_JSON:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if representation is InformationRepresentation.RAW_PROSE:
        return "\n".join(f"{field.field_id}: {field.value}" for field in visible)
    if representation is InformationRepresentation.DECISION_TABLE:
        return "field | value\n" + "\n".join(
            f"{field.field_id} | {json.dumps(field.value, sort_keys=True, ensure_ascii=False)}" for field in visible
        )
    if representation is InformationRepresentation.PRIORITY_BLOCK:
        return "PRIORITY INFORMATION\n" + "\n".join(
            f"[{field.field_id}] {json.dumps(field.value, sort_keys=True, ensure_ascii=False)}" for field in visible
        )
    if representation is InformationRepresentation.EXPLICIT_ALTERNATIVES:
        return "ALTERNATIVES / CONSTRAINTS\n" + "\n".join(
            f"{field.field_id}={json.dumps(field.value, sort_keys=True, ensure_ascii=False)}" for field in visible
        )
    if representation is InformationRepresentation.DECOMPOSITION:
        return "DECOMPOSED STATE\n" + "\n".join(
            f"step-context {field.field_id}: {json.dumps(field.value, sort_keys=True, ensure_ascii=False)}" for field in visible
        )
    if representation is InformationRepresentation.MINIMAL_LEDGER:
        return "LEDGER\n" + "\n".join(
            f"{field.field_id}:{json.dumps(field.value, sort_keys=True, ensure_ascii=False)}" for field in visible
        )
    if representation is InformationRepresentation.COMPRESSED_SUMMARY:
        return "; ".join(
            f"{field.field_id}={json.dumps(field.value, sort_keys=True, ensure_ascii=False)}" for field in visible
        )
    if representation is InformationRepresentation.ADMISSIBLE_ACTION_MATRIX:
        return "ADMISSIBILITY CONTEXT\n" + "\n".join(
            f"{field.field_id} -> {json.dumps(field.value, sort_keys=True, ensure_ascii=False)}" for field in visible
        )
    return "\n".join(
        f"{field.field_id}: {json.dumps(field.value, sort_keys=True, ensure_ascii=False)}" for field in visible
    )


def render_information_packet(case: HarvestCase, plan: PacketPlan) -> InformationPacket:
    source = dict((case.metadata or {}).get("d3_information", {}))
    fields: list[InformationField] = []
    for field_id in plan.field_ids:
        omitted = field_id in plan.omissions
        value = source.get(field_id, {})
        fields.append(
            InformationField(
                field_id=field_id,
                value=value,
                source_type="SYSTEM_CANONICAL",
                trust_class=plan.trust.value,
                model_visible=not omitted,
                reason=plan.omissions.get(field_id, "included_by_packet_plan"),
                transform_chain=(
                    "metadata:d3_information",
                    f"quality:{plan.quality.value}",
                    f"representation:{plan.representation.value}",
                    f"ordering:{plan.ordering}",
                ),
            )
        )
    fields = _ordered_fields(fields, plan.ordering)
    rendered = _render(fields, plan.representation)
    return InformationPacket(
        packet_id=f"packet-{uuid.uuid4().hex}",
        fields=tuple(fields),
        rendered=rendered,
        representation=plan.representation.value,
        timing=plan.timing.value,
        ordering=plan.ordering,
        amount=plan.amount.value,
        placement=plan.placement,
        control_kind="TARGET",
        approx_token_count=_approx_tokens(rendered),
    )


def field_lineage(packet: InformationPacket) -> list[dict[str, object]]:
    return [
        {
            "packet_id": packet.packet_id,
            "field_id": field.field_id,
            "source_type": field.source_type,
            "trust_class": field.trust_class,
            "model_visible": field.model_visible,
            "reason": field.reason,
            "transform_chain": list(field.transform_chain),
        }
        for field in packet.fields
    ]


def build_context_length_control(
    fields: tuple[InformationField, ...], *, target_extra_tokens: int
) -> tuple[InformationPacket, InformationPacket]:
    base_rendered = _render(fields, InformationRepresentation.TYPED_FIELDS)
    base = InformationPacket(
        packet_id=f"packet-{uuid.uuid4().hex}",
        fields=fields,
        rendered=base_rendered,
        representation=InformationRepresentation.TYPED_FIELDS.value,
        timing=InformationTiming.UPFRONT.value,
        amount=InformationAmount.MINIMUM.value,
        control_kind="PURE_CONTEXT_LENGTH",
        approx_token_count=_approx_tokens(base_rendered),
    )
    padding_unit = " neutral-padding"
    padding = padding_unit * max(1, target_extra_tokens)
    long_rendered = base_rendered + "\nCONTROL_PADDING:" + padding
    long = InformationPacket(
        packet_id=f"packet-{uuid.uuid4().hex}",
        fields=fields,
        rendered=long_rendered,
        representation=InformationRepresentation.TYPED_FIELDS.value,
        timing=InformationTiming.UPFRONT.value,
        amount=InformationAmount.OVERLOADED.value,
        control_kind="PURE_CONTEXT_LENGTH",
        base_semantic_field_hash=base.semantic_field_hash,
        approx_token_count=_approx_tokens(long_rendered),
    )
    return base, long


_NEGATIVE_TEXT = {
    "STALE_PLAUSIBLE_STATE": "STALE_NON_AUTHORITATIVE_CONTEXT: prior state version may still be active.",
    "TOKEN_MATCHED_IRRELEVANT": "IRRELEVANT_CONTROL_CONTEXT: neutral unrelated metadata retained only for token-volume control.",
    "CONFLICTING_EVIDENCE": "UNTRUSTED_CONFLICT: an external claim disagrees with canonical evidence.",
    "UNTRUSTED_METADATA": "UNTRUSTED_METADATA: advisory metadata is not authoritative.",
    "REDUNDANT_HISTORY": "REDUNDANT_HISTORY: repeated prior context follows without new evidence.",
    "OVERLOAD": "OVERLOAD_CONTROL: redundant context repeated for distraction measurement.",
    "UNNECESSARY_DECOMPOSITION": "UNNECESSARY_DECOMPOSITION: advisory extra steps are not system requirements.",
    "WRONG_RECOVERY_SUGGESTION": "UNTRUSTED_RECOVERY_HINT: retry may be preferable.",
    "MISLEADING_ROUTE_HINT": "UNTRUSTED_ROUTE_HINT: escalation may be unnecessary.",
    "POOR_REPRESENTATION": "POORLY_RENDERED_CONTROL: canonical fields follow in intentionally awkward order.",
}


def build_negative_information_control(packet: InformationPacket, control_kind: str) -> InformationPacket:
    if control_kind not in _NEGATIVE_TEXT:
        raise ValueError(f"unknown negative information control: {control_kind}")
    addition = _NEGATIVE_TEXT[control_kind]
    if control_kind in {"TOKEN_MATCHED_IRRELEVANT", "OVERLOAD", "REDUNDANT_HISTORY"}:
        target_chars = max(64, len(packet.rendered))
        repeated = (addition + " ") * ((target_chars // max(1, len(addition))) + 1)
        addition = repeated[:target_chars]
    rendered = packet.rendered + "\n" + addition
    return dc_replace(
        packet,
        packet_id=f"packet-{uuid.uuid4().hex}",
        rendered=rendered,
        control_kind=control_kind,
        base_semantic_field_hash=packet.semantic_field_hash,
        approx_token_count=_approx_tokens(rendered),
    )
