import pytest

from inverted.harvest_d.causal import CausalPair, classify_mechanism
from inverted.harvest_d.frontier import CapabilityEnvelope, CapabilityKey, OperatingPoint, intervention_value, minimum_required_scaffolding, size_dependence_index, synergy
from inverted.harvest_d.knowledge import KnowledgeObject, KnowledgeRegistry, PromotionError, PromotionEvidence, ratchet_metrics
from inverted.harvest_d.routing import RouteDecision, compute_routing_metrics, validate_call_rate_matched_sham
from inverted.harvest_d.statistics import classify_sequential_interval
from inverted.harvest_d.types import CapabilityState, MechanismClass, PromotionState, RouteMode, SequentialDecision


def test_capability_envelope_is_per_capability_and_versioned():
    env = CapabilityEnvelope.empty(); k1 = CapabilityKey('qwen', 'semantic', 'F1'); k2 = CapabilityKey('qwen', 'planning', 'F5')
    env2 = env.with_state(k1, CapabilityState.RELIABLE); env3 = env2.with_state(k2, CapabilityState.UNSTABLE)
    assert (env.version, env2.version, env3.version) == (0, 1, 2)
    assert env3.state_for(k1) is CapabilityState.RELIABLE and env3.state_for(k2) is CapabilityState.UNSTABLE


def test_frontier_metrics_are_safe_when_denominator_is_zero():
    assert size_dependence_index(0.0, 0.0) is None and intervention_value(0.2, 0.0) is None
    assert size_dependence_index(0.2, 0.1) == pytest.approx(0.5)
    assert synergy(0.7, 0.5, 0.6, 0.3) == pytest.approx(-0.1)


def test_minimum_required_scaffolding_prefers_least_involved_noninferior_point():
    points = [OperatingPoint('raw', .80, True, .02, 0, 1, 0, 10), OperatingPoint('light', .94, True, .01, 0, 1, .2, 12),
              OperatingPoint('heavy', .95, True, .01, 0, 2, .8, 20), OperatingPoint('unsafe', .99, False, 0, 0, 1, 0, 8)]
    assert minimum_required_scaffolding(points, noninferiority_margin=.02).name == 'light'


def make_obj(): return KnowledgeObject('k1', 1, 'sig', 'hyp', 'mechanism', source_model='qwen')


def test_single_success_cannot_skip_promotion_states():
    reg = KnowledgeRegistry(); reg.add(make_obj())
    with pytest.raises(PromotionError): reg.advance('k1', PromotionState.CAUSALLY_VERIFIED, PromotionEvidence(targeted_success=True), actor='system')


def test_model_actor_cannot_promote_beyond_hypothesis():
    reg = KnowledgeRegistry(); reg.add(make_obj()); reg.advance('k1', PromotionState.HYPOTHESIZED, PromotionEvidence(), actor='model')
    with pytest.raises(PromotionError): reg.advance('k1', PromotionState.CAUSALLY_VERIFIED, PromotionEvidence(same_state=True, targeted_success=True), actor='model')


def test_full_promotion_requires_causal_generalization_and_regression_gates():
    reg = KnowledgeRegistry(); reg.add(make_obj()); reg.advance('k1', PromotionState.HYPOTHESIZED, PromotionEvidence(), actor='model')
    reg.advance('k1', PromotionState.CAUSALLY_VERIFIED, PromotionEvidence(same_state=True, targeted_success=True, sham_success=False), actor='system')
    reg.advance('k1', PromotionState.NEIGHBOR_GENERALIZED, PromotionEvidence(neighbor_passed=True), actor='system')
    reg.advance('k1', PromotionState.FRESH_GENERALIZED, PromotionEvidence(fresh_passed=True), actor='system')
    reg.advance('k1', PromotionState.REGRESSION_SAFE, PromotionEvidence(regression_safe=True), actor='system')
    reg.advance('k1', PromotionState.PROMOTED, PromotionEvidence(), actor='system')
    assert reg.get('k1').state is PromotionState.PROMOTED


