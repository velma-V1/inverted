"""Stable public contracts for the Universal Capability Ratchet replay kernel."""

from .core import (
    FailureFixture,
    Partition,
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
from .query import ReplaySelector, select_failures
from .qwen_replay import QwenReplayAdapter, V2ReplayScorer
from .replay import ReplayAdapter, ReplayCompletion, ReplayExecutor, ReplayPlan
from .replay_store import ReplayStore, ReplayValidation, SupersessionRecord
from .snapshot import build_failure_fixture

__all__ = [
    "FailureFixture",
    "HistoricalSeedResult",
    "Partition",
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
    "V2EvidenceSource",
    "V2ReplayScorer",
    "build_failure_fixture",
    "from_payload",
    "preview_v2_failures",
    "seed_v2_failures",
    "select_failures",
    "to_payload",
]
