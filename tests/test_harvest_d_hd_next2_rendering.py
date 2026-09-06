import hashlib
import json
from dataclasses import replace

import pytest

from inverted.harvest_d.hd_next2 import rendering
from inverted.harvest_d.models import OllamaChatAdapter
from inverted.harvest_d.d3_cases import generate_d3_cases
from inverted.harvest_d.hd_next1_space import render_treatment_messages
from inverted.harvest_d.hd_next2.ingredients import extract_ingredient_payload
from inverted.harvest_d.hd_next2.rendering import (
    RenderedLayer,
    render_hd_next1_historical_seed,
    render_static_treatment,
    validate_dose_integrity,
)
from inverted.harvest_d.hd_next2.types import DeliveryMode, IngredientLayer, RecurrenceMode, TreatmentPath


def _case():
    return generate_d3_cases(partition="development", seed=20260921, per_family=1)[0]


def _layer(ingredient, dose="CORE", formulation="RAW_PROSE"):
    return IngredientLayer(ingredient, formulation, dose)


def test_empty_path_is_true_raw_no_support_baseline():
    treatment = TreatmentPath("raw", DeliveryMode.STATIC, ())

    rendered = render_static_treatment(_case(), treatment)

    assert rendered.layers == ()
    assert rendered.formulation_id == "RAW_PROSE"
    assert rendered.semantic_atoms == frozenset()
    assert rendered.source_lineage == ()
    assert rendered.rendered == ""
    assert rendered.utf8_bytes == b""
    assert rendered.sha256 == hashlib.sha256(b"").hexdigest()


