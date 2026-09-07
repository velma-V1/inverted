import json

from inverted.universal_tuning.core import AtomicTask, FailureClass
from inverted.universal_tuning.scoring import score_atomic_task


def task(expected, scorer="sequence", family="CLASSIFICATION_ROUTING"):
    return AtomicTask(
        task_id="t1", family=family, difficulty=2, prompt="p",
        expected=expected, scorer=scorer, contract="answer_object",
    )


def test_semantic_pass_contract_fail_for_wrong_json_shape():
    result = score_atomic_task(task(["UI", "AUTHORITY", "DEPENDENCY"]),
                               '["UI","AUTHORITY","DEPENDENCY"]')
    assert result.semantic_pass is True
    assert result.contract_pass is False
    assert FailureClass.CONTRACT_FAIL in result.failure_classes
    assert FailureClass.SEMANTIC_FAIL not in result.failure_classes


def test_numeric_key_object_is_semantically_canonicalized():
    text = '{"1":"P","2":"FALSE","3":"YES"}'
    result = score_atomic_task(task(["P", "FALSE", "YES"], family="LOGIC_CONSTRAINTS"), text)
    assert result.semantic_pass and not result.contract_pass


def test_list_of_single_key_objects_is_semantically_canonicalized():
    text = '[{"action":"RECONCILE"},{"action":"REJECT"},{"action":"DENY"}]'
    result = score_atomic_task(task(["RECONCILE", "REJECT", "DENY"], family="AMBIGUITY_UNCERTAINTY"), text)
    assert result.semantic_pass and not result.contract_pass


def test_synthesis_normalizes_number_words_for_semantics_only():
    expected = [["wednesday", "noor", "8"], ["04:15", "7", "dana"]]
    text = json.dumps({"answer": [
        "Noor owns Wednesday with a limit of eight people.",
        "Dana owns the seven minute window at 04:15 UTC.",
    ]})
    result = score_atomic_task(task(expected, scorer="contains_all_batch", family="SYNTHESIS_WRITING"), text)
    assert result.semantic_pass is True
    assert result.contract_pass is True
    assert result.semantic_quality == 1.0


def test_completion_failure_is_not_misclassified_as_semantic_only():
    result = score_atomic_task(task(["A"]), "")
    assert result.completed is False
    assert FailureClass.COMPLETION_FAIL in result.failure_classes


def test_python_expression_batch_scores_behavior_not_exact_strings():
    expected = ["max_default", "all_positive", "reverse_items"]
    text = json.dumps({"answer": [
        "max(values, default=0)",
        "all(v > 0 for v in values)",
        "items[::-1]",
    ]})
    result = score_atomic_task(task(expected, scorer="python_expr_batch", family="CODING_GENERATION"), text)
    assert result.semantic_pass is True
    assert result.contract_pass is True


def test_single_value_wrong_key_preserves_semantics_but_fails_contract():
    task = AtomicTask(
        task_id="route-key", family="CLASSIFICATION_ROUTING", difficulty=2,
        prompt="classify", expected="AUTHORITY", scorer="exact_value",
    )
    score = score_atomic_task(task, '{"result":"AUTHORITY"}')
    assert score.semantic_pass is True
    assert score.contract_pass is False
    assert FailureClass.CONTRACT_FAIL in score.failure_classes
