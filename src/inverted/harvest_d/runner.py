from __future__ import annotations

from dataclasses import asdict, dataclass
import uuid

from .cases import HarvestCase, score_response
from .models import ModelAdapter
from .telemetry import SystemInvolvement
from .types import IdentityRegistry, RouteMode


@dataclass(frozen=True)
class TrialResult:
    case_id: str
    family: str
    capability: str
    difficulty: int
    model: str
    physical_model_call_id: str
    route: RouteMode
    semantic_success: bool
    format_valid: bool
    schema_valid: bool
    disposition_correct: bool
    answer_correct: bool
    contract_success: bool
    input_tokens: int
    output_tokens: int
    latency_ms: float
    involvement: SystemInvolvement
    response_text: str

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["route"] = self.route.value
        return value


class ModelTrialRunner:
    def __init__(self, identity_registry: IdentityRegistry | None = None) -> None:
        self.identity_registry = identity_registry or IdentityRegistry()

    def run(
        self,
        case: HarvestCase,
        adapter: ModelAdapter,
        *,
        route: RouteMode,
        involvement: SystemInvolvement,
        system_prompt: str | None = None,
    ) -> TrialResult:
        call_id = f"model-call-{uuid.uuid4().hex}"
        self.identity_registry.register(call_id)
        response = adapter.complete(case.model_prompt(), system=system_prompt)
        score = score_response(case, response.text)
        return TrialResult(
            case.case_id,
            case.family,
            case.capability,
            case.difficulty,
            response.model,
            call_id,
            route,
            score.overall_semantic_correct,
            score.format_valid,
            score.schema_valid,
            score.disposition_correct,
            score.answer_correct,
            score.contract_success,
            response.input_tokens,
            response.output_tokens,
            response.latency_ms,
            involvement,
            response.text,
        )
