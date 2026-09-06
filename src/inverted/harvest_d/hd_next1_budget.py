from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HDNext1BudgetState:
    max_inference_seconds: float
    total_cap: int = 672
    model_caps: dict[str, int] = field(default_factory=lambda: {"SMALL_A": 576, "QWEN": 96})
    qwen_pool_caps: dict[str, int] = field(default_factory=lambda: {"calibration": 12, "development": 21, "confirmation": 63})
    total_used: int = 0
    model_used: dict[str, int] = field(default_factory=lambda: {"SMALL_A": 0, "QWEN": 0})
    qwen_pool_used: dict[str, int] = field(default_factory=lambda: {"calibration": 0, "development": 0, "confirmation": 0})
    inference_seconds_reserved: float = 0.0
    system_only_operations: int = 0

    @classmethod
    def default(cls, *, max_inference_seconds: float) -> "HDNext1BudgetState":
        if max_inference_seconds <= 0:
            raise ValueError("max inference seconds must be positive")
        return cls(float(max_inference_seconds))

    def remaining(self, model_key: str, pool: str) -> int:
        if model_key not in self.model_caps:
            raise ValueError("unknown model key")
        model_remaining = max(0, self.model_caps[model_key] - self.model_used[model_key])
        total_remaining = max(0, self.total_cap - self.total_used)
        if model_key == "QWEN":
            if pool not in self.qwen_pool_caps:
                raise ValueError("unknown QWEN pool")
            return min(total_remaining, model_remaining, max(0, self.qwen_pool_caps[pool] - self.qwen_pool_used[pool]))
        return min(total_remaining, model_remaining)

    def reserve(self, model_key: str, pool: str, *, expected_seconds: float) -> None:
        if expected_seconds <= 0:
            raise ValueError("model call must reserve positive inference time")
        if self.remaining(model_key, pool) < 1:
            raise ValueError(f"{model_key} {pool} budget exhausted")
        if self.inference_seconds_reserved + expected_seconds > self.max_inference_seconds:
            raise ValueError("inference-time budget exhausted")
        self.total_used += 1
        self.model_used[model_key] += 1
        if model_key == "QWEN":
            self.qwen_pool_used[pool] += 1
        self.inference_seconds_reserved += float(expected_seconds)

    def reconcile(self, model_key: str, pool: str, *, expected_seconds: float, actual_seconds: float) -> None:
        if expected_seconds <= 0 or actual_seconds < 0:
            raise ValueError("invalid inference-time reconciliation")
        self.inference_seconds_reserved += float(actual_seconds) - float(expected_seconds)
        if self.inference_seconds_reserved > self.max_inference_seconds + 1e-9:
            raise ValueError("actual inference time exceeded frozen budget")

    def record_system_only_operation(self, count: int = 1) -> None:
        if count < 0:
            raise ValueError("system-only operation count must be non-negative")
        self.system_only_operations += int(count)

    def to_dict(self) -> dict[str, object]:
        return {
            "total_cap": self.total_cap,
            "model_caps": dict(self.model_caps),
            "qwen_pool_caps": dict(self.qwen_pool_caps),
            "total_used": self.total_used,
            "model_used": dict(self.model_used),
            "qwen_pool_used": dict(self.qwen_pool_used),
            "inference_seconds_reserved": self.inference_seconds_reserved,
            "max_inference_seconds": self.max_inference_seconds,
            "system_only_operations": self.system_only_operations,
        }