def test_a_b_a_layers_remain_separately_positioned_and_hashed():
    treatment = TreatmentPath("aba", DeliveryMode.STATIC, (
        IngredientLayer("OBJECTIVE", "RAW_PROSE", "CORE", RecurrenceMode.REPEAT_EXACT, "BEFORE", "JUST_IN_TIME", "SYSTEM_CONTEXT"),
        _layer("SUBGOAL"),
        IngredientLayer("OBJECTIVE", "RAW_PROSE", "CORE", RecurrenceMode.REPEAT_EXACT, "BEFORE", "JUST_IN_TIME", "SYSTEM_CONTEXT"),
    ))

    rendered = render_static_treatment(_case(), treatment)

    assert [layer.position for layer in rendered.layers] == [0, 1, 2]
    assert [layer.ingredient_id for layer in rendered.layers] == ["OBJECTIVE", "SUBGOAL", "OBJECTIVE"]
    assert rendered.layers[0].sha256 == rendered.layers[2].sha256
    assert rendered.layers[0].byte_offsets[1] == rendered.layers[0].byte_offsets[0] + len(rendered.layers[0].utf8_bytes)
    assert rendered.layers[1].byte_offsets[0] == rendered.layers[0].byte_offsets[1] + 1
    assert rendered.layers[2].byte_offsets[0] == rendered.layers[1].byte_offsets[1] + 1
    assert rendered.layers[0].byte_offsets != rendered.layers[2].byte_offsets
    assert rendered.layers[0].recurrence is RecurrenceMode.REPEAT_EXACT
    assert rendered.layers[0].spacing == "BEFORE"
    assert rendered.layers[0].timing == "JUST_IN_TIME"
    assert rendered.layers[0].placement == "SYSTEM_CONTEXT"
    expected_starts = []
    prefix = ""
    for layer in rendered.layers:
        expected_starts.append(len(prefix.encode("utf-8")) // 4)
        prefix += ("\n" if prefix else "") + layer.rendered
    assert [layer.approximate_start_token_position for layer in rendered.layers] == expected_starts
    assert rendered.critical_information_positions == tuple(
        (layer.position, layer.byte_offsets, layer.approximate_start_token_position)
        for layer in rendered.layers
    )


def test_layer_integrity_records_exact_bytes_atoms_lineage_offsets_and_tokens():
    rendered = render_static_treatment(_case(), TreatmentPath("one", DeliveryMode.STATIC, (_layer("OBJECTIVE"),)))
    layer = rendered.layers[0]

    assert layer.utf8_bytes == layer.rendered.encode("utf-8")
    assert layer.sha256 == hashlib.sha256(layer.utf8_bytes).hexdigest()
    assert layer.semantic_atoms == frozenset({"I1.objective"})
    assert layer.source_lineage[-2:] == ("transform:select:objective", "dose:CORE")
    assert layer.byte_offsets == (0, len(layer.utf8_bytes))
    assert layer.approx_token_count == max(1, (len(layer.utf8_bytes) + 3) // 4)


@pytest.mark.parametrize("formulation", ["RAW_PROSE", "TYPED_FIELDS", "STRICT_JSON", "LEDGER", "MATRIX", "GRAPH", "ORDERED_LIST", "COMPACT_SUMMARY", "EXPLICIT_ALTERNATIVES"])
def test_supported_formulations_are_static_and_deterministic(formulation):
    treatment = TreatmentPath("f", DeliveryMode.STATIC, (_layer("CANONICAL_STATE", formulation=formulation),))

    first = render_static_treatment(_case(), treatment)
    second = render_static_treatment(_case(), treatment)

    assert first.layers[0].rendered == second.layers[0].rendered
    assert first.layers[0].sha256 == second.layers[0].sha256


def test_dose_integrity_rejects_adjacent_fake_levels_even_when_hashes_match():
    core = extract_ingredient_payload(_case(), "CANONICAL_STATE", "CORE")
    full = extract_ingredient_payload(_case(), "CANONICAL_STATE", "FULL")
    assert core is not None and full is not None
    assert not validate_dose_integrity(core, core)


def test_dose_integrity_rejects_identical_rendered_bytes_even_with_different_metadata():
    core = render_static_treatment(_case(), TreatmentPath("core", DeliveryMode.STATIC, (_layer("CANONICAL_STATE"),))).layers[0]
    full = replace(
        core,
        dose_id="FULL",
        semantic_atoms=core.semantic_atoms | {"I2.extra"},
        source_lineage=core.source_lineage + ("dose:FULL",),
    )

    assert not validate_dose_integrity(core, full)


def test_rendered_canonical_state_core_and_full_have_distinct_hashes_and_valid_integrity():
    case = _case()
    core = render_static_treatment(case, TreatmentPath("core", DeliveryMode.STATIC, (_layer("CANONICAL_STATE", formulation="STRICT_JSON"),))).layers[0]
    full = render_static_treatment(case, TreatmentPath("full", DeliveryMode.STATIC, (_layer("CANONICAL_STATE", "FULL", "STRICT_JSON"),))).layers[0]

    assert core.utf8_bytes != full.utf8_bytes
    assert core.sha256 != full.sha256
    assert validate_dose_integrity(core, full)


def test_unavailable_full_layer_fails_closed_instead_of_rendering_empty_text():
    case = type("Case", (), {"metadata": {"d3_information": {"I1": {"objective": "do work"}}}})()

    with pytest.raises(ValueError, match="unavailable"):
        render_static_treatment(case, TreatmentPath("full", DeliveryMode.STATIC, (_layer("OBJECTIVE", "FULL"),)))


def test_all_formulations_canonically_serialize_nested_values():
    case = type("Case", (), {"metadata": {"d3_information": {
        "I2": {"canonical_version": {"b", "a"}, "stale_candidate_version": {"z": 1, "a": [2, 1]}},
    }}})()
    for formulation in ["RAW_PROSE", "TYPED_FIELDS", "STRICT_JSON", "LEDGER", "MATRIX", "GRAPH", "ORDERED_LIST", "COMPACT_SUMMARY", "EXPLICIT_ALTERNATIVES"]:
        first = render_static_treatment(case, TreatmentPath("f", DeliveryMode.STATIC, (_layer("CANONICAL_STATE", formulation=formulation),)))
        second = render_static_treatment(case, TreatmentPath("f", DeliveryMode.STATIC, (_layer("CANONICAL_STATE", formulation=formulation),)))
        assert first.utf8_bytes == second.utf8_bytes
        assert first.sha256 == second.sha256


@pytest.mark.parametrize("formulation, expected", [
    ("RAW_PROSE", 'I2.canonical_version: {"a":[2,1],"b":["a","z"]}'),
    ("TYPED_FIELDS", 'I2.canonical_version<dict>: {"a":[2,1],"b":["a","z"]}'),
])
def test_prose_formulations_use_recursive_canonical_serialization(formulation, expected):
    case = type("Case", (), {"metadata": {"d3_information": {
        "I2": {"canonical_version": {"b": {"z", "a"}, "a": [2, 1]},
              "stale_candidate_version": {"z": 1}},
    }}})()

    rendered = render_static_treatment(
        case,
        TreatmentPath("f", DeliveryMode.STATIC, (_layer("STATE_DELTA", "FULL", formulation),)),
    )

    assert expected in rendered.rendered
    assert "{" not in expected or "{'" not in rendered.rendered


def test_token_positions_and_cumulative_tokens_use_joined_model_visible_stream():
    treatment = TreatmentPath("joined", DeliveryMode.STATIC, (
        _layer("OBJECTIVE"),
        _layer("SUBGOAL"),
    ))

    rendered = render_static_treatment(_case(), treatment)
    expected_stream = "\n".join(layer.rendered for layer in rendered.layers)
    expected_bytes = expected_stream.encode("utf-8")
    expected_starts = []
    prefix = ""
    for layer in rendered.layers:
        expected_starts.append(len(prefix.encode("utf-8")) // 4)
        prefix += ("\n" if prefix else "") + layer.rendered

    assert rendered.utf8_bytes == expected_bytes
    assert [layer.approximate_start_token_position for layer in rendered.layers] == expected_starts
    expected_cumulative_tokens = max(1, (len(expected_bytes) + 3) // 4) if expected_bytes else 0
    assert rendered.cumulative_tokens == expected_cumulative_tokens
    assert rendered.cumulative_context_tokens == expected_cumulative_tokens
    assert rendered.critical_information_positions == tuple(
        (layer.position, layer.byte_offsets, expected_starts[layer.position])
        for layer in rendered.layers
    )


def test_full_must_be_strict_semantic_superset_and_one_atom_has_no_fake_full():
    case = type("Case", (), {"metadata": {"d3_information": {"I1": {"objective": "do work"}}}})()
    core = extract_ingredient_payload(case, "OBJECTIVE", "CORE")
    assert core is not None
    assert extract_ingredient_payload(case, "OBJECTIVE", "FULL") is None
    assert not validate_dose_integrity(core, None)


def test_historical_seed_delegates_to_frozen_hd_next1_renderer():
    case = _case()
    vector = {f"I{i}": "ON" if i in {1, 2, 9, 10} else "OFF" for i in range(1, 11)}
    vector.update({f"A{i}": "TARGET" if i in {1, 3} else "OFF" for i in range(1, 5)})
    vector.update(amount="MINIMUM", ordering="DEFAULT", representation="ADMISSIBLE_ACTION_MATRIX", timing="JUST_IN_TIME", placement="SYSTEM_CONTEXT")

    expected = render_treatment_messages(case, vector)
    actual = render_hd_next1_historical_seed(case)

    assert actual == expected


def test_canonical_a0_raw_request_preserves_frozen_baseline_without_support_context():
    case = _case()
    expected_user = str(case.prompt).replace(
        "Return one JSON object with exactly keys disposition and answer.",
        "Return one JSON object with exactly key answer. Do not return a system disposition.",
    )
    expected_system = (
        "INVERTED HD-NEXT-1 controlled measurement. Use only the supplied model-visible context. "
        "Return exactly one JSON object containing key answer. Do not invent a system disposition."
    )

    actual = rendering.serialize_canonical_a0_request(
        case, "qwen2.5:1.5b-instruct-q8_0", "RAW"
    )

    assert json.loads(actual)["messages"] == [
        {"role": "system", "content": expected_system},
        {"role": "user", "content": expected_user},
    ]
    assert b"HD_NEXT1_CONTEXT" not in actual


def test_canonical_a0_request_bytes_are_the_bytes_ollama_adapter_sends():
    case = _case()
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"model":"qwen3.5:9b-q8_0","message":{"content":"ok"}}'

    def fake_opener(request, **kwargs):
        captured["data"] = request.data
        return FakeResponse()

    system, user, _ = render_hd_next1_historical_seed(case)
    OllamaChatAdapter(
        "qwen3.5:9b-q8_0", opener=fake_opener, think=False
    ).complete(user, system=system)

    actual = rendering.serialize_canonical_a0_request(
        case, "qwen3.5:9b-q8_0", "HISTORICAL_SEED"
    )

    assert actual == captured["data"]


def test_canonical_a0_historical_seed_preserves_frozen_system_context_placement():
    case = _case()
    system, user, _ = render_hd_next1_historical_seed(case)
    expected_messages = [
        {"content": system, "role": "system"},
        {"content": user, "role": "user"},
    ]

    actual = rendering.serialize_canonical_a0_request(
        case, "qwen3.5:9b-q8_0", "HISTORICAL_SEED"
    )

    assert json.loads(actual)["messages"] == expected_messages
