from inverted.arms import Arm, Budget, run_arm
from inverted.models import MockModelAdapter
from inverted.tasks import generate_task


def test_all_six_arms_preserve_task_identity():
    task = generate_task("state", 2, 3)
    model = MockModelAdapter(executor_accuracy=0.8, auditor_accuracy=0.9, seed=7)
    records = [run_arm(arm, task, model, executor_quality=0.8, seed=12, run_id="r", budget=Budget(max_candidates=3, max_tokens=10000)) for arm in Arm]
    assert {r.task_id for r in records} == {task.id}
    assert {r.arm for r in records} == {a.value for a in Arm}


def test_random_auditor_is_seed_reproducible():
    task = generate_task("state", 3, 4)
    model = MockModelAdapter(seed=1)
    a = run_arm(Arm.E_RANDOM_AUDITOR, task, model, 0.5, 99, "r", Budget(max_candidates=4, max_tokens=10000))
    b = run_arm(Arm.E_RANDOM_AUDITOR, task, model, 0.5, 99, "r", Budget(max_candidates=4, max_tokens=10000))
    assert a.candidate_attempts == b.candidate_attempts
    assert a.success == b.success
    assert a.accepted_candidate_id == b.accepted_candidate_id


def test_oracle_auditor_accepts_perfect_candidate():
    task = generate_task("policy", 2, 9)
    model = MockModelAdapter()
    trial = run_arm(Arm.F_ORACLE_AUDITOR, task, model, 1.0, 10, "r", Budget(max_candidates=3, max_tokens=10000))
    assert trial.success is True
    assert trial.candidate_attempts == 1


def test_inverted_auditor_can_reject_bad_candidates():
    task = generate_task("reconciliation", 3, 6)
    model = MockModelAdapter(auditor_accuracy=1.0, seed=5)
    trial = run_arm(Arm.D_INVERTED, task, model, 0.0, 17, "r", Budget(max_candidates=3, max_tokens=10000))
    assert trial.success is False
    assert trial.candidate_attempts == 3
    assert trial.rejections == 3
    assert trial.audit_tn == 3


def test_equal_token_budget_is_enforced():
    task = generate_task("state", 2, 20)
    model = MockModelAdapter(executor_accuracy=1.0)
    trial = run_arm(Arm.A_DIRECT, task, model, 0.8, 1, "r", Budget(max_candidates=3, max_tokens=1))
    assert trial.budget_exhausted is True
    assert trial.success is False

def test_candidate_event_contains_reconstructable_state_evidence():
    task = generate_task("state", 2, 31)
    model = MockModelAdapter(auditor_accuracy=1.0)
    trial = run_arm(Arm.D_INVERTED, task, model, 0.8, 55, "r", Budget(max_candidates=2, max_tokens=10000))
    event = trial.candidate_events[0]
    required = {"candidate_id", "attempt", "configured_quality", "goal", "pre_state", "post_state", "pre_state_hash", "post_state_hash", "state_diff", "actions", "oracle_success", "faults", "decision"}
    assert required <= set(event)
    assert event["pre_state_hash"] != event["post_state_hash"]
    assert isinstance(event["state_diff"], list)
    assert event["actions"]

def test_checked_direct_baseline_rejects_semantically_wrong_but_structurally_legal_outputs():
    task = generate_task("state", 2, 73)
    model = MockModelAdapter(executor_accuracy=0.0, seed=2)
    trial = run_arm(Arm.B_DIRECT_CHECKED, task, model, 0.8, 41, "r", Budget(max_candidates=3, max_tokens=100000))
    assert trial.success is False
    assert trial.rejections == 3
    assert trial.terminal_status == "REJECTED_ALL"
