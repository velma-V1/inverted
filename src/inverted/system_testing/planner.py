from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .types import InteractionProbe, MechanismSpec, SystemTestTemplate


class PlannerError(ValueError):
    pass


class ComparisonKind(str, Enum):
    FULL_VS_RAW = "FULL_VS_RAW"
    ISOLATION = "ISOLATION"
    ABLATION = "ABLATION"
    INTERACTION = "INTERACTION"
    FACTORIAL_CORE = "FACTORIAL_CORE"


@dataclass(frozen=True)
class ComparisonCell:
    label: str
    system_id: str
    factors: tuple[str, ...]
    active_mechanisms: tuple[str, ...]


@dataclass(frozen=True)
class ComparisonSpec:
    comparison_id: str
    kind: ComparisonKind
    decision_id: str
    reason: str
    cells: tuple[ComparisonCell, ...]

@dataclass(frozen=True)
class ComparisonPlan:
    system_id: str
    comparisons: tuple[ComparisonSpec, ...]

    @property
    def comparison_count(self) -> int:
        return len(self.comparisons)

    @property
    def condition_count(self) -> int:
        return sum(len(comparison.cells) for comparison in self.comparisons)


def _cell(label: str, system_id: str, factors: Iterable[str], mechanisms: Iterable[str]) -> ComparisonCell:
    return ComparisonCell(
        label=label,
        system_id=system_id,
        factors=tuple(sorted(set(factors))),
        active_mechanisms=tuple(sorted(set(mechanisms))),
    )


def _full_vs_raw(template: SystemTestTemplate, full: tuple[str, ...]) -> ComparisonSpec:
    return ComparisonSpec(
        comparison_id=f"{template.system_id}:FULL_VS_RAW",
        kind=ComparisonKind.FULL_VS_RAW,
        decision_id=template.decision_id,
        reason="Determine whether the complete system improves on the same model raw.",
        cells=(
            _cell("RAW", "RAW", (), ()),
            _cell("FULL", template.system_id, template.factors, full),
        ),
    )

def _isolation(template: SystemTestTemplate, mechanism: MechanismSpec) -> ComparisonSpec:
    return ComparisonSpec(
        comparison_id=f"{template.system_id}:ISOLATE:{mechanism.mechanism_id}",
        kind=ComparisonKind.ISOLATION,
        decision_id=mechanism.decision_id,
        reason=f"Measure {mechanism.mechanism_id} against RAW in isolation.",
        cells=(
            _cell("RAW", "RAW", (), ()),
            _cell(
                f"ONLY_{mechanism.mechanism_id}",
                template.system_id,
                template.factors,
                (mechanism.mechanism_id,),
            ),
        ),
    )


def _ablation(
    template: SystemTestTemplate,
    mechanism: MechanismSpec,
    full: tuple[str, ...],
) -> ComparisonSpec:
    without = tuple(mid for mid in full if mid != mechanism.mechanism_id)
    return ComparisonSpec(
        comparison_id=f"{template.system_id}:ABLATE:{mechanism.mechanism_id}",
        kind=ComparisonKind.ABLATION,
        decision_id=mechanism.decision_id,
        reason=f"Test whether {mechanism.mechanism_id} is necessary inside the full system.",
        cells=(
            _cell(f"WITHOUT_{mechanism.mechanism_id}", template.system_id, template.factors, without),
            _cell("FULL", template.system_id, template.factors, full),
        ),
    )

def _interaction(template: SystemTestTemplate, probe: InteractionProbe) -> ComparisonSpec:
    members = tuple(sorted(probe.members))
    cells = [_cell("RAW", "RAW", (), ())]
    for member in members:
        cells.append(
            _cell(f"ONLY_{member}", template.system_id, template.factors, (member,))
        )
    cells.append(
        _cell("COMBINED", template.system_id, template.factors, members)
    )
    return ComparisonSpec(
        comparison_id=f"{template.system_id}:INTERACTION:{probe.probe_id}",
        kind=ComparisonKind.INTERACTION,
        decision_id=probe.decision_id,
        reason=probe.reason,
        cells=tuple(cells),
    )


def plan_template_comparisons(template: SystemTestTemplate) -> ComparisonPlan:
    if template.system_id == "RAW":
        return ComparisonPlan(system_id="RAW", comparisons=())

    mechanisms = tuple(sorted(template.mechanisms, key=lambda item: item.mechanism_id))
    full = tuple(item.mechanism_id for item in mechanisms)
    comparisons: list[ComparisonSpec] = [_full_vs_raw(template, full)]

    comparisons.extend(
        _isolation(template, mechanism)
        for mechanism in mechanisms
        if mechanism.isolation_required
    )
    comparisons.extend(
        _ablation(template, mechanism, full)
        for mechanism in mechanisms
        if mechanism.ablation_required
    )
    comparisons.extend(
        _interaction(template, probe)
        for probe in sorted(template.interactions, key=lambda item: item.probe_id)
    )
    return ComparisonPlan(system_id=template.system_id, comparisons=tuple(comparisons))


def build_factorial_core(templates: Iterable[SystemTestTemplate]) -> ComparisonSpec:
    by_id = {template.system_id: template for template in templates}
    required = ("RAW", "BRAIN", "INVERTED_SYSTEM", "BRAIN_INVERTED")
    missing = tuple(system_id for system_id in required if system_id not in by_id)
    if missing:
        raise PlannerError(f"missing factorial profile(s): {', '.join(missing)}")

    expected_factors = {
        "RAW": (),
        "BRAIN": ("BRAIN",),
        "INVERTED_SYSTEM": ("INVERTED",),
        "BRAIN_INVERTED": ("BRAIN", "INVERTED"),
    }
    cells: list[ComparisonCell] = []
    for system_id in required:
        template = by_id[system_id]
        factors = tuple(sorted(template.factors))
        if factors != expected_factors[system_id]:
            raise PlannerError(
                f"{system_id} factors must equal {expected_factors[system_id]!r}; got {factors!r}"
            )
        cells.append(
            _cell(system_id, system_id, factors, template.mechanism_ids)
        )

    return ComparisonSpec(
        comparison_id="CORE:BRAIN_X_INVERTED",
        kind=ComparisonKind.FACTORIAL_CORE,
        decision_id="DECIDE-BRAIN-X-INVERTED",
        reason="Measure Brain main effect, INVERTED main effect, and Brain×INVERTED interaction.",
        cells=tuple(cells),
    )