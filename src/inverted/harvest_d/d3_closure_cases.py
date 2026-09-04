from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .cases import HarvestCase, OracleKind, OracleSpec
from .d3_cases import generate_d3_cases


_PARTITIONS = {
    "closure-development": ("development", "d3-dev-", "closure-dev-"),
    "closure-r1-calibration": ("development", "d3-dev-", "closure-r1-cal-"),
    "closure-fresh": ("fresh", "d3-fresh-", "closure-fresh-"),
    "closure-sealed": ("sealed", "d3-sealed-", "closure-sealed-"),
}


def generate_closure_cases(
    partition: str,
    *,
    seed: int,
    per_family: int = 1,
) -> tuple[HarvestCase, ...]:
    if partition not in _PARTITIONS:
        raise ValueError(
            "closure partition must be closure-development, closure-r1-calibration, closure-fresh, or closure-sealed"
        )
    base_partition, old_prefix, new_prefix = _PARTITIONS[partition]
    base = generate_d3_cases(partition=base_partition, seed=int(seed), per_family=int(per_family))
    rows: list[HarvestCase] = []
    for case in base:
        expected = case.oracle.expected if isinstance(case.oracle.expected, dict) else {}
        answer = expected.get("answer")
        metadata = dict(case.metadata or {})
        metadata.update(
            {
                "partition": partition,
                "closure_protocol": "D3-CLOSURE-v2",
                "source_generator": "D3_CASE_GENERATOR_WITH_FRESH_CLOSURE_SEED",
                "source_case_id": case.case_id,
            }
        )
        prompt = case.prompt.replace(
            "Return one JSON object with exactly keys disposition and answer.",
            "Return one JSON object with exactly key answer. Do not invent or return a system disposition.",
        )
        rows.append(
            replace(
                case,
                case_id=case.case_id.replace(old_prefix, new_prefix, 1),
                prompt=prompt,
                oracle=OracleSpec(OracleKind.JSON_EQUALS, {"answer": answer}),
                metadata=metadata,
            )
        )
    return tuple(rows)


def one_per_family(cases: Iterable[HarvestCase]) -> tuple[HarvestCase, ...]:
    seen: set[str] = set()
    rows: list[HarvestCase] = []
    for case in cases:
        if case.family in seen:
            continue
        seen.add(case.family)
        rows.append(case)
    return tuple(rows)
