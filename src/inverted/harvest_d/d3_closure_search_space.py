from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable


@dataclass(frozen=True)
class PrimarySearchSpace:
    content_fields: tuple[str, ...]
    representations: tuple[str, ...]
    orderings: tuple[str, ...]
    amounts: tuple[str, ...]
    timings: tuple[str, ...]
    placements: tuple[str, ...]
    assistance_factors: tuple[str, ...]

    @property
    def raw_theoretical_candidate_count(self) -> int:
        nonempty_content_subsets = (2 ** len(self.content_fields)) - 1
        assistance_combinations = 2 ** len(self.assistance_factors)
        return (
            nonempty_content_subsets
            * len(self.representations)
            * len(self.orderings)
            * len(self.amounts)
            * len(self.timings)
            * len(self.placements)
            * assistance_combinations
        )

    def factor_levels(self) -> dict[str, tuple[str, ...]]:
        factors: dict[str, tuple[str, ...]] = {}
        for field_id in self.content_fields:
            factors[field_id] = ("OFF", "ON")
        factors["representation"] = self.representations
        factors["ordering"] = self.orderings
        factors["amount"] = self.amounts
        factors["timing"] = self.timings
        factors["placement"] = self.placements
        for mechanism in self.assistance_factors:
            factors[mechanism] = ("OFF", "TARGET")
        return factors

    def to_manifest(self) -> dict[str, object]:
        return {
            "content_fields": list(self.content_fields),
            "representations": list(self.representations),
            "orderings": list(self.orderings),
            "amounts": list(self.amounts),
            "timings": list(self.timings),
            "placements": list(self.placements),
            "assistance_factors": list(self.assistance_factors),
            "raw_theoretical_candidate_count": self.raw_theoretical_candidate_count,
            "factor_cardinalities": {key: len(value) for key, value in self.factor_levels().items()},
        }


def build_primary_search_space() -> PrimarySearchSpace:
    return PrimarySearchSpace(
        content_fields=tuple(f"I{i}" for i in range(1, 11)),
        representations=(
            "RAW_PROSE",
            "TYPED_FIELDS",
            "STRICT_JSON",
            "DECISION_TABLE",
            "PRIORITY_BLOCK",
            "EXPLICIT_ALTERNATIVES",
            "DECOMPOSITION",
            "MINIMAL_LEDGER",
            "COMPRESSED_SUMMARY",
            "ADMISSIBLE_ACTION_MATRIX",
        ),
        orderings=(
            "DEFAULT",
            "TASK_OBJECTIVE_FIRST",
            "STATE_FIRST",
            "EVIDENCE_FIRST",
            "SAFETY_STATE_EVIDENCE_FIRST",
            "SHUFFLED_CONTROL",
        ),
        amounts=("MINIMUM", "COMPRESSED", "MODERATE", "FULL", "OVERLOADED"),
        timings=("UPFRONT", "PRE_DECISION", "JUST_IN_TIME", "PROGRESSIVE"),
        placements=("TASK_CONTEXT", "SYSTEM_CONTEXT", "MIXED_CONTEXT"),
        assistance_factors=("A1", "A2", "A3", "A4"),
    )


def _stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def treatment_equivalence_key(
    *,
    semantic_field_hash: str,
    rendered_hash: str,
    system_message_hash: str,
    user_message_hash: str,
    field_order: Iterable[str],
    assistance_hash: str,
) -> str:
    """Identity of the actual model-visible treatment, independent of labels.

    Two nominal experiment labels are one treatment when every model-visible
    semantic/rendering/delivery dimension is identical. This intentionally does
    not include arm/variant names.
    """

    return _stable_hash(
        {
            "semantic_field_hash": semantic_field_hash,
            "rendered_hash": rendered_hash,
            "system_message_hash": system_message_hash,
            "user_message_hash": user_message_hash,
            "field_order": list(field_order),
            "assistance_hash": assistance_hash,
        }
    )


def content_subset_count(field_count: int) -> int:
    if field_count < 1:
        return 0
    return (2 ** field_count) - 1
