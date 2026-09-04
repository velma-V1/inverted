from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Iterable


class EvidenceTier(str, Enum):
    DETERMINISTIC = "E0_DETERMINISTIC"
    HISTORICAL_PRIOR = "E1_HISTORICAL_PRIOR"
    FRESH_DEVELOPMENT = "E2_FRESH_DEVELOPMENT"
    FRESH_SEALED = "E3_FRESH_SEALED"
    NOVELTY_EDGE = "E4_NOVELTY_EDGE"


class PriorValueClass(str, Enum):
    STRONG_CAUSAL_PRIOR = "STRONG_CAUSAL_PRIOR"
    USEFUL_DIRECTIONAL_PRIOR = "USEFUL_DIRECTIONAL_PRIOR"
    FAILURE_ATLAS_PRIOR = "FAILURE_ATLAS_PRIOR"
    COST_RUNTIME_PRIOR = "COST_RUNTIME_PRIOR"
    INSTRUMENTATION_WARNING = "INSTRUMENTATION_WARNING"
    NONTRANSFERABLE = "NONTRANSFERABLE"


@dataclass(frozen=True)
class PriorEvidenceRecord:
    evidence_source_id: str
    source_path: str
    evidence_tier: EvidenceTier
    sample_size: int
    causal_strength: PriorValueClass
    reusable_for: tuple[str, ...]
    forbidden_for: tuple[str, ...]
    scheduler_prior_weight: float
    reason: str
    present: bool = True
    source_sha256: str | None = None
    families: tuple[str, ...] = ()
    instrumentation_complete: bool | None = None
    freshness_compatible: bool = False

    def __post_init__(self) -> None:
        if self.sample_size < 0:
            raise ValueError("prior sample size must be non-negative")
        if not 0.0 <= self.scheduler_prior_weight <= 1.0:
            raise ValueError("scheduler prior weight must be between zero and one")
        if self.evidence_tier is not EvidenceTier.HISTORICAL_PRIOR:
            raise ValueError("prior evidence records must remain historical-prior tier")
        if self.freshness_compatible:
            raise ValueError("historical priors cannot be marked freshness-compatible")
        forbidden = set(self.forbidden_for)
        required_forbidden = {"fresh_confirmation", "sealed_confirmation", "global_optimum"}
        if not required_forbidden <= forbidden:
            raise ValueError("historical prior must forbid fresh/sealed/global-optimum promotion")

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence_source_id": self.evidence_source_id,
            "source_path": self.source_path,
            "evidence_tier": self.evidence_tier.value,
            "sample_size": self.sample_size,
            "causal_strength": self.causal_strength.value,
            "reusable_for": list(self.reusable_for),
            "forbidden_for": list(self.forbidden_for),
            "scheduler_prior_weight": self.scheduler_prior_weight,
            "reason": self.reason,
            "present": self.present,
            "source_sha256": self.source_sha256,
            "families": list(self.families),
            "instrumentation_complete": self.instrumentation_complete,
            "freshness_compatible": self.freshness_compatible,
        }


_FORBIDDEN = ("fresh_confirmation", "sealed_confirmation", "global_optimum")

