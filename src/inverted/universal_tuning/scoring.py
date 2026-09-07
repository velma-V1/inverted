from __future__ import annotations

import ast
import json
import re
from typing import Any

from .core import AtomicScore, AtomicTask, FailureClass

_NUMBER_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12",
}


def _strip_fence(text: str) -> str:
    value = text.strip()
    if value.startswith("```") and value.endswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return value


def _parse_jsonish(text: str) -> Any:
    try:
        return json.loads(_strip_fence(text))
    except (json.JSONDecodeError, TypeError):
        return None


def _semantic_candidate(parsed: Any) -> Any:
    if isinstance(parsed, dict):
        if "answer" in parsed:
            return parsed["answer"]
        keys = list(parsed)
        if keys and all(str(key).isdigit() for key in keys):
            return [parsed[key] for key in sorted(keys, key=lambda k: int(k))]
    if isinstance(parsed, list) and parsed and all(isinstance(item, dict) and len(item) == 1 for item in parsed):
        return [next(iter(item.values())) for item in parsed]
    return parsed


def _canonical(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().casefold()
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_canonical(item) for item in value)
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    return value


def _sequence_quality(candidate: Any, expected: Any) -> float:
    if not isinstance(candidate, list) or not isinstance(expected, (list, tuple)):
        return float(_canonical(candidate) == _canonical(expected))
    if not expected:
        return float(candidate == [])
    matches = sum(
        _canonical(actual) == _canonical(wanted)
        for actual, wanted in zip(candidate, expected)
    )
    return matches / len(expected)


def _normalize_sentence(text: str) -> str:
    value = text.casefold()
    for word, digit in _NUMBER_WORDS.items():
        value = re.sub(rf"\b{word}\b", digit, value)
    return re.sub(r"\s+", " ", value).strip()


def _contains_all_batch_quality(candidate: Any, expected: Any) -> float:
    if not isinstance(candidate, list) or not isinstance(expected, (list, tuple)) or not expected:
        return 0.0
    matches = 0
    for sentence, required in zip(candidate, expected):
        normalized = _normalize_sentence(str(sentence))
        if all(_normalize_sentence(str(token)) in normalized for token in required):
            matches += 1
    return matches / len(expected)


_ALLOWED_CALLS = {
    "max": max, "all": all, "any": any, "sum": sum, "sorted": sorted,
    "set": set, "list": list, "reversed": reversed,
}
_ALLOWED_NODES = (
    ast.Expression, ast.Call, ast.Name, ast.Load, ast.Store, ast.Constant,
    ast.keyword, ast.Compare, ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.Eq,
    ast.NotEq, ast.GeneratorExp, ast.comprehension, ast.Subscript, ast.Slice,
    ast.UnaryOp, ast.USub, ast.UAdd, ast.BoolOp, ast.And, ast.Or,
    ast.BinOp, ast.Mod, ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.IfExp,
)


def _safe_eval_expr(expr: str, env: dict[str, Any]) -> Any:
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"unsafe expression node: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_CALLS:
                raise ValueError("unsafe function call")
    scope = dict(_ALLOWED_CALLS)
    scope.update(env)
    return eval(compile(tree, "<tuning-expression>", "eval"), {"__builtins__": {}}, scope)


