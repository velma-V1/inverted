from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .hd_next1_statistics import noninferiority_family_decisions
from .types import SequentialDecision


@dataclass(frozen=True)
class HDNext1AdequacyReport:
    ready_for_owner_authorization: bool
    physical_model_calls: int
    max_fully_powered_zero_loss_cells: int
    question_capabilities: dict[str, str]
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ready_for_owner_authorization": self.ready_for_owner_authorization,
            "physical_model_calls": self.physical_model_calls,
            "max_fully_powered_zero_loss_cells": self.max_fully_powered_zero_loss_cells,
            "question_capabilities": dict(self.question_capabilities),
            "blockers": list(self.blockers),
        }


def max_fully_powered_zero_loss_cells(total_cases: int, *, margin: float = 0.05, family_alpha: float = 0.05) -> int:
    best = 0
    for cells in range(1, total_cases + 1):
        base, remainder = divmod(total_cases, cells)
        ns = [base + (1 if i < remainder else 0) for i in range(cells)]
        if min(ns) <= 0:
            break
        decisions = noninferiority_family_decisions([0] * cells, ns, margin=margin, family_alpha=family_alpha)
        if all(item is SequentialDecision.NONINFERIOR for item in decisions):
            best = cells
        else:
            break
    return best


def evaluate_prerun_adequacy(config: dict[str, Any], design: Any, assignments: Iterable[Any]) -> HDNext1AdequacyReport:
    blockers: list[str] = []
    if design.physical_model_calls != 0:
        blockers.append("zero-call design unexpectedly consumed model inference")
    if design.pairwise_coverage_ratio < 1.0:
        blockers.append("pairwise coverage incomplete")
    if design.required_three_way_coverage_ratio < 1.0:
        blockers.append("required three-way coverage incomplete")
    rows = tuple(assignments)
    qwen_confirmation = sum(row.model_key == "QWEN" and row.pool == "confirmation" for row in rows)
    if qwen_confirmation != 63:
        blockers.append(f"Qwen protected confirmation reserve is {qwen_confirmation}, expected 63")
    if config.get("model_call_caps") != {"SMALL_A": 576, "QWEN": 96}:
        blockers.append("model call caps are not frozen")
    if config.get("qwen_pools") != {"calibration": 12, "development": 21, "confirmation": 63}:
        blockers.append("Qwen pool partition is not frozen")
    if float(config.get("effect_margin", -1)) != 0.05:
        blockers.append("five-point decision margin is not frozen")
    capacity = max_fully_powered_zero_loss_cells(
        63, margin=float(config["effect_margin"]), family_alpha=float(config["family_alpha"])
    )
    if capacity < 1:
        blockers.append("protected reserve cannot close even one ideal five-point noninferiority cell")
    capabilities = {
        "Q-MODEL-SUBSTITUTION": "TESTABLE_WITH_UNRESOLVED_FALLBACK",
        "Q-MINIMUM-SUPPORT": "MINIMUM_SUFFICIENT_TESTABLE_WITH_ABLATION",
        "Q-NEGATIVE-TRANSFER-BOUNDARY": "CONDITIONAL_ROUTER_TESTABLE",
    }
    return HDNext1AdequacyReport(
        ready_for_owner_authorization=not blockers,
        physical_model_calls=0,
        max_fully_powered_zero_loss_cells=capacity,
        question_capabilities=capabilities,
        blockers=tuple(blockers),
    )
