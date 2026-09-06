"""Static, auditable HD-NEXT-2 treatment rendering."""

from __future__ import annotations

from dataclasses import dataclass, replace as dataclass_replace
import hashlib
import json
from collections.abc import Mapping
from typing import Any

from ..hd_next1_space import _SYSTEM, render_treatment_messages
from ..models import OllamaChatAdapter
from .ingredients import IngredientPayload, extract_ingredient_payload
from .types import DeliveryMode, IngredientLayer, TreatmentPath

SUPPORTED_FORMULATIONS = frozenset({
    "RAW_PROSE", "TYPED_FIELDS", "STRICT_JSON", "LEDGER", "MATRIX",
    "GRAPH", "ORDERED_LIST", "COMPACT_SUMMARY", "EXPLICIT_ALTERNATIVES",
})

@dataclass(frozen=True)
class RenderedLayer:
    position: int
    ingredient_id: str
    formulation_id: str
    dose_id: str
    rendered: str
    utf8_bytes: bytes
    sha256: str
    semantic_atoms: frozenset[str]
    source_lineage: tuple[str, ...]
    byte_offsets: tuple[int, int]
    approx_token_count: int
    recurrence: object
    spacing: str
    timing: str
    placement: str
    trigger: str
    approximate_start_token_position: int


@dataclass(frozen=True)
class RenderedTreatment:
    treatment_id: str
    formulation_id: str
    layers: tuple[RenderedLayer, ...]
    rendered: str
    utf8_bytes: bytes
    sha256: str
    semantic_atoms: frozenset[str]
    source_lineage: tuple[str, ...]
    byte_offsets: tuple[int, int]
    approx_token_count: int
    cumulative_bytes: int
    cumulative_tokens: int
    critical_information_positions: tuple[tuple[int, tuple[int, int], int], ...]
    system: str = ""
    user: str = ""
    metadata: Mapping[str, object] = None  # type: ignore[assignment]

    @property
    def cumulative_context_tokens(self) -> int:
        return self.cumulative_tokens


def _json(value: object) -> str:
    if isinstance(value, Mapping):
        entries = sorted((_json(key), _json(item)) for key, item in value.items())
        return "{" + ",".join(f"{key}:{item}" for key, item in entries) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_json(item) for item in value) + "]"
    if isinstance(value, (set, frozenset)):
        return "[" + ",".join(sorted(_json(item) for item in value)) + "]"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _render_payload(payload: IngredientPayload, formulation: str) -> str:
    value = payload.payload
    if formulation == "STRICT_JSON":
        return _json(value)
    items = sorted(next(iter(value.values())).items(), key=lambda item: _json(item[0]))
    if formulation == "RAW_PROSE":
        return "\n".join(f"{key}: {_json(item)}" for key, item in items)
    if formulation == "TYPED_FIELDS":
        return "\n".join(f"{key}<{type(item).__name__}>: {_json(item)}" for key, item in items)
    if formulation == "LEDGER":
        return "\n".join(f"{key}={_json(item)}" for key, item in items)
    if formulation == "MATRIX":
        return "field | value\n" + "\n".join(f"{key} | {_json(item)}" for key, item in items)
    if formulation == "GRAPH":
        return "\n".join(f"ingredient -> {key} -> {_json(item)}" for key, item in items)
    if formulation == "ORDERED_LIST":
        return "\n".join(f"{index + 1}. {key}: {_json(item)}" for index, (key, item) in enumerate(items))
    if formulation == "COMPACT_SUMMARY":
        return ";".join(f"{key}={_json(item)}" for key, item in items)
    if formulation == "EXPLICIT_ALTERNATIVES":
        return "ALTERNATIVES / CONSTRAINTS\n" + "\n".join(f"{key}={_json(item)}" for key, item in items)
    raise ValueError(f"unsupported formulation: {formulation}")


