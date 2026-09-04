from inverted.harvest_d.d3_closure_scoring import (
    CompletionClass,
    SystemSemantics,
    classify_completion,
    compile_system_disposition,
    score_semantic_action,
)
from inverted.harvest_d.types import Disposition


def test_semantic_action_correctness_is_independent_of_strict_formatting():
    score = score_semantic_action(
        '```json\n{"answer":"USE_CURRENT"}\n```',
        expected_answer="USE_CURRENT",
    )
    assert score.parseable_json is True
    assert score.format_valid is False
    assert score.semantic_action_correct is True


def test_disposition_is_compiled_from_system_semantics():
    assert compile_system_disposition(SystemSemantics(missing_required_evidence=True)) is Disposition.ACQUIRE_EVIDENCE
    assert compile_system_disposition(SystemSemantics(external_effect_status="UNKNOWN")) is Disposition.ESCALATE
    assert compile_system_disposition(SystemSemantics(hard_invariant_ok=False)) is Disposition.SAFE_STOP
    assert compile_system_disposition(SystemSemantics()) is Disposition.EXECUTE


def test_context_exhaustion_is_not_semantic_failure_class():
    result = classify_completion(done_reason="length", input_tokens=100, output_tokens=3996, num_ctx=4096, final_text="")
    assert result is CompletionClass.CONTEXT_EXHAUSTED


def test_empty_final_after_non_exhausted_generation_is_distinct():
    result = classify_completion(done_reason="stop", input_tokens=100, output_tokens=50, num_ctx=4096, final_text="")
    assert result is CompletionClass.EMPTY_FINAL


def test_completed_text_is_semantic_result():
    result = classify_completion(done_reason="stop", input_tokens=100, output_tokens=50, num_ctx=4096, final_text='{"answer":"x"}')
    assert result is CompletionClass.SEMANTIC_RESULT
