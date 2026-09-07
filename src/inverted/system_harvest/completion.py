from __future__ import annotations

from dataclasses import dataclass

from .coverage import CoverageLedger


_TERMINAL_EXAMPLES = {"PASS", "RECOVERED_BY_ESCALATION"}


@dataclass(frozen=True)
class SystemCompletionReport:
    complete: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class CampaignCompletionReport:
    complete: bool
    blockers: tuple[str, ...]


def evaluate_system_completion(ledger: CoverageLedger, example_statuses: tuple[str, ...],
                               present_channels: tuple[str, ...], required_channels: tuple[str, ...],
                               manifests_verified: bool, mechanism_records_complete: bool,
                               escalation_capsules_verified: bool) -> SystemCompletionReport:
    blockers: list[str] = []
    if ledger.is_open:
        blockers.append("coverage ledger contains unresolved items")
    if not ledger.future_query_ready:
        blockers.append("future-query survivability probe missing or failed")
    nonterminal = [status for status in example_statuses if status not in _TERMINAL_EXAMPLES]
    if not example_statuses or nonterminal:
        blockers.append(f"nonterminal examples: {nonterminal or 'none recorded'}")
    missing = sorted(set(required_channels) - set(present_channels))
    if missing:
        blockers.append("missing evidence channels: " + ", ".join(missing))
    if not manifests_verified:
        blockers.append("evidence manifests not verified")
    if not mechanism_records_complete:
        blockers.append("mechanism extraction records incomplete")
    if "RECOVERED_BY_ESCALATION" in example_statuses and not escalation_capsules_verified:
        blockers.append("escalation capsule chain not verified")
    return SystemCompletionReport(not blockers, tuple(blockers))


def evaluate_campaign_completion(expected_systems: tuple[str, ...],
                                 reports: dict[str, SystemCompletionReport],
                                 cross_manifest_verified: bool) -> CampaignCompletionReport:
    blockers: list[str] = []
    missing = [system for system in expected_systems if system not in reports]
    extra = [system for system in reports if system not in expected_systems]
    if missing:
        blockers.append("missing system reports: " + ", ".join(missing))
    if extra:
        blockers.append("unexpected system reports: " + ", ".join(extra))
    incomplete = [system for system in expected_systems if system in reports and not reports[system].complete]
    if incomplete:
        blockers.append("incomplete systems: " + ", ".join(incomplete))
    if not cross_manifest_verified:
        blockers.append("cross-system manifest not verified")
    return CampaignCompletionReport(not blockers, tuple(blockers))
