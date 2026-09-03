from inverted.harvest_d.d3_cases import generate_d3_cases
from inverted.harvest_d.d3_information import PacketPlan, render_information_packet


def test_d3_fresh_bank_covers_all_failure_layers_with_complete_information_fields():
    cases = generate_d3_cases(partition="development", seed=20260903, per_family=4)
    assert len(cases) == 44
    layers = {case.metadata["fault_layer"] for case in cases}
    assert layers == {
        "STATE",
        "EVIDENCE",
        "CONTEXT",
        "TOPOLOGY",
        "AUTHORITY",
        "TRANSACTION",
        "VERIFIER_ORACLE",
        "RECOVERY",
        "ROUTING",
        "GLOBAL_INTERACTION",
        "NOVELTY",
    }
    for case in cases:
        info = case.metadata["d3_information"]
        assert set(info) == {f"I{i}" for i in range(1, 11)}
        assert "expected" not in str(info).lower()
        assert "oracle" not in str(info).lower()
        assert case.metadata["partition"] == "development"


def test_d3_sealed_partition_is_disjoint_from_development_partition():
    development = generate_d3_cases(partition="development", seed=20260903, per_family=2)
    sealed = generate_d3_cases(partition="sealed", seed=20261003, per_family=2)
    assert {case.case_id for case in development}.isdisjoint({case.case_id for case in sealed})
    assert all(case.metadata["partition"] == "sealed" for case in sealed)


def test_generated_cases_render_nonempty_model_information_packets_without_hidden_labels():
    case = generate_d3_cases(partition="development", seed=20260903, per_family=1)[0]
    packet = render_information_packet(case, PacketPlan.minimum())
    assert packet.rendered.strip()
    assert packet.approx_token_count > 1
    assert "expected" not in packet.rendered.lower()
    assert "oracle" not in packet.rendered.lower()


def test_case_generation_is_deterministic_for_same_seed_and_partition():
    a = generate_d3_cases(partition="development", seed=12345, per_family=2)
    b = generate_d3_cases(partition="development", seed=12345, per_family=2)
    assert [(x.case_id, x.prompt, x.oracle.expected, x.metadata) for x in a] == [
        (x.case_id, x.prompt, x.oracle.expected, x.metadata) for x in b
    ]