def _behavior_scenarios(spec: Any) -> list[tuple[dict[str, Any], Any]]:
    if isinstance(spec, str):
        spec = {"behavior": spec}
    kind = spec.get("behavior")
    if kind == "max_default":
        default = spec.get("default", 0)
        return [({"values": []}, default), ({"values": [1, 5, 2]}, 5), ({"values": [-3, -1]}, -1)]
    if kind in {"all_positive", "all_gt"}:
        threshold = 0 if kind == "all_positive" else spec["threshold"]
        return [({"values": []}, True), ({"values": [threshold + 1, threshold + 3]}, True), ({"values": [threshold, threshold + 2]}, False)]
    if kind == "reverse_items":
        return [({"items": []}, []), ({"items": [1, 2, 3]}, [3, 2, 1]), ({"items": ["a", "b"]}, ["b", "a"])]
    if kind == "sum_multiples":
        d = spec["divisor"]
        return [({"values": []}, 0), ({"values": [d, d + 1, 2*d, 3*d]}, 6*d), ({"values": [1, 2, 3]}, sum(x for x in [1,2,3] if x % d == 0))]
    if kind == "first_default":
        default = spec["default"]
        return [({"items": []}, default), ({"items": [8, 3]}, 8), ({"items": ["x"]}, "x")]
    if kind == "sorted_unique":
        return [({"values": []}, []), ({"values": [3,1,3,2]}, [1,2,3]), ({"values": [-1,2,-1]}, [-1,2])]
    if kind == "count_gt":
        threshold = spec["threshold"]
        return [({"values": []}, 0), ({"values": [threshold-1, threshold+1, threshold+2]}, 2), ({"values": [threshold]}, 0)]
    if kind == "clamp_min":
        minimum = spec["minimum"]
        return [({"value": minimum-5}, minimum), ({"value": minimum}, minimum), ({"value": minimum+4}, minimum+4)]
    if kind == "any_equal":
        target = spec["target"]
        return [({"values": []}, False), ({"values": [target-1, target, target+1]}, True), ({"values": [target+2]}, False)]
    if kind == "sum_values":
        return [({"values": []}, 0), ({"values": [1,2,3]}, 6), ({"values": [-2,5]}, 3)]
    return []


def _expression_matches(expr: str, behavior: Any) -> bool:
    scenarios = _behavior_scenarios(behavior)
    if not scenarios:
        return False
    try:
        return all(_safe_eval_expr(expr, env) == expected for env, expected in scenarios)
    except (SyntaxError, ValueError, TypeError, NameError, IndexError, KeyError):
        return False

def _python_expr_batch_quality(candidate: Any, expected: Any) -> float:
    if not isinstance(candidate, list) or len(candidate) != len(expected) or not expected:
        return 0.0
    passed = sum(
        isinstance(expr, str) and _expression_matches(expr, behavior)
        for expr, behavior in zip(candidate, expected)
    )
    return passed / len(expected)


def _contract_pass(task: AtomicTask, parsed: Any) -> bool:
    if task.contract == "answer_object":
        return isinstance(parsed, dict) and set(parsed) == {"answer"}
    if task.contract == "json":
        return parsed is not None
    return True


def score_atomic_task(task: AtomicTask, response_text: str) -> AtomicScore:
    completed = bool(response_text and response_text.strip())
    if not completed:
        return AtomicScore(
            completed=False, semantic_pass=False, contract_pass=False,
            semantic_quality=0.0, contract_quality=0.0,
            failure_classes=(FailureClass.COMPLETION_FAIL,), reason="empty response",
        )

    parsed = _parse_jsonish(response_text)
    candidate = _semantic_candidate(parsed)
    if task.scorer in {"sequence", "exact_json", "exact_value"}:
        quality = _sequence_quality(candidate, task.expected)
    elif task.scorer == "contains_all_batch":
        quality = _contains_all_batch_quality(candidate, task.expected)
    elif task.scorer == "python_expr_batch":
        quality = _python_expr_batch_quality(candidate, task.expected)
    else:
        return AtomicScore(
            completed=True, semantic_pass=False, contract_pass=_contract_pass(task, parsed),
            semantic_quality=0.0, contract_quality=float(_contract_pass(task, parsed)),
            failure_classes=(FailureClass.SCORER_INVALID,), normalized_answer=candidate,
            reason=f"unknown scorer {task.scorer}",
        )

    semantic_pass = math_is_one(quality)
    contract_pass = _contract_pass(task, parsed)
    failures = []
    if not semantic_pass:
        failures.append(FailureClass.SEMANTIC_FAIL)
    if not contract_pass:
        failures.append(FailureClass.CONTRACT_FAIL)
    return AtomicScore(
        completed=True, semantic_pass=semantic_pass, contract_pass=contract_pass,
        semantic_quality=quality, contract_quality=float(contract_pass),
        failure_classes=tuple(failures), normalized_answer=candidate,
        reason="pass" if not failures else "+".join(item.value for item in failures),
    )


def math_is_one(value: float) -> bool:
    return abs(float(value) - 1.0) <= 1e-12
