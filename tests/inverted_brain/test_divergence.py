from inverted_brain.contracts import AgentEvent, ConstraintEvaluation
from inverted_brain.divergence import localize_critical_divergence


def ev(i, kind, actor="x"):
    return AgentEvent(i, kind, actor, {}, source_id=f"e{i}")


def test_earliest_hard_violation_beats_terminal_error():
    q = [ev(0,"observation"), ev(1,"mutation"), ev(2,"failure"), ev(3,"final")]
    t = [ev(0,"observation"), ev(1,"dependency_inspection"), ev(2,"mutation"), ev(3,"verification")]
    ledger = [ConstraintEvaluation("preserve_state", 1, "violated", recoverable=False, evidence=["e1"])]
    d = localize_critical_divergence(q,t,ledger,{"id":"t"})
    assert d.qwen_index == 1
    assert d.failure_class == "constraint_violation:preserve_state"


def test_recoverable_failure_is_not_automatically_critical():
    q = [ev(0,"observation"), ev(1,"failure"), ev(2,"repair"), ev(3,"verification")]
    t = [ev(0,"observation"), ev(1,"dependency_inspection"), ev(2,"repair"), ev(3,"verification")]
    ledger = [ConstraintEvaluation("x",1,"violated",recoverable=True)]
    d = localize_critical_divergence(q,t,ledger,{"id":"t"})
    assert d.failure_class == "qwen_failure_instead_of_dependency_inspection"
    assert d.qwen_index == 1
