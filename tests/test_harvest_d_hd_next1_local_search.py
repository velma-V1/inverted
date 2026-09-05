from __future__ import annotations

from inverted.harvest_d.hd_next1_local_search import LOCAL_SEARCH_RULE_HASH, active_support_components, generate_local_variants


def _winner():
    row = {f"I{i}": "OFF" for i in range(1, 11)}
    row.update({"I1": "ON", "I2": "ON", "I4": "ON", "I7": "ON"})
    row.update({f"A{i}": "OFF" for i in range(1, 5)})
    row["A3"] = "TARGET"
    row.update({
        "representation": "TYPED_FIELDS",
        "ordering": "EVIDENCE_FIRST",
        "amount": "MODERATE",
        "timing": "PRE_DECISION",
        "placement": "TASK_CONTEXT",
    })
    return row


def test_local_search_generates_leave_one_out_joint_and_negative_controls():
    winner = _winner()
    variants = generate_local_variants(winner)
    components = set(active_support_components(winner))
    leave_one_out = {row.component_ids[0] for row in variants if row.kind == "LEAVE_ONE_OUT"}
    assert components <= leave_one_out
    assert any(row.kind == "JOINT_REMOVAL" for row in variants)
    assert any(row.kind == "NEGATIVE_TRANSFER" and row.factor_vector["amount"] == "OVERLOADED" for row in variants)
    assert len({row.variant_id for row in variants}) == len(variants)
    assert len(LOCAL_SEARCH_RULE_HASH) == 64


def test_local_search_never_creates_all_information_off_candidate():
    for row in generate_local_variants(_winner()):
        assert any(row.factor_vector[f"I{i}"] == "ON" for i in range(1, 11))
