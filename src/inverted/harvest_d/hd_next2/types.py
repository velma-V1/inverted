from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StageId(str, Enum):
    A0 = "2A-0"
    A1 = "2A-1"
    A2 = "2A-2"
    A3 = "2A-3"
    A4 = "2A-4"
    A5 = "2A-5"
    A6 = "2A-6"
    A7 = "2A-7"
    A8 = "2A-8"
    A9 = "2A-9"
    A10 = "2A-10"


class DeliveryMode(str, Enum):
    STATIC = "STATIC"
    PROGRESSIVE = "PROGRESSIVE"


class RecurrenceMode(str, Enum):
    NONE = "NONE"
    REPEAT_EXACT = "REPEAT_EXACT"
    REPEAT_REFRESHED = "REPEAT_REFRESHED"
    REANCHOR_COMPRESSED = "REANCHOR_COMPRESSED"


class CoverageState(str, Enum):
    UNTESTED = "UNTESTED"
    PARTIAL = "PARTIAL"
    NOISY = "NOISY"
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    CONDITIONAL = "CONDITIONAL"
    ENABLER = "ENABLER"
    RECURRENT = "RECURRENT"
    RECOVERY_ONLY = "RECOVERY_ONLY"
    DORMANT = "DORMANT"
    HARMFUL = "HARMFUL"


@dataclass(frozen=True)
class IngredientLayer:
    ingredient_id: str
    formulation_id: str
    dose_id: str
    recurrence: RecurrenceMode = RecurrenceMode.NONE
    spacing: str = "ADJACENT"
    timing: str = "UPFRONT"
    placement: str = "TASK_CONTEXT"
    trigger: str = "ALWAYS"


@dataclass(frozen=True)
class TreatmentPath:
    treatment_id: str
    delivery_mode: DeliveryMode
    layers: tuple[IngredientLayer, ...]


@dataclass(frozen=True)
class StagePlan:
    campaign_id: str
    stage: StageId
    units: tuple[object, ...]
    forecast_combined_actions: int
