from __future__ import annotations

from dataclasses import dataclass, replace as dc_replace
import hashlib
import json
import random
from typing import Any

from .d3_closure_assistance import AssistanceMode, apply_predecision_assistance


_BASE_SYSTEM = (
    "INVERTED D3-CLOSURE controlled measurement. Use only model-visible task/context. "
    "Return exactly one JSON object containing key answer. Do not invent hidden system labels."
)


class UnsupportedTreatment(ValueError):
    pass


@dataclass(frozen=True)
class ClosureTreatmentPlan:
    field_ids: tuple[str, ...] = ("I1", "I2", "I4", "I6", "I7")
    representation: str = "TYPED_FIELDS"
    ordering: str = "DEFAULT"
    amount: str = "MODERATE"
    timing: str = "UPFRONT"
    placement: str = "TASK_CONTEXT"
    assistance: tuple[str, ...] = ()
    shuffle_seed: int = 20260903

    def replace(self, **changes: object) -> "ClosureTreatmentPlan":
        return dc_replace(self, **changes)


@dataclass(frozen=True)
class ClosureRenderedTreatment:
    plan: ClosureTreatmentPlan
    rendered: str
    rendered_hash: str
    semantic_field_hash: str
    field_order: tuple[str, ...]
    assistance_hash: str
    system_message: str
    user_message: str
    system_message_hash: str
    user_message_hash: str
    approx_token_count: int


