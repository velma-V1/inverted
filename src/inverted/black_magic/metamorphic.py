from __future__ import annotations

from typing import Any


def evaluate_metamorphic_pair(base_result: Any, transformed_result: Any, relation: str) -> dict[str, Any]:
    relation = str(relation).upper()
    if relation == "INVARIANT":
        passed = base_result == transformed_result
    elif relation == "BOUNDARY_FLIP":
        passed = base_result != transformed_result
    else:
        raise ValueError(f"unknown metamorphic relation: {relation}")
    return {
        "relation": relation,
        "base_result": base_result,
        "transformed_result": transformed_result,
        "passed": bool(passed),
    }
