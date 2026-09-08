"""Stable public contracts for the Universal Capability Ratchet replay kernel."""

from .boundaries import CapabilityBoundaries, derive_capability_boundaries
from .campaign_snapshot import ReplayFailureSnapshotter
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
from .ollama_retry import OllamaExecutionCapabilities, OllamaRetryAttemptExecutor
from .orchestration import (
    AttemptEvidence,
    AttemptOutcome,
    RetryCampaignOrchestrator,
    RetryIngredient,
)
from .qwen_retry import QwenRetryAttemptExecutor
from .three_model_session import (
    QueuedFailureReplay,
    ThreeModelSessionOrchestrator,
    ThreeModelSessionResult,
)

__all__ = [
    "AttemptEvidence",
    "AttemptOutcome",
    "CapabilityBoundaries",
    "FailureFixture",
    "OllamaExecutionCapabilities",
    "OllamaRetryAttemptExecutor",
    "Partition",
    "PromotionState",
    "QueuedFailureReplay",
    "QwenRetryAttemptExecutor",
    "ReplayFailureSnapshotter",
    "ReplayMode",
    "ReplayRecord",
    "ReplayRecordType",
    "ReplayRequest",
    "ReplayResult",
    "RetryCampaignOrchestrator",
    "RetryIngredient",
    "ThreeModelSessionOrchestrator",
    "ThreeModelSessionResult",
    "derive_capability_boundaries",
    "from_payload",
    "to_payload",
]