_EXPECTED_CASE_PRIORS: tuple[tuple[str, str, PriorValueClass, float, str], ...] = (
    (
        "D2_QWEN_GAIN_V1",
        "cases/harvest_d/d2-qwen-gain-v1.jsonl",
        PriorValueClass.USEFUL_DIRECTIONAL_PRIOR,
        0.45,
        "small matched Qwen-gain slice; useful for residual-family and scheduler prioritization",
    ),
    (
        "D2_NEITHER_9B_V1",
        "cases/harvest_d/d2-neither-9b-v1.jsonl",
        PriorValueClass.FAILURE_ATLAS_PRIOR,
        0.40,
        "persistent residual slice; useful for hard-family and novelty prioritization",
    ),
    (
        "D2_RESIDUAL_3B_TO_9B_V1",
        "cases/harvest_d/d2-residual-3b-to-9b-v1.jsonl",
        PriorValueClass.USEFUL_DIRECTIONAL_PRIOR,
        0.35,
        "small model-substitution residual slice; directional only",
    ),
    (
        "D2_RESIDUAL_F7_002_V1",
        "cases/harvest_d/d2-residual-f7-002-v1.jsonl",
        PriorValueClass.FAILURE_ATLAS_PRIOR,
        0.25,
        "single-edge residual is retained for edge-case/failure-atlas value, never effect-size inference",
    ),
    (
        "D2_SMALL_A_SEED_V1",
        "cases/harvest_d/d2-small-a-seed-v1.jsonl",
        PriorValueClass.USEFUL_DIRECTIONAL_PRIOR,
        0.35,
        "small-model capability seed; useful for family prioritization",
    ),
    (
        "D2_SMALL_A_SEED_V2",
        "cases/harvest_d/d2-small-a-seed-v2.jsonl",
        PriorValueClass.USEFUL_DIRECTIONAL_PRIOR,
        0.40,
        "corrected/expanded small-model seed; useful for family prioritization",
    ),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonl_summary(path: Path) -> tuple[int, tuple[str, ...]]:
    sample_size = 0
    families: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            sample_size += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            family = row.get("family")
            if family:
                families.add(str(family))
    return sample_size, tuple(sorted(families))


def _record_for_expected(
    repo_root: Path,
    evidence_source_id: str,
    relative_path: str,
    value_class: PriorValueClass,
    prior_weight: float,
    reason: str,
) -> PriorEvidenceRecord:
    path = repo_root / relative_path
    if not path.exists():
        return PriorEvidenceRecord(
            evidence_source_id=evidence_source_id,
            source_path=relative_path,
            evidence_tier=EvidenceTier.HISTORICAL_PRIOR,
            sample_size=0,
            causal_strength=PriorValueClass.NONTRANSFERABLE,
            reusable_for=("availability_audit",),
            forbidden_for=_FORBIDDEN,
            scheduler_prior_weight=0.0,
            reason=f"expected historical source unavailable at inventory time: {relative_path}",
            present=False,
            instrumentation_complete=None,
        )
    sample_size, families = _jsonl_summary(path)
    return PriorEvidenceRecord(
        evidence_source_id=evidence_source_id,
        source_path=relative_path,
        evidence_tier=EvidenceTier.HISTORICAL_PRIOR,
        sample_size=sample_size,
        causal_strength=value_class,
        reusable_for=("scheduler_prior", "failure_strata", "sentinel_selection", "coverage_gap_detection"),
        forbidden_for=_FORBIDDEN,
        scheduler_prior_weight=prior_weight,
        reason=reason,
        present=True,
        source_sha256=_sha256(path),
        families=families,
        instrumentation_complete=None,
    )


def _dynamic_case_records(repo_root: Path, known_paths: set[str]) -> list[PriorEvidenceRecord]:
    root = repo_root / "cases" / "harvest_d"
    if not root.exists():
        return []
    records: list[PriorEvidenceRecord] = []
    for path in sorted(root.glob("*.jsonl")):
        relative = path.relative_to(repo_root).as_posix()
        if relative in known_paths:
            continue
        sample_size, families = _jsonl_summary(path)
        source_id = "HARVEST_D_CASE_" + path.stem.upper().replace("-", "_")
        records.append(
            PriorEvidenceRecord(
                evidence_source_id=source_id,
                source_path=relative,
                evidence_tier=EvidenceTier.HISTORICAL_PRIOR,
                sample_size=sample_size,
                causal_strength=PriorValueClass.FAILURE_ATLAS_PRIOR,
                reusable_for=("scheduler_prior", "failure_strata", "sentinel_selection", "coverage_gap_detection"),
                forbidden_for=_FORBIDDEN,
                scheduler_prior_weight=0.20 if sample_size else 0.0,
                reason="additional committed Harvest D case slice retained for failure-atlas and challenge-selection value",
                present=True,
                source_sha256=_sha256(path),
                families=families,
                instrumentation_complete=None,
            )
        )
    return records


def inventory_prior_evidence(repo_root: str | Path) -> tuple[PriorEvidenceRecord, ...]:
    root = Path(repo_root)
    records = [
        _record_for_expected(root, source_id, path, value_class, weight, reason)
        for source_id, path, value_class, weight, reason in _EXPECTED_CASE_PRIORS
    ]
    known_paths = {path for _, path, _, _, _ in _EXPECTED_CASE_PRIORS}
    records.extend(_dynamic_case_records(root, known_paths))
    return tuple(sorted(records, key=lambda row: (row.evidence_source_id, row.source_path)))


def write_prior_evidence_ledger(
    output_root: str | Path,
    records: Iterable[PriorEvidenceRecord],
) -> Path:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "closure_prior_evidence_ledger.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
    return path
