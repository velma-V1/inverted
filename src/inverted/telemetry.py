from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ModelCallRecord:
    call_id: str
    run_id: str
    trial_id: str
    candidate_id: str | None
    role: str
    model: str
    provider: str
    start_ts: str
    end_ts: str
    latency_s: float
    ttft_s: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_tokens: int | None = None
    cached_tokens: int | None = None
    cache_write_tokens: int | None = None
    prompt_eval_duration_s: float | None = None
    eval_duration_s: float | None = None
    load_duration_s: float | None = None
    generated_tokens_per_s: float | None = None
    end_to_end_tokens_per_s: float | None = None
    status_code: int | None = None
    error_class: str | None = None
    error_message: str | None = None
    timeout: bool = False
    retry_number: int = 0
    retry_reason: str | None = None
    finish_reason: str | None = None
    parse_success: bool | None = None
    parse_error: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    cost_usd: float | None = None
    raw_usage: dict[str, Any] = field(default_factory=dict)
    raw_provider_telemetry: dict[str, Any] = field(default_factory=dict)
    prompt: Any = None
    response: Any = None

    def __post_init__(self) -> None:
        if self.generated_tokens_per_s is None and self.output_tokens is not None and self.eval_duration_s and self.eval_duration_s > 0:
            self.generated_tokens_per_s = self.output_tokens / self.eval_duration_s
        if self.end_to_end_tokens_per_s is None and self.output_tokens is not None and self.latency_s > 0:
            self.end_to_end_tokens_per_s = self.output_tokens / self.latency_s

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
