"""Stable public contracts for the Universal Capability Ratchet replay kernel."""

from .autopsy import AutopsyReport, FailureAutopsy
from .causal_core import (
    ArchitectureOwner,
    CausalHypothesis,
    DivergenceClass,
    FirstDivergence,
    HypothesisStatus,
    InterventionDefinition,
    InterventionKind,
    MechanismRole,
)
from .causal_store import CausalEvidenceStore
from .core import (
    FailureFixture,
    MechanismLabel,
    Partition,
    PromotionEvent,
    PromotionState,
    ReplayMode,
    ReplayRecord,
    ReplayRecordType,
    ReplayRequest,
    ReplayResult,
    from_payload,
    to_payload,
)
from .historical import (
    HistoricalSeedResult,
    V2EvidenceSource,
    preview_v2_failures,
    seed_v2_failures,
)
from .interventions import InterventionGenerator, TailoredInterventionGenerator
from .lab import FailureLab, FailureResearchProgram, FailureResearchResult
from .mechanisms import MechanismAssessment, MechanismLocalizer
from .query import ReplaySelector, select_failures
from .qwen_replay import QwenReplayAdapter, V2ReplayScorer
from .replay import ReplayAdapter, ReplayCompletion, ReplayExecutor, ReplayPlan
from .replay_store import ReplayStore, ReplayValidation, SupersessionRecord
from .snapshot import build_failure_fixture
from .tournament import TournamentBranch, TournamentPlan, TournamentPlanner, build_ablations

__all__ = [
    "ArchitectureOwner",
    "AutopsyReport",
    "CausalEvidenceStore",
    "CausalHypothesis",
    "DivergenceClass",
    "FailureAutopsy",
    "FailureFixture",
    "FailureLab",
    "FailureResearchProgram",
    "FailureResearchResult",
    "FirstDivergence",
    "HistoricalSeedResult",
    "HypothesisStatus",
    "InterventionDefinition",
    "InterventionGenerator",
    "InterventionKind",
    "MechanismAssessment",
    "MechanismLabel",
    "MechanismLocalizer",
    "MechanismRole",
    "Partition",
    "PromotionEvent",
    "PromotionState",
    "QwenReplayAdapter",
    "ReplayAdapter",
    "ReplayCompletion",
    "ReplayExecutor",
    "ReplayMode",
    "ReplayPlan",
    "ReplayRecord",
    "ReplayRecordType",
    "ReplayRequest",
    "ReplayResult",
    "ReplaySelector",
    "ReplayStore",
    "ReplayValidation",
    "SupersessionRecord",
    "TailoredInterventionGenerator",
    "TournamentBranch",
    "TournamentPlan",
    "TournamentPlanner",
    "V2EvidenceSource",
    "V2ReplayScorer",
    "build_ablations",
    "build_failure_fixture",
    "from_payload",
    "preview_v2_failures",
    "seed_v2_failures",
    "select_failures",
    "to_payload",
]