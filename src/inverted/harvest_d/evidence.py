from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .types import ClaimState, DuplicateIdentityError, IdentityRegistry


class EvidenceIntegrityError(ValueError):
    pass


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    contaminated: bool = False
    diagnostic: bool = False
    physical_call_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceClaim:
    claim_id: str
    state: ClaimState
    source_ids: tuple[str, ...]
    statement: str = ""


@dataclass(frozen=True)
class ReadinessQuestion:
    question_id: str
    supporting: tuple[str, ...] = ()
    contradicting: tuple[str, ...] = ()
    missing_discriminator: str = ""
    target_stage: str = ""


class EvidenceLedger:
    def __init__(self) -> None:
        self.sources: dict[str, EvidenceSource] = {}
        self.claims: dict[str, EvidenceClaim] = {}
        self._physical_ids = IdentityRegistry()

    def add_source(self, source: EvidenceSource) -> None:
        if not source.source_id or source.source_id in self.sources:
            raise EvidenceIntegrityError(f"invalid or duplicate source_id: {source.source_id}")
        try:
            for call_id in source.physical_call_ids:
                self._physical_ids.register(call_id)
        except DuplicateIdentityError as exc:
            raise EvidenceIntegrityError(f"duplicate physical model call identity: {exc}") from exc
        self.sources[source.source_id] = source

    def add_claim(self, claim: EvidenceClaim) -> None:
        if claim.claim_id in self.claims:
            raise EvidenceIntegrityError(f"duplicate claim_id: {claim.claim_id}")
        if not claim.source_ids:
            raise EvidenceIntegrityError("claim requires at least one source")
        missing = [sid for sid in claim.source_ids if sid not in self.sources]
        if missing:
            raise EvidenceIntegrityError(f"unknown evidence sources: {missing}")
        weak = [self.sources[sid] for sid in claim.source_ids if self.sources[sid].contaminated or self.sources[sid].diagnostic]
        if weak and claim.state not in {ClaimState.OBSERVED, ClaimState.CONTRADICTED}:
            raise EvidenceIntegrityError("contaminated/diagnostic evidence cannot support promotion beyond OBSERVED")
        self.claims[claim.claim_id] = claim

    def source_quality(self, source_ids: Iterable[str]) -> tuple[bool, bool]:
        selected = [self.sources[sid] for sid in source_ids]
        return any(x.contaminated for x in selected), any(x.diagnostic for x in selected)
