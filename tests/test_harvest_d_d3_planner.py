from inverted.harvest_d.d3_cases import generate_d3_cases
from inverted.harvest_d.d3_config import D3Phase
from inverted.harvest_d.d3_planner import D3ExperimentPlanner


def _planner():
    return D3ExperimentPlanner(
        development_cases=generate_d3_cases(partition="development", seed=20260903, per_family=2),
        fresh_cases=generate_d3_cases(partition="fresh", seed=20260913, per_family=1),
        sealed_cases=generate_d3_cases(partition="sealed", seed=20261003, per_family=1),
        model_keys=("SMALL_A", "QWEN"),
    )


def test_planner_builds_real_raw_and_information_candidates_for_both_models():
    planner = _planner()
    baseline = planner.candidates_for_phase(D3Phase.BASELINE)
    information = planner.candidates_for_phase(D3Phase.INFORMATION)
    assert baseline
    assert information
    assert {item.model_key for item in baseline} == {"SMALL_A", "QWEN"}
    assert {item.arm_kind for item in baseline} == {"RAW"}
    assert "INFORMATION" in {item.arm_kind for item in information}


def test_information_candidate_renders_nonempty_context_but_raw_does_not_append_packet():
    planner = _planner()
    raw = planner.candidates_for_phase(D3Phase.BASELINE)[0]
    info = planner.candidates_for_phase(D3Phase.INFORMATION)[0]
    raw_plan = raw.to_call_plan()
    info_plan = info.to_call_plan()
    assert "<D3_CONTEXT>" not in raw_plan.prompt
    assert "<D3_CONTEXT>" in info_plan.prompt or "D3_CONTEXT" in (info_plan.system or "")
    assert info_plan.information_packet["rendered"].strip()
    assert info_plan.case is info.case


def test_planner_never_places_hidden_oracle_or_expected_answer_in_model_visible_text():
    planner = _planner()
    for phase in (D3Phase.BASELINE, D3Phase.INFORMATION, D3Phase.REPRESENTATION, D3Phase.NEGATIVE_TRANSFER):
        for item in planner.candidates_for_phase(phase)[:20]:
            plan = item.to_call_plan()
            visible = ((plan.system or "") + "\n" + plan.prompt).lower()
            assert "oracle" not in visible
            assert "expected" not in visible
            assert str(item.case.oracle.expected).lower() not in visible


def test_sealed_candidates_are_distinct_and_only_live_in_sealed_phase():
    planner = _planner()
    sealed = planner.candidates_for_phase(D3Phase.SEALED_CONFIRMATION)
    assert sealed
    assert all(item.sealed for item in sealed)
    sealed_ids = {item.case.case_id for item in sealed}
    for phase in D3Phase:
        if phase is D3Phase.SEALED_CONFIRMATION:
            continue
        assert sealed_ids.isdisjoint({item.case.case_id for item in planner.candidates_for_phase(phase)})


def test_planner_records_zero_call_assistance_replay_opportunities():
    planner = _planner()
    item = planner.candidates_for_phase(D3Phase.COMBINED)[0]
    assert item.zero_call_assistance
    assert {x["mode"] for x in item.zero_call_assistance} == {"OFF", "TARGET", "SHAM"}
    assert {x["mechanism_id"] for x in item.zero_call_assistance} >= {"A2", "A6", "A9"}


def test_planner_uses_adaptive_candidate_pool_not_full_cartesian_product():
    planner = _planner()
    total = sum(len(planner.candidates_for_phase(phase)) for phase in D3Phase)
    impossible_cartesian = 22 * 2 * 10 * 10 * 5 * 4
    assert total < impossible_cartesian
    assert total > 100


def test_candidate_ids_are_unique_across_entire_planner():
    planner = _planner()
    ids = [item.experiment_id for phase in D3Phase for item in planner.candidates_for_phase(phase)]
    assert len(ids) == len(set(ids))
