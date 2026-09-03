import pytest

from inverted.harvest_d.evidence import EvidenceClaim, EvidenceIntegrityError, EvidenceLedger, EvidenceSource, ReadinessQuestion
from inverted.harvest_d.faults import FaultDefinitionError, FaultInjection, FaultLayer
from inverted.harvest_d.kernel import CanonicalState, EffectStatus, KernelViolation, ProofCarryingAction, TrustedKernel
from inverted.harvest_d.telemetry import SystemInvolvement, architecture_intervention_ratio
from inverted.harvest_d.types import ClaimState, Disposition, DuplicateIdentityError, IdentityRegistry, stable_hash


def test_stable_hash_is_mapping_order_independent():
    assert stable_hash({'b': 2, 'a': 1}) == stable_hash({'a': 1, 'b': 2})


def test_physical_model_call_identity_cannot_repeat():
    registry = IdentityRegistry(); registry.register('call-1')
    with pytest.raises(DuplicateIdentityError): registry.register('call-1')


def test_system_involvement_channels_remain_independent():
    x = SystemInvolvement(context=True, state=True, evidence=True, verification=True, routing=True, knowledge=True)
    assert x.triggered_channels() == {'context', 'state', 'evidence', 'verification', 'routing', 'knowledge'}


def test_architecture_intervention_ratio_counts_consequential_steps():
    rows = [SystemInvolvement(context=True), SystemInvolvement(), SystemInvolvement(state=True)]
    assert architecture_intervention_ratio(rows) == pytest.approx(2/3)


def test_contaminated_diagnostic_evidence_cannot_be_promoted():
    ledger = EvidenceLedger(); ledger.add_source(EvidenceSource('test2', contaminated=True, diagnostic=True, physical_call_ids=('p1',)))
    with pytest.raises(EvidenceIntegrityError): ledger.add_claim(EvidenceClaim('c1', ClaimState.CAUSALLY_VERIFIED, ('test2',)))
    ledger.add_claim(EvidenceClaim('c2', ClaimState.OBSERVED, ('test2',)))


def test_duplicate_physical_call_identity_blocks_evidence_ingestion():
    ledger = EvidenceLedger(); ledger.add_source(EvidenceSource('a', physical_call_ids=('same',)))
    with pytest.raises(EvidenceIntegrityError): ledger.add_source(EvidenceSource('b', physical_call_ids=('same',)))


def test_readiness_question_preserves_contradictions():
    q = ReadinessQuestion('router', supporting=('S2 rich routing',), contradicting=('S2 non-decisive', 'Test2 contaminated'))
    assert len(q.contradicting) == 2


def make_action(kernel, state, action_id='a1', payload=None):
    payload = payload or {'op': 'write', 'path': 'x'}
    lease = kernel.issue_authority(payload)
    return ProofCarryingAction(action_id=action_id, payload=payload, state_version=state.version, authority_id=lease.authority_id)


def test_stale_state_is_rejected():
    kernel = TrustedKernel(CanonicalState(version=2, data={'x': 1})); lease = kernel.issue_authority({'op': 'write'})
    with pytest.raises(KernelViolation): kernel.prepare(ProofCarryingAction('a', {'op': 'write'}, 1, lease.authority_id))


def test_mutated_action_invalidates_authority_binding():
    kernel = TrustedKernel(CanonicalState(version=1, data={})); lease = kernel.issue_authority({'op': 'read'})
    with pytest.raises(KernelViolation): kernel.prepare(ProofCarryingAction('a', {'op': 'delete'}, 1, lease.authority_id))


def test_consumed_authority_cannot_be_reused_or_resurrected_by_rollback():
    kernel = TrustedKernel(CanonicalState(version=1, data={})); action = make_action(kernel, kernel.state)
    tx = kernel.prepare(action); kernel.commit_effect(tx.tx_id, effect_id='effect-1'); kernel.rollback(tx.tx_id)
    with pytest.raises(KernelViolation): kernel.prepare(action)


def test_duplicate_committed_effect_is_blocked():
    kernel = TrustedKernel(CanonicalState(version=1, data={}))
    tx1 = kernel.prepare(make_action(kernel, kernel.state, 'a1')); kernel.commit_effect(tx1.tx_id, effect_id='effect-1')
    tx2 = kernel.prepare(make_action(kernel, kernel.state, 'a2'))
    with pytest.raises(KernelViolation): kernel.commit_effect(tx2.tx_id, effect_id='effect-1')


def test_unknown_effect_requires_reconciliation_not_retry():
    kernel = TrustedKernel(CanonicalState(version=1, data={})); tx = kernel.prepare(make_action(kernel, kernel.state)); kernel.mark_effect_unknown(tx.tx_id)
    assert kernel.transaction(tx.tx_id).effect_status is EffectStatus.UNKNOWN
    with pytest.raises(KernelViolation): kernel.retry(tx.tx_id)
    kernel.reconcile(tx.tx_id, committed=False)
    assert kernel.transaction(tx.tx_id).effect_status is EffectStatus.NOT_COMMITTED


def test_done_is_system_owned_and_requires_no_unknown_transactions():
    kernel = TrustedKernel(CanonicalState(version=1, data={})); tx = kernel.prepare(make_action(kernel, kernel.state)); kernel.mark_effect_unknown(tx.tx_id)
    assert not kernel.can_complete(); kernel.reconcile(tx.tx_id, committed=False); kernel.close(tx.tx_id); assert kernel.can_complete()


def test_fault_injection_requires_expected_response_and_oracle():
    with pytest.raises(FaultDefinitionError):
        FaultInjection('f1', FaultLayer.STATE, 'before', {}, {}, '', Disposition.SAFE_STOP, (), (), '', '', 'reset')