def test_hard_invariant_violation_suspends_and_authority_expansion_is_forbidden():
    reg = KnowledgeRegistry(); reg.add(make_obj()); reg.suspend_on_evidence('k1', PromotionEvidence(hard_invariant_violation=True))
    assert reg.get('k1').state is PromotionState.SUSPENDED
    with pytest.raises(PromotionError): reg.validate_automatic_change({'authority_expansion': True})


def test_envelope_update_can_be_rolled_back():
    reg = KnowledgeRegistry(); reg.add(make_obj()); env = CapabilityEnvelope.empty(); key = CapabilityKey('small', 'semantic', 'F1')
    assert reg.apply_envelope_update(env, key, CapabilityState.RELIABLE).version == 1
    assert reg.rollback_envelope().version == 0


def test_ratchet_metrics_include_negative_transfer():
    m = ratchet_metrics(investigated=10, externalized=5, previously_qwen_required=4, qwen_retired=2, transfer_eligible=5, small_takeovers=3,
                        applicable_future=10, reused=7, prior_correct_exposed=20, harmed=1, territory_before=100, territory_after=104)
    assert m.capability_expansion_rate == pytest.approx(.5) and m.qwen_retirement_rate == pytest.approx(.5)
    assert m.negative_transfer_rate == pytest.approx(.05) and m.capability_regression_rate == 0


def test_routing_metrics_separate_missed_and_false_escalation():
    rows = [RouteDecision('a', RouteMode.ROUTINE_LOCAL, RouteMode.QWEN_STANDARD), RouteDecision('b', RouteMode.QWEN_STANDARD, RouteMode.ROUTINE_LOCAL),
            RouteDecision('c', RouteMode.QWEN_STANDARD, RouteMode.QWEN_STANDARD), RouteDecision('d', RouteMode.SCAFFOLDED_LOCAL, RouteMode.SCAFFOLDED_LOCAL)]
    m = compute_routing_metrics(rows)
    assert (m.missed_escalations, m.false_escalations) == (1, 1)
    assert m.qwen_precision == pytest.approx(.5) and m.qwen_recall == pytest.approx(.5) and m.qwen_call_fraction == pytest.approx(.5)


def test_random_sham_router_must_match_qwen_call_rate():
    target = [RouteMode.QWEN_STANDARD, RouteMode.ROUTINE_LOCAL] * 5; matched = [RouteMode.QWEN_MAX, RouteMode.SCAFFOLDED_LOCAL] * 5
    assert validate_call_rate_matched_sham(target, matched, tolerance=.01)
    assert not validate_call_rate_matched_sham(target, [RouteMode.QWEN_STANDARD] * 10, tolerance=.01)


def pair(target, sham, region='r'): return CausalPair('state', 'm', region, target, sham)


def test_causal_classification_required_redundant_harmful_conditional():
    assert classify_mechanism([pair(1,0), pair(1,0)], margin=.1) is MechanismClass.REQUIRED
    assert classify_mechanism([pair(1,1), pair(0,0)], margin=.1) is MechanismClass.REDUNDANT
    assert classify_mechanism([pair(0,1), pair(0,1)], margin=.1) is MechanismClass.HARMFUL
    assert classify_mechanism([pair(1,0,'a'), pair(0,0,'b')], margin=.1) is MechanismClass.CONDITIONAL


def test_causal_pair_requires_same_state_hash():
    p = CausalPair('same', 'm', 'r', 1, 0, sham_state_hash='different')
    assert not p.valid_same_state and classify_mechanism([p]) is MechanismClass.UNRESOLVED


def test_sequential_interval_classification_respects_margin_and_hard_failures():
    assert classify_sequential_interval(.05,.2,margin=.02) is SequentialDecision.SUPERIOR
    assert classify_sequential_interval(-.01,.1,margin=.02) is SequentialDecision.NONINFERIOR
    assert classify_sequential_interval(-.2,-.03,margin=.02) is SequentialDecision.HARMFUL
    assert classify_sequential_interval(-.5,.5,margin=.02) is SequentialDecision.UNRESOLVED
    assert classify_sequential_interval(.2,.3,margin=.02,hard_violation=True) is SequentialDecision.HARMFUL
    assert classify_sequential_interval(-.5,.5,margin=.02,futile=True) is SequentialDecision.FUTILE
