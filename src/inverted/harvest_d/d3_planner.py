from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from .cases import HarvestCase
from .d3_config import D3Phase
from .d3_executor import D3CallPlan
from .d3_information import (
    InformationAmount,
    InformationRepresentation,
    InformationTiming,
    PacketPlan,
    build_negative_information_control,
    field_lineage,
    render_information_packet,
)
from .d3_scheduler import ExperimentCandidate
from .d3_types import InformationPacket


_BASE_SYSTEM = (
    "INVERTED D3 controlled measurement. Use only the model-visible task and context supplied in this call. "
    "Return the requested JSON object and do not invent hidden labels or future outcomes."
)

_NEGATIVE_CONTROLS = (
    "STALE_PLAUSIBLE_STATE",
    "TOKEN_MATCHED_IRRELEVANT",
    "CONFLICTING_EVIDENCE",
    "UNTRUSTED_METADATA",
    "REDUNDANT_HISTORY",
    "OVERLOAD",
    "UNNECESSARY_DECOMPOSITION",
    "WRONG_RECOVERY_SUGGESTION",
    "MISLEADING_ROUTE_HINT",
    "POOR_REPRESENTATION",
)

_ORDERINGS = (
    "DEFAULT",
    "SAFETY_STATE_EVIDENCE_FIRST",
    "TASK_OBJECTIVE_FIRST",
    "EVIDENCE_FIRST",
    "SHUFFLED_CONTROL",
)

_AMOUNTS = (
    InformationAmount.MINIMUM,
    InformationAmount.COMPRESSED,
    InformationAmount.MODERATE,
    InformationAmount.FULL,
    InformationAmount.OVERLOADED,
)


def _packet_dict(packet: InformationPacket | None) -> dict[str, object]:
    if packet is None:
        return {
            "packet_id": "RAW-NONE",
            "rendered": "",
            "fields": [],
            "representation": "RAW",
            "timing": "NONE",
            "ordering": "NONE",
            "amount": "NONE",
            "placement": "NONE",
            "control_kind": "RAW",
            "approx_token_count": 0,
            "field_lineage": [],
        }
    row = asdict(packet)
    row["field_lineage"] = field_lineage(packet)
    return row


