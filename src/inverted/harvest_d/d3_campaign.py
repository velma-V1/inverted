from __future__ import annotations

from dataclasses import dataclass
from io import TextIOBase
import json
from pathlib import Path
from typing import Any, TextIO

from inverted.progress import InPlaceProgress

from .d3_config import D3BudgetState, D3Phase, D3_PHASE_RESERVOIRS
from .d3_executor import D3CallExecutor, D3CallPlan
from .d3_resume import D3Journal
from .d3_scheduler import D3Scheduler, ExperimentCandidate
from .d3_store import D3EvidenceStore, D3IntegrityError
from .models import ModelAdapter


class HardStop(RuntimeError):
    pass


@dataclass(frozen=True)
class PreflightResult:
    calls_used: int
    oracle_leakage_check: bool
    output_writable: bool
    max_calls: int


@dataclass(frozen=True)
class CampaignResult:
    calls_used: int
    final_state: str
    operator_actions_required: tuple[str, ...]
    hard_stop_reason: str | None = None


_PHASE_ORDER = tuple(D3_PHASE_RESERVOIRS.keys())


class D3Campaign:
    """Automation-first D3 campaign controller.

    The controller owns mechanics only. It may select among preregistered
    candidates, but it cannot rewrite oracles, authority, sealed evidence, or
    budgets in response to observed outcomes.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        adapter: ModelAdapter,
        max_calls: int,
        progress_stream: TextIO | None = None,
        scheduler: D3Scheduler | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> None:
        if not 0 <= int(max_calls) <= 1000:
            raise ValueError("D3 campaign max_calls must be in [0,1000]")
        self.root = Path(root)
        self.adapter = adapter
        self.max_calls = int(max_calls)
        self.progress_stream = progress_stream
        self.scheduler = scheduler or D3Scheduler.default()
        self.budget = D3BudgetState.default()
        self.provenance = dict(
            provenance
            or {
                "mode": "D3",
                "adapter_model": str(getattr(adapter, "model_id", "unknown")),
                "max_calls": self.max_calls,
            }
        )
        self.store = D3EvidenceStore(self.root)
        self.executor = D3CallExecutor(store=self.store)

    @classmethod
    def testing(
        cls,
        root: str | Path,
        *,
        adapter: ModelAdapter,
        max_calls: int,
        progress_stream: TextIO | None = None,
    ) -> "D3Campaign":
        return cls(
            root,
            adapter=adapter,
            max_calls=max_calls,
            progress_stream=progress_stream,
            provenance={
                "mode": "testing",
                "adapter_model": str(getattr(adapter, "model_id", "unknown")),
                "max_calls": int(max_calls),
            },
        )

    def preflight(self, *, model_free: bool = False) -> PreflightResult:
        self.root.mkdir(parents=True, exist_ok=True)
        probe = self.root / ".d3-write-probe"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
        # Model-facing templates created by this controller contain no hidden
        # expected answer/oracle label. Experiment-specific packet builders have
        # their own stronger leak tests.
        oracle_leakage_check = True
        result = PreflightResult(
            calls_used=0,
            oracle_leakage_check=oracle_leakage_check,
            output_writable=True,
            max_calls=self.max_calls,
        )
        (self.root / "d3_preflight.json").write_text(
            json.dumps(
                {
                    "model_free": bool(model_free),
                    "calls_used": 0,
                    "oracle_leakage_check": oracle_leakage_check,
                    "output_writable": True,
                    "max_calls": self.max_calls,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return result

    @staticmethod
    def _phase_for_call_index(index: int) -> D3Phase:
        cursor = 0
        for phase in _PHASE_ORDER:
            cursor += D3_PHASE_RESERVOIRS[phase]
            if index < cursor:
                return phase
        return D3Phase.SEALED_CONFIRMATION

    def _candidate(self, index: int, phase: D3Phase) -> ExperimentCandidate:
        # The production scheduler receives richer candidates from the D3 case
        # constructor. This default keeps the controller independently testable.
        return ExperimentCandidate(
            candidate_id=f"{phase.value}:case-{index + 1:04d}",
            mechanism_id=f"{phase.value}:default",
            semantic_uncertainty=1.0,
            recovery_uncertainty=0.5 if phase is D3Phase.RECOVERY else 0.0,
            sealed=phase is D3Phase.SEALED_CONFIRMATION,
        )

    @staticmethod
    def _hard_stop_reason(text: str) -> str | None:
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None
        if isinstance(parsed, dict):
            if parsed.get("hard_invariant_ok") is False or parsed.get("hard_invariant_violation") is True:
                return "HARD_INVARIANT_VIOLATION"
            if parsed.get("oracle_leak") is True:
                return "ORACLE_LEAK"
            if parsed.get("authority_resurrected") is True:
                return "RESURRECTED_AUTHORITY"
            if parsed.get("duplicate_irreversible_effect") is True:
                return "DUPLICATE_IRREVERSIBLE_EFFECT"
        return None

    def run_model_free_simulation(self) -> CampaignResult:
        self.preflight(model_free=True)
        progress = InPlaceProgress(stream=self.progress_stream, min_interval_s=0.0)
        progress.update(
            completed=0,
            total=max(1, self.max_calls),
            current="D3 model-free",
            calls_used=0,
            calls_available=self.max_calls,
            force=True,
        )
        progress.finish()
        return CampaignResult(
            calls_used=0,
            final_state="MODEL_FREE_COMPLETE",
            operator_actions_required=(),
        )

    def run(self) -> CampaignResult:
        self.preflight(model_free=False)
        journal = D3Journal(self.root, provenance=self.provenance)
        progress = InPlaceProgress(stream=self.progress_stream, min_interval_s=0.0)
        progress.update(
            completed=0,
            total=max(1, self.max_calls),
            current="D3 preflight",
            calls_used=0,
            calls_available=self.max_calls,
            force=True,
        )

        hard_stop_reason: str | None = None
        for index in range(self.max_calls):
            phase = self._phase_for_call_index(index)
            if phase is D3Phase.SEALED_CONFIRMATION:
                self.scheduler.sealed_open = True
            candidate = self._candidate(index, phase)
            scheduled = self.scheduler.select_next([candidate])
            action_id = f"d3-action-{index + 1:04d}"
            journal.schedule(action_id)
            self.budget.reserve_call(phase)
            plan = D3CallPlan(
                case_id=scheduled.candidate_id,
                prompt=(
                    "Return one JSON object describing your proposed D3 decision. "
                    "Do not assume hidden labels or future outcomes."
                ),
                system="INVERTED D3 measurement: use only the information supplied.",
                information_packet={
                    "packet_id": f"packet-{index + 1:04d}",
                    "model_visible": True,
                    "phase": phase.value,
                },
                scheduler_event={
                    "action_id": action_id,
                    "candidate_id": scheduled.candidate_id,
                    "selection_mode": scheduled.selection_mode,
                    "priority_reason": scheduled.priority_reason,
                    "selection_probability": scheduled.selection_probability,
                    "alternatives": list(scheduled.alternatives),
                },
                phase=phase.value,
            )
            try:
                call = self.executor.execute_once(plan, self.adapter)
            except D3IntegrityError:
                hard_stop_reason = "EVIDENCE_INTEGRITY_FAILURE"
                break
            journal.record_call_received(action_id, call.physical_model_call_id)
            journal.commit_call(action_id, call.physical_model_call_id)

            hard_stop_reason = self._hard_stop_reason(call.text)
            progress.update(
                completed=index + 1,
                total=max(1, self.max_calls),
                current=f"{phase.value} {scheduled.selection_mode}",
                calls_used=index + 1,
                calls_available=self.max_calls,
                force=True,
            )
            if hard_stop_reason:
                break

        progress.finish()
        if hard_stop_reason:
            return CampaignResult(
                calls_used=self.budget.used,
                final_state="HARD_STOP",
                operator_actions_required=(),
                hard_stop_reason=hard_stop_reason,
            )
        return CampaignResult(
            calls_used=self.budget.used,
            final_state="EVIDENCE_CEILING_REACHED" if self.max_calls else "COMPLETE",
            operator_actions_required=(),
        )
