from __future__ import annotations

from dataclasses import dataclass
import math

from .hd_next1_statistics import clopper_pearson_upper, noninferiority_family_decisions
from .types import SequentialDecision


@dataclass(frozen=True)
class ArchitectureDecision:
    state: str
    action: str
    detail: str


def compile_model_ownership(*, qwen_only_wins: int, matched_n: int) -> ArchitectureDecision:
    decision = noninferiority_family_decisions([qwen_only_wins], [matched_n], margin=0.05)[0]
    if decision is SequentialDecision.NONINFERIOR:
        return ArchitectureDecision("REDUNDANT", "SMALL_A_OWNS", "Qwen-only loss probability cleared the five-point upper bound")
    return ArchitectureDecision("UNRESOLVED", "RETAIN_BOUNDED_QWEN_ESCALATION", "protected evidence cannot prove Qwen is redundant")


def compile_support_component(*, component_id: str, full_only_wins: int, matched_n: int) -> ArchitectureDecision:
    decision = noninferiority_family_decisions([full_only_wins], [matched_n], margin=0.05)[0]
    if decision is SequentialDecision.NONINFERIOR:
        return ArchitectureDecision("REDUNDANT", "DELETE", f"removing {component_id} cleared the five-point noninferiority bound")
    rate = full_only_wins / matched_n if matched_n else 1.0
    if matched_n > 0 and rate > 0.05:
        return ArchitectureDecision("UNRESOLVED", "RETAIN_PENDING_STRONGER_EVIDENCE", f"{component_id} removal may be materially harmful")
    return ArchitectureDecision("UNRESOLVED", "RETAIN_PENDING_STRONGER_EVIDENCE", "minimality evidence is insufficient")


def _sign_test_pvalue(successes: int, failures: int) -> float:
    n = successes + failures
    if n <= 0:
        return 1.0
    k = min(successes, failures)
    tail = sum(math.comb(n, i) * (0.5 ** n) for i in range(k + 1))
    return min(1.0, 2.0 * tail)


def compile_negative_transfer(*, extra_only_wins: int, minimal_only_wins: int, matched_n: int) -> ArchitectureDecision:
    if matched_n <= 0:
        return ArchitectureDecision("UNRESOLVED", "NO_ROUTER", "no protected matched evidence")
    net = (extra_only_wins - minimal_only_wins) / matched_n
    pvalue = _sign_test_pvalue(extra_only_wins, minimal_only_wins)
    if net > 0.05 and pvalue < 0.05:
        return ArchitectureDecision("REQUIRED", "ALLOW_EXTRA_SUPPORT_IN_STRATUM", "extra support is materially and directionally helpful")
    if net < -0.05 and pvalue < 0.05:
        return ArchitectureDecision("HARMFUL", "FORBID_EXTRA_SUPPORT_IN_STRATUM", "extra support is materially and directionally harmful")
    discordant = extra_only_wins + minimal_only_wins
    if discordant == 0 and clopper_pearson_upper(0, matched_n, 0.05) < 0.05:
        return ArchitectureDecision("REDUNDANT", "USE_MINIMAL_SUPPORT", "support effect is bounded inside the five-point margin")
    return ArchitectureDecision("UNRESOLVED", "NO_ROUTER", "negative-transfer boundary is not confirmatory")


def router_is_promotable(
    *,
    predicate_is_pre_outcome: bool,
    frozen_before_confirmation: bool,
    fresh_reproduced: bool,
    sealed_reproduced: bool,
    absolute_improvement: float,
    prevents_material_safety_regression: bool,
) -> bool:
    return bool(
        predicate_is_pre_outcome
        and frozen_before_confirmation
        and fresh_reproduced
        and sealed_reproduced
        and (float(absolute_improvement) >= 0.05 or prevents_material_safety_regression)
    )