def _placement(plan: PacketPlan, case_prompt: str, rendered: str) -> tuple[str, str]:
    context = f"<D3_CONTEXT>\n{rendered}\n</D3_CONTEXT>"
    timing = plan.timing
    placement = str(plan.placement).upper()

    if timing is InformationTiming.PROGRESSIVE:
        lines = rendered.splitlines() or [rendered]
        split = max(1, len(lines) // 2)
        first = "\n".join(lines[:split])
        second = "\n".join(lines[split:])
        system = _BASE_SYSTEM + f"\n<D3_CONTEXT_PART_1>\n{first}\n</D3_CONTEXT_PART_1>"
        prompt = case_prompt + f"\n<D3_CONTEXT_PART_2>\n{second}\n</D3_CONTEXT_PART_2>"
        return system, prompt

    if placement == "SYSTEM_CONTEXT":
        return _BASE_SYSTEM + "\n" + context, case_prompt

    if timing is InformationTiming.UPFRONT:
        return _BASE_SYSTEM, context + "\n" + case_prompt
    if timing is InformationTiming.PRE_DECISION:
        return _BASE_SYSTEM, case_prompt + "\n" + context + "\nUse the context immediately before deciding."
    if timing is InformationTiming.JUST_IN_TIME:
        return _BASE_SYSTEM, case_prompt + "\n<JIT_INFORMATION>\n" + rendered + "\n</JIT_INFORMATION>"
    return _BASE_SYSTEM, case_prompt + "\n" + context


def _priority(case: HarvestCase) -> dict[str, float]:
    family = case.family
    return {
        "hard_invariant_uncertainty": 1.0 if family in {"AUTHORITY", "TRANSACTION", "GLOBAL_INTERACTION"} else 0.0,
        "semantic_uncertainty": 1.0,
        "silent_wrong_action_uncertainty": 0.8 if family in {"STATE", "AUTHORITY", "ROUTING"} else 0.2,
        "recovery_uncertainty": 1.0 if family in {"RECOVERY", "TRANSACTION", "GLOBAL_INTERACTION"} else 0.0,
        "interaction_uncertainty": 0.8 if family in {"CONTEXT", "GLOBAL_INTERACTION", "VERIFIER_ORACLE"} else 0.2,
        "model_substitution_uncertainty": 0.8,
        "information_marginal_uncertainty": 0.8,
        "assistance_marginal_uncertainty": 0.8,
        "minimum_support_uncertainty": 0.5,
        "efficiency": 0.5,
    }


def _replay_opportunities() -> tuple[dict[str, str], ...]:
    return tuple(
        {"mechanism_id": f"A{i}", "mode": mode}
        for i in range(1, 12)
        for mode in ("OFF", "TARGET", "SHAM")
    )


@dataclass(frozen=True)
class D3PlannedExperiment:
    experiment_id: str
    phase: D3Phase
    model_key: str
    case: HarvestCase
    arm_kind: str
    packet_plan: PacketPlan | None = None
    information_packet: InformationPacket | None = None
    variant: str = "RAW"
    sealed: bool = False
    zero_call_assistance: tuple[dict[str, str], ...] = ()

    def to_scheduler_candidate(self) -> ExperimentCandidate:
        return ExperimentCandidate(
            candidate_id=self.experiment_id,
            mechanism_id=self.variant,
            sealed=self.sealed,
            **_priority(self.case),
        )

    def to_call_plan(self) -> D3CallPlan:
        packet_row = _packet_dict(self.information_packet)
        if self.information_packet is None or self.arm_kind in {"RAW", "ASSISTANCE"}:
            system = _BASE_SYSTEM
            prompt = self.case.model_prompt()
        else:
            plan = self.packet_plan or PacketPlan.minimum()
            system, prompt = _placement(plan, self.case.model_prompt(), self.information_packet.rendered)
        return D3CallPlan(
            case_id=self.case.case_id,
            prompt=prompt,
            system=system,
            information_packet=packet_row,
            scheduler_event={
                "experiment_id": self.experiment_id,
                "phase": self.phase.value,
                "model_key": self.model_key,
                "arm_kind": self.arm_kind,
                "variant": self.variant,
                "sealed": self.sealed,
                "zero_call_assistance": list(self.zero_call_assistance),
            },
            arm_id=self.arm_kind,
            phase=self.phase.value,
            case=self.case,
        )


class D3ExperimentPlanner:
    """Builds a preregistered candidate frontier without a Cartesian explosion."""

    def __init__(
        self,
        *,
        development_cases: Iterable[HarvestCase],
        fresh_cases: Iterable[HarvestCase],
        sealed_cases: Iterable[HarvestCase],
        model_keys: tuple[str, ...] = ("SMALL_A", "QWEN"),
    ) -> None:
        self.development_cases = tuple(development_cases)
        self.fresh_cases = tuple(fresh_cases)
        self.sealed_cases = tuple(sealed_cases)
        self.model_keys = tuple(model_keys)
        if not self.development_cases or not self.fresh_cases or not self.sealed_cases:
            raise ValueError("D3 planner requires development, fresh, and sealed cases")
        if not self.model_keys:
            raise ValueError("D3 planner requires at least one model key")
        self._by_phase = self._build()
        all_ids = [item.experiment_id for rows in self._by_phase.values() for item in rows]
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("D3 planner generated duplicate experiment identities")

    @staticmethod
    def _packet(case: HarvestCase, plan: PacketPlan) -> InformationPacket:
        return render_information_packet(case, plan)

    def _item(
        self,
        *,
        phase: D3Phase,
        model_key: str,
        case: HarvestCase,
        arm_kind: str,
        variant: str,
        plan: PacketPlan | None = None,
        packet: InformationPacket | None = None,
        sealed: bool = False,
        assistance: bool = False,
    ) -> D3PlannedExperiment:
        safe_variant = variant.replace("/", "-").replace(" ", "_")
        experiment_id = f"{phase.value}:{model_key}:{case.case_id}:{arm_kind}:{safe_variant}"
        return D3PlannedExperiment(
            experiment_id=experiment_id,
            phase=phase,
            model_key=model_key,
            case=case,
            arm_kind=arm_kind,
            packet_plan=plan,
            information_packet=packet,
            variant=variant,
            sealed=sealed,
            zero_call_assistance=_replay_opportunities() if assistance else (),
        )

    def _build(self) -> dict[D3Phase, tuple[D3PlannedExperiment, ...]]:
        rows: dict[D3Phase, list[D3PlannedExperiment]] = {phase: [] for phase in D3Phase}

        # D3.1: raw development plus genuinely fresh-family baseline observations.
        for case in (*self.development_cases, *self.fresh_cases):
            for model_key in self.model_keys:
                rows[D3Phase.BASELINE].append(
                    self._item(
                        phase=D3Phase.BASELINE,
                        model_key=model_key,
                        case=case,
                        arm_kind="RAW",
                        variant="RAW",
                    )
                )

        # D3.2: full information plus one-field-at-a-time omissions. This lets
        # the scheduler estimate information marginal value without a 2^10 sweep.
        for case in self.development_cases:
            for model_key in self.model_keys:
                full_plan = PacketPlan.minimum().replace(amount=InformationAmount.FULL)
                rows[D3Phase.INFORMATION].append(
                    self._item(
                        phase=D3Phase.INFORMATION,
                        model_key=model_key,
                        case=case,
                        arm_kind="INFORMATION",
                        variant="I_ALL",
                        plan=full_plan,
                        packet=self._packet(case, full_plan),
                    )
                )
                for field_id in (f"I{i}" for i in range(1, 11)):
                    omit = full_plan.with_omission(field_id, reason=f"D3_CONTENT_ABLATION:{field_id}")
                    rows[D3Phase.INFORMATION].append(
                        self._item(
                            phase=D3Phase.INFORMATION,
                            model_key=model_key,
                            case=case,
                            arm_kind="INFORMATION",
                            variant=f"WITHOUT_{field_id}",
                            plan=omit,
                            packet=self._packet(case, omit),
                        )
                    )

        # D3.3: orthogonal representation/order/amount/timing screens on a
        # structurally diverse subset, not their Cartesian product.
        rep_cases = self.development_cases[: min(12, len(self.development_cases))]
        for case in rep_cases:
            for model_key in self.model_keys:
                for representation in InformationRepresentation:
                    plan = PacketPlan.minimum().replace(representation=representation)
                    rows[D3Phase.REPRESENTATION].append(
                        self._item(
                            phase=D3Phase.REPRESENTATION,
                            model_key=model_key,
                            case=case,
                            arm_kind="INFORMATION",
                            variant=f"REP_{representation.value}",
                            plan=plan,
                            packet=self._packet(case, plan),
                        )
                    )
                for ordering in _ORDERINGS:
                    plan = PacketPlan.minimum().replace(ordering=ordering)
                    rows[D3Phase.REPRESENTATION].append(
                        self._item(
                            phase=D3Phase.REPRESENTATION,
                            model_key=model_key,
                            case=case,
                            arm_kind="INFORMATION",
                            variant=f"ORDER_{ordering}",
                            plan=plan,
                            packet=self._packet(case, plan),
                        )
                    )
                for amount in _AMOUNTS:
                    plan = PacketPlan.minimum().replace(amount=amount)
                    rows[D3Phase.REPRESENTATION].append(
                        self._item(
                            phase=D3Phase.REPRESENTATION,
                            model_key=model_key,
                            case=case,
                            arm_kind="INFORMATION",
                            variant=f"AMOUNT_{amount.value}",
                            plan=plan,
                            packet=self._packet(case, plan),
                        )
                    )
                for timing in InformationTiming:
                    plan = PacketPlan.minimum().replace(timing=timing)
                    rows[D3Phase.REPRESENTATION].append(
                        self._item(
                            phase=D3Phase.REPRESENTATION,
                            model_key=model_key,
                            case=case,
                            arm_kind="INFORMATION",
                            variant=f"TIMING_{timing.value}",
                            plan=plan,
                            packet=self._packet(case, plan),
                        )
                    )

        # D3.4: raw cognition is physically sampled; A1-A11 are replayed OFF /
        # TARGET / SHAM against that same response whenever causally valid.
        assistance_cases = self.development_cases[: min(16, len(self.development_cases))]
        for case in assistance_cases:
            for model_key in self.model_keys:
                rows[D3Phase.ASSISTANCE].append(
                    self._item(
                        phase=D3Phase.ASSISTANCE,
                        model_key=model_key,
                        case=case,
                        arm_kind="ASSISTANCE",
                        variant="A1_A11_REPLAY_SOURCE",
                        assistance=True,
                    )
                )

        recovery_cases = tuple(
            case
            for case in self.development_cases
            if case.family in {"RECOVERY", "TRANSACTION", "GLOBAL_INTERACTION", "AUTHORITY"}
        )
        for case in recovery_cases:
            for model_key in self.model_keys:
                plan = PacketPlan.minimum().replace(ordering="SAFETY_STATE_EVIDENCE_FIRST")
                rows[D3Phase.RECOVERY].append(
                    self._item(
                        phase=D3Phase.RECOVERY,
                        model_key=model_key,
                        case=case,
                        arm_kind="INFORMATION",
                        variant="RECOVERY_CONTEXT",
                        plan=plan,
                        packet=self._packet(case, plan),
                        assistance=True,
                    )
                )

        combined_cases = self.development_cases[: min(20, len(self.development_cases))]
        for case in combined_cases:
            for model_key in self.model_keys:
                plan = PacketPlan.minimum().replace(
                    ordering="SAFETY_STATE_EVIDENCE_FIRST",
                    representation=InformationRepresentation.MINIMAL_LEDGER,
                )
                rows[D3Phase.COMBINED].append(
                    self._item(
                        phase=D3Phase.COMBINED,
                        model_key=model_key,
                        case=case,
                        arm_kind="INFORMATION_ASSISTANCE",
                        variant="INFO_PLUS_A1_A11",
                        plan=plan,
                        packet=self._packet(case, plan),
                        assistance=True,
                    )
                )

        negative_cases = self.development_cases[: min(12, len(self.development_cases))]
        for case in negative_cases:
            for model_key in self.model_keys:
                base_plan = PacketPlan.minimum()
                base_packet = self._packet(case, base_plan)
                for control in _NEGATIVE_CONTROLS:
                    packet = build_negative_information_control(base_packet, control)
                    rows[D3Phase.NEGATIVE_TRANSFER].append(
                        self._item(
                            phase=D3Phase.NEGATIVE_TRANSFER,
                            model_key=model_key,
                            case=case,
                            arm_kind="INFORMATION",
                            variant=f"NEG_{control}",
                            plan=base_plan,
                            packet=packet,
                        )
                    )

        # D3.8 is physically and logically disjoint from development. Keep the
        # candidate set <= protected 100-call reservoir with 2 sealed cases per
        # family under the production defaults (22 cases * 2 models * 2 arms=88).
        for case in self.sealed_cases:
            for model_key in self.model_keys:
                rows[D3Phase.SEALED_CONFIRMATION].append(
                    self._item(
                        phase=D3Phase.SEALED_CONFIRMATION,
                        model_key=model_key,
                        case=case,
                        arm_kind="RAW",
                        variant="SEALED_RAW",
                        sealed=True,
                    )
                )
                plan = PacketPlan.minimum().replace(ordering="SAFETY_STATE_EVIDENCE_FIRST")
                rows[D3Phase.SEALED_CONFIRMATION].append(
                    self._item(
                        phase=D3Phase.SEALED_CONFIRMATION,
                        model_key=model_key,
                        case=case,
                        arm_kind="INFORMATION_ASSISTANCE",
                        variant="SEALED_SUPPORTED",
                        plan=plan,
                        packet=self._packet(case, plan),
                        sealed=True,
                        assistance=True,
                    )
                )

        return {phase: tuple(items) for phase, items in rows.items()}

    def candidates_for_phase(self, phase: D3Phase) -> tuple[D3PlannedExperiment, ...]:
        return self._by_phase[phase]

    def candidate_count(self) -> int:
        return sum(len(rows) for rows in self._by_phase.values())
