from __future__ import annotations

from dataclasses import dataclass

from .types import RouteMode

_QWEN = {RouteMode.QWEN_STANDARD, RouteMode.QWEN_MAX, RouteMode.NOVELTY_INVESTIGATION}

@dataclass(frozen=True)
class RouteDecision:
    case_id: str
    chosen: RouteMode
    optimal_after: RouteMode

@dataclass(frozen=True)
class RoutingMetrics:
    missed_escalations: int
    false_escalations: int
    qwen_precision: float | None
    qwen_recall: float | None
    qwen_call_fraction: float
    routing_regret: float
    premature_escalations: int
    late_escalations: int

def _safe(num: int, den: int) -> float | None:
    return None if den == 0 else num / den

def compute_routing_metrics(rows: list[RouteDecision]) -> RoutingMetrics:
    chosen_qwen = sum(r.chosen in _QWEN for r in rows)
    needed_qwen = sum(r.optimal_after in _QWEN for r in rows)
    true_qwen = sum(r.chosen in _QWEN and r.optimal_after in _QWEN for r in rows)
    missed = sum(r.chosen not in _QWEN and r.optimal_after in _QWEN for r in rows)
    false = sum(r.chosen in _QWEN and r.optimal_after not in _QWEN for r in rows)
    regret = 0.0 if not rows else sum(r.chosen != r.optimal_after for r in rows) / len(rows)
    return RoutingMetrics(missed, false, _safe(true_qwen, chosen_qwen), _safe(true_qwen, needed_qwen),
                          0.0 if not rows else chosen_qwen / len(rows), regret, false, missed)

def _qwen_fraction(routes: list[RouteMode]) -> float:
    return 0.0 if not routes else sum(r in _QWEN for r in routes) / len(routes)

def validate_call_rate_matched_sham(target: list[RouteMode], sham: list[RouteMode], *, tolerance: float = 0.02) -> bool:
    return len(target) == len(sham) and abs(_qwen_fraction(target) - _qwen_fraction(sham)) <= tolerance