def _layer(case: object, source: IngredientLayer, position: int, start: int) -> RenderedLayer:
    if source.formulation_id not in SUPPORTED_FORMULATIONS:
        raise ValueError(f"unsupported formulation: {source.formulation_id}")
    payload = extract_ingredient_payload(case, source.ingredient_id, source.dose_id)
    if payload is None:
        raise ValueError(f"unavailable dose: {source.ingredient_id}/{source.dose_id}")
    text = _render_payload(payload, source.formulation_id)
    raw = text.encode("utf-8")
    return RenderedLayer(
        position, source.ingredient_id, source.formulation_id, source.dose_id, text, raw,
        hashlib.sha256(raw).hexdigest(),
        frozenset() if payload is None else payload.semantic_atoms,
        () if payload is None else payload.source_lineage,
        (start, start + len(raw)), max(1, (len(raw) + 3) // 4) if raw else 0,
        source.recurrence, source.spacing, source.timing, source.placement, source.trigger,
        start // 4,
    )


def render_static_treatment(case: object, treatment: TreatmentPath) -> RenderedTreatment:
    """Render all layers once, preserving layer identity and exact UTF-8 evidence."""
    if treatment.delivery_mode is not DeliveryMode.STATIC:
        raise ValueError("progressive execution is outside the static rendering slice")
    rendered_layers: list[RenderedLayer] = []
    cursor = 0
    chunks: list[str] = []
    for position, source in enumerate(treatment.layers):
        item = _layer(case, source, position, cursor)
        item = dataclass_replace(item, approximate_start_token_position=cursor // 4)
        rendered_layers.append(item)
        chunks.append(item.rendered)
        cursor += len(item.utf8_bytes)
        if position + 1 < len(treatment.layers):
            cursor += 1
    rendered = "\n".join(chunks)
    raw = rendered.encode("utf-8")
    return RenderedTreatment(
        treatment.treatment_id,
        treatment.layers[0].formulation_id if treatment.layers else "RAW_PROSE",
        tuple(rendered_layers), rendered, raw, hashlib.sha256(raw).hexdigest(),
        frozenset().union(*(layer.semantic_atoms for layer in rendered_layers)),
        tuple(lineage for layer in rendered_layers for lineage in layer.source_lineage),
        (0, len(raw)), max(1, (len(raw) + 3) // 4) if raw else 0,
        len(raw), max(1, (len(raw) + 3) // 4) if raw else 0,
        tuple((layer.position, layer.byte_offsets, layer.approximate_start_token_position) for layer in rendered_layers),
    )


def _field(value: object, name: str) -> object:
    return getattr(value, name, None) if not isinstance(value, Mapping) else value.get(name)


def _rendered_fields(value: RenderedLayer | RenderedTreatment) -> tuple[object, ...] | None:
    if isinstance(value, RenderedLayer):
        if value.utf8_bytes != value.rendered.encode("utf-8"):
            return None
        if value.sha256 != hashlib.sha256(value.utf8_bytes).hexdigest():
            return None
        return value.ingredient_id, value.dose_id, value.semantic_atoms, value.utf8_bytes, value.sha256
    if isinstance(value, RenderedTreatment):
        if value.utf8_bytes != value.rendered.encode("utf-8"):
            return None
        if value.sha256 != hashlib.sha256(value.utf8_bytes).hexdigest():
            return None
        if not value.layers or any(_rendered_fields(layer) is None for layer in value.layers):
            return None
        dose_ids = {layer.dose_id for layer in value.layers}
        ingredient_ids = {layer.ingredient_id for layer in value.layers}
        if len(dose_ids) != 1 or len(ingredient_ids) != 1:
            return None
        return value.layers[0].ingredient_id, value.layers[0].dose_id, value.semantic_atoms, value.utf8_bytes, value.sha256
    return None


def validate_dose_integrity(core: RenderedLayer | RenderedTreatment | None, full: RenderedLayer | RenderedTreatment | None) -> bool:
    """Return true only for a distinct FULL strict semantic superset of CORE."""
    if core is None or full is None:
        return False
    core_fields = _rendered_fields(core)
    full_fields = _rendered_fields(full)
    if core_fields is None or full_fields is None:
        return False
    core_ingredient, core_dose, core_atoms, core_bytes, core_sha = core_fields
    full_ingredient, full_dose, full_atoms, full_bytes, full_sha = full_fields
    if core_dose != "CORE" or full_dose != "FULL":
        return False
    if core_ingredient != full_ingredient:
        return False
    core_atoms = frozenset(core_atoms)
    full_atoms = frozenset(full_atoms)
    if not core_atoms < full_atoms:
        return False
    return core_bytes != full_bytes and core_sha != full_sha


def render_hd_next1_historical_seed(case: object):
    """Compatibility adapter for the frozen HD-NEXT-1 winning factor vector."""
    vector = {f"I{i}": "ON" if i in {1, 2, 9, 10} else "OFF" for i in range(1, 11)}
    vector.update({f"A{i}": "TARGET" if i in {1, 3} else "OFF" for i in range(1, 5)})
    vector.update(amount="MINIMUM", ordering="DEFAULT", representation="ADMISSIBLE_ACTION_MATRIX", timing="JUST_IN_TIME", placement="SYSTEM_CONTEXT")
    return render_treatment_messages(case, vector)


def serialize_canonical_a0_request(
    case: object, model_id: str, treatment_kind: str,
) -> bytes:
    """Return the exact static Ollama request bytes for one frozen A0 cell."""
    if not isinstance(model_id, str) or not model_id:
        raise ValueError("canonical A0 model identity is required")
    if treatment_kind == "RAW":
        user = str(getattr(case, "prompt")).replace(
            "Return one JSON object with exactly keys disposition and answer.",
            "Return one JSON object with exactly key answer. Do not return a system disposition.",
        )
        system = _SYSTEM
    elif treatment_kind == "HISTORICAL_SEED":
        system, user, _ = render_hd_next1_historical_seed(case)
    else:
        raise ValueError(f"unsupported canonical A0 treatment: {treatment_kind}")
    return OllamaChatAdapter(model_id, think=False).request_bytes(user, system)