def _hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _approx_tokens(text: str) -> int:
    return max(1, (len(text.encode("utf-8")) + 3) // 4)


def _ordered_fields(field_ids: tuple[str, ...], ordering: str, seed: int) -> tuple[str, ...]:
    fields = list(field_ids)
    priorities: dict[str, tuple[str, ...]] = {
        "TASK_OBJECTIVE_FIRST": tuple(f"I{i}" for i in range(1, 11)),
        "STATE_FIRST": ("I2", "I1", "I3", "I4", "I5", "I6", "I7", "I8", "I9", "I10"),
        "EVIDENCE_FIRST": ("I4", "I1", "I2", "I3", "I5", "I6", "I7", "I8", "I9", "I10"),
        "SAFETY_STATE_EVIDENCE_FIRST": ("I6", "I2", "I4", "I3", "I5", "I7", "I8", "I9", "I10", "I1"),
    }
    if ordering == "SHUFFLED_CONTROL":
        shuffled = list(fields)
        random.Random(int(seed)).shuffle(shuffled)
        if len(shuffled) > 1 and shuffled == fields:
            shuffled = shuffled[1:] + shuffled[:1]
        return tuple(shuffled)
    if ordering in priorities:
        rank = {field_id: index for index, field_id in enumerate(priorities[ordering])}
        return tuple(sorted(fields, key=lambda field_id: rank.get(field_id, 999)))
    if ordering != "DEFAULT":
        raise UnsupportedTreatment(f"unsupported ordering: {ordering}")
    return tuple(fields)


def _render_representation(ordered: tuple[str, ...], source: dict[str, Any], representation: str) -> str:
    payload = {field_id: source[field_id] for field_id in ordered}
    if representation == "STRICT_JSON":
        return json.dumps(payload, sort_keys=False, separators=(",", ":"), ensure_ascii=False)
    if representation == "RAW_PROSE":
        return "\n".join(f"{field_id}: {source[field_id]}" for field_id in ordered)
    if representation == "DECISION_TABLE":
        return "field | value\n" + "\n".join(
            f"{field_id} | {json.dumps(source[field_id], sort_keys=True, ensure_ascii=False)}" for field_id in ordered
        )
    if representation == "PRIORITY_BLOCK":
        return "PRIORITY INFORMATION\n" + "\n".join(
            f"[{field_id}] {json.dumps(source[field_id], sort_keys=True, ensure_ascii=False)}" for field_id in ordered
        )
    if representation == "EXPLICIT_ALTERNATIVES":
        return "ALTERNATIVES / CONSTRAINTS\n" + "\n".join(
            f"{field_id}={json.dumps(source[field_id], sort_keys=True, ensure_ascii=False)}" for field_id in ordered
        )
    if representation == "DECOMPOSITION":
        return "DECOMPOSED STATE\n" + "\n".join(
            f"step-context {field_id}: {json.dumps(source[field_id], sort_keys=True, ensure_ascii=False)}" for field_id in ordered
        )
    if representation == "MINIMAL_LEDGER":
        return "\n".join(
            f"{field_id}:{json.dumps(source[field_id], sort_keys=True, separators=(',', ':'), ensure_ascii=False)}"
            for field_id in ordered
        )
    if representation == "COMPRESSED_SUMMARY":
        return ";".join(
            f"{field_id}={json.dumps(source[field_id], sort_keys=True, separators=(',', ':'), ensure_ascii=False)}"
            for field_id in ordered
        )
    if representation == "ADMISSIBLE_ACTION_MATRIX":
        return "ADMISSIBILITY CONTEXT\n" + "\n".join(
            f"{field_id} -> {json.dumps(source[field_id], sort_keys=True, ensure_ascii=False)}" for field_id in ordered
        )
    if representation == "TYPED_FIELDS":
        return "\n".join(
            f"{field_id}: {json.dumps(source[field_id], sort_keys=True, ensure_ascii=False)}" for field_id in ordered
        )
    raise UnsupportedTreatment(f"unsupported representation: {representation}")


def _apply_amount(rendered: str, amount: str) -> str:
    if amount == "MINIMUM":
        # Lossless compacting of the same selected semantic field set.
        return " ".join(part.strip() for part in rendered.splitlines() if part.strip())
    if amount == "COMPRESSED":
        return " ".join(rendered.split())
    if amount == "MODERATE":
        return rendered
    if amount == "FULL":
        return "FULL CANONICAL CONTEXT\n" + rendered + "\nEND FULL CANONICAL CONTEXT"
    if amount == "OVERLOADED":
        neutral = " NON_AUTHORITATIVE_NEUTRAL_BURDEN"
        return (
            "FULL CANONICAL CONTEXT\n"
            + rendered
            + "\nEND FULL CANONICAL CONTEXT\nCONTROL_BURDEN:"
            + neutral * max(16, len(rendered) // max(1, len(neutral)))
        )
    raise UnsupportedTreatment(f"unsupported amount: {amount}")


def _context_from_case(case: Any) -> dict[str, Any]:
    information = dict((case.metadata or {}).get("d3_information", {}))
    state = dict(information.get("I2", {}))
    evidence = dict(information.get("I4", {}))
    actions = dict(information.get("I7", {}))
    dependencies = dict(information.get("I8", {}))
    return {
        "canonical_state": state,
        "admissible_actions": list(actions.get("admissible_actions", [])),
        "required_evidence": list(evidence.get("required", [])),
        "available_evidence": list(evidence.get("available", [])),
        "missing_evidence": list(evidence.get("missing", [])),
        "dependencies": dependencies,
    }


def _assistance_payload(case: Any, mechanisms: tuple[str, ...]) -> dict[str, Any]:
    additions: dict[str, Any] = {}
    context = _context_from_case(case)
    for mechanism in mechanisms:
        if mechanism not in {"A1", "A2", "A3", "A4"}:
            raise UnsupportedTreatment(f"unsupported model-visible assistance: {mechanism}")
        result = apply_predecision_assistance(mechanism, AssistanceMode.TARGET, context)
        additions[mechanism] = result.model_visible_additions
    return additions


def _wrap_context(rendered: str) -> str:
    return f"<CLOSURE_CONTEXT>\n{rendered}\n</CLOSURE_CONTEXT>"


def render_treatment(case: Any, plan: ClosureTreatmentPlan) -> ClosureRenderedTreatment:
    if plan.timing == "PROGRESSIVE":
        raise UnsupportedTreatment(
            "PROGRESSIVE is not a valid one-call treatment; it requires a real multi-step delivery protocol"
        )
    if plan.timing not in {"UPFRONT", "PRE_DECISION", "JUST_IN_TIME"}:
        raise UnsupportedTreatment(f"unsupported timing: {plan.timing}")
    if plan.placement not in {"TASK_CONTEXT", "SYSTEM_CONTEXT", "MIXED_CONTEXT"}:
        raise UnsupportedTreatment(f"unsupported placement: {plan.placement}")

    source = dict((case.metadata or {}).get("d3_information", {}))
    selected = tuple(field_id for field_id in plan.field_ids if field_id in source)
    if not selected:
        raise UnsupportedTreatment("treatment must expose at least one applicable information field")
    if any(field_id not in {f"I{i}" for i in range(1, 11)} for field_id in selected):
        raise UnsupportedTreatment("unknown information field")

    ordered = _ordered_fields(selected, plan.ordering, plan.shuffle_seed)
    semantic_payload = {field_id: source[field_id] for field_id in sorted(selected)}
    base_rendered = _render_representation(ordered, source, plan.representation)
    rendered = _apply_amount(base_rendered, plan.amount)

    assistance = _assistance_payload(case, plan.assistance)
    assistance_hash = _hash(assistance)
    assistance_block = ""
    if assistance:
        assistance_block = (
            "<PREDECISION_ASSISTANCE>\n"
            + json.dumps(assistance, sort_keys=True, ensure_ascii=False)
            + "\n</PREDECISION_ASSISTANCE>"
        )

    task = str(case.prompt)
    system = _BASE_SYSTEM
    user = task

    if plan.placement == "SYSTEM_CONTEXT":
        system = system + "\n" + _wrap_context(rendered)
        # System context is necessarily upstream of the user turn. Timing labels
        # that do not create a physically distinct message will collapse through
        # the treatment equivalence key.
        user = task
    elif plan.placement == "TASK_CONTEXT":
        context = _wrap_context(rendered)
        if plan.timing == "UPFRONT":
            user = context + "\n" + task
        elif plan.timing == "PRE_DECISION":
            user = task + "\n" + context + "\nUse the supplied context immediately before deciding."
        else:
            user = task + "\n<JIT_INFORMATION>\n" + rendered + "\n</JIT_INFORMATION>"
    else:
        split = max(1, len(ordered) // 2)
        system_fields = tuple(ordered[:split])
        user_fields = tuple(ordered[split:])
        system_rendered = _apply_amount(_render_representation(system_fields, source, plan.representation), plan.amount)
        user_rendered = (
            _apply_amount(_render_representation(user_fields, source, plan.representation), plan.amount)
            if user_fields
            else ""
        )
        system = system + "\n" + _wrap_context(system_rendered)
        if user_rendered:
            if plan.timing == "UPFRONT":
                user = _wrap_context(user_rendered) + "\n" + task
            elif plan.timing == "PRE_DECISION":
                user = task + "\n" + _wrap_context(user_rendered)
            else:
                user = task + "\n<JIT_INFORMATION>\n" + user_rendered + "\n</JIT_INFORMATION>"

    if assistance_block:
        user = user + "\n" + assistance_block + "\nUse this assistance before making the final decision."

    visible = (system + "\n" + user).lower()
    for forbidden in ("expected_disposition", "hidden_oracle", "oracle.expected"):
        if forbidden in visible:
            raise UnsupportedTreatment(f"model-visible treatment contains forbidden oracle material: {forbidden}")

    return ClosureRenderedTreatment(
        plan=plan,
        rendered=rendered,
        rendered_hash=_hash(rendered),
        semantic_field_hash=_hash(semantic_payload),
        field_order=ordered,
        assistance_hash=assistance_hash,
        system_message=system,
        user_message=user,
        system_message_hash=_hash(system),
        user_message_hash=_hash(user),
        approx_token_count=_approx_tokens(system + "\n" + user),
    )
