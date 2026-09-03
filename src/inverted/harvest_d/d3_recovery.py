from __future__ import annotations

from dataclasses import dataclass

from .d3_types import RecoveryChoice, RecoveryStage


@dataclass(frozen=True)
class RecoveryDecision:
    choice: RecoveryChoice
    reason: str
    allow_retry: bool = False


@dataclass(frozen=True)
class RecoveryStep:
    stage: RecoveryStage
    ordinal: int
    detail: str = ""
    choice: RecoveryChoice | None = None
    outcome: str | None = None


@dataclass(frozen=True)
class RecoveryTrace:
    steps: tuple[RecoveryStep, ...]
    local_recovered: bool
    global_invariant_ok: bool
    external_effect_known: bool = True

    def stage(self, stage: RecoveryStage) -> RecoveryStep:
        for step in self.steps:
            if step.stage is stage:
                return step
        raise KeyError(stage)


class RecoveryPolicy:
    """System-owned recovery selection from observable state only."""

    def decide(
        self,
        *,
        external_effect_status: str = "NOT_COMMITTED",
        missing_required_evidence: bool = False,
        hard_invariant_ok: bool = True,
        stale_state: bool = False,
        recoverable_action_failure: bool = False,
    ) -> RecoveryDecision:
        if not hard_invariant_ok:
            return RecoveryDecision(RecoveryChoice.SAFE_STOP, "hard invariant is not intact")
        if external_effect_status == "UNKNOWN":
            return RecoveryDecision(
                RecoveryChoice.RECONCILE,
                "external effect is unknown; reconciliation is mandatory before retry",
            )
        if missing_required_evidence:
            return RecoveryDecision(
                RecoveryChoice.ACQUIRE_EVIDENCE,
                "required evidence is missing",
            )
        if stale_state:
            return RecoveryDecision(RecoveryChoice.REPLAN, "canonical state is stale")
        if recoverable_action_failure:
            return RecoveryDecision(
                RecoveryChoice.ALTERNATE_ACTION,
                "action failed with known non-committed effect",
            )
        return RecoveryDecision(RecoveryChoice.SAFE_STOP, "no justified recovery move")


def _trace_for(
    *,
    diagnosis: str,
    choice: RecoveryChoice,
    local_recovered: bool,
    global_invariant_ok: bool,
    external_effect_known: bool = True,
) -> RecoveryTrace:
    final_outcome = (
        "MIGRATED"
        if local_recovered and not global_invariant_ok
        else "RECOVERED"
        if local_recovered and global_invariant_ok
        else "NOT_RECOVERED"
    )
    steps = (
        RecoveryStep(RecoveryStage.DETECTION, 1, detail="failure detected"),
        RecoveryStep(RecoveryStage.DIAGNOSIS, 2, detail=diagnosis),
        RecoveryStep(RecoveryStage.SELECTION, 3, detail="recovery selected", choice=choice),
        RecoveryStep(RecoveryStage.ADMISSION, 4, detail="system admission evaluated", choice=choice),
        RecoveryStep(RecoveryStage.EXECUTION, 5, detail="recovery executed", choice=choice),
        RecoveryStep(RecoveryStage.VERIFICATION, 6, detail="postcondition checked", outcome=final_outcome),
    )
    return RecoveryTrace(
        steps=steps,
        local_recovered=local_recovered,
        global_invariant_ok=global_invariant_ok,
        external_effect_known=external_effect_known,
    )


def simulate_recovery(*, fault: str) -> RecoveryTrace:
    fault_name = str(fault).upper()
    if fault_name == "STALE_STATE":
        return _trace_for(
            diagnosis="canonical state version is stale",
            choice=RecoveryChoice.REPLAN,
            local_recovered=True,
            global_invariant_ok=True,
        )
    if fault_name == "UNKNOWN_EFFECT":
        return _trace_for(
            diagnosis="external effect status is unknown",
            choice=RecoveryChoice.RECONCILE,
            local_recovered=True,
            global_invariant_ok=True,
        )
    return _trace_for(
        diagnosis=f"unclassified fault: {fault_name}",
        choice=RecoveryChoice.SAFE_STOP,
        local_recovered=False,
        global_invariant_ok=True,
    )


def trajectory(*, local_recovered: bool, global_invariant_ok: bool) -> RecoveryTrace:
    return _trace_for(
        diagnosis="test trajectory",
        choice=RecoveryChoice.REPLAN if local_recovered else RecoveryChoice.SAFE_STOP,
        local_recovered=local_recovered,
        global_invariant_ok=global_invariant_ok,
    )


def failure_migrated(trace: RecoveryTrace) -> bool:
    return bool(trace.local_recovered and not trace.global_invariant_ok)


def classify_recovery_trajectory(trace: RecoveryTrace) -> str:
    if failure_migrated(trace):
        return "MIGRATED"
    if trace.local_recovered and trace.global_invariant_ok:
        return "RECOVERED"
    if not trace.external_effect_known:
        return "UNRESOLVED_EXTERNAL_EFFECT"
    return "NOT_RECOVERED"
