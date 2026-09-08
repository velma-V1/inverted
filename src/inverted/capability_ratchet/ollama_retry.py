"""Capability-aware Ollama execution without duplicating the Test1B-v3 evidence path.

The proven Qwen retry executor owns retry construction, scoring, telemetry, runtime
failure normalization, and AttemptEvidence creation. This module narrows only the
runtime-control surface that differs between Ollama model families.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inverted.universal_tuning.core import Profile
from inverted.universal_tuning.qwen_ollama import QwenOllamaAdapter

from .orchestration import AttemptContext, AttemptOutcome
from .qwen_retry import QwenRetryAttemptExecutor


_THINKING_MODES = frozenset({"NONE", "OLLAMA"})


@dataclass(frozen=True)
class OllamaExecutionCapabilities:
    """Runtime controls that are proven safe to expose to one Ollama model."""

    thinking_mode: str = "NONE"

    def __post_init__(self) -> None:
        if not isinstance(self.thinking_mode, str):
            raise TypeError("thinking_mode must be a string")
        mode = self.thinking_mode.strip().upper()
        if mode not in _THINKING_MODES:
            raise ValueError(
                "thinking_mode must be one of: " + ", ".join(sorted(_THINKING_MODES))
            )
        object.__setattr__(self, "thinking_mode", mode)

    @property
    def supports_thinking(self) -> bool:
        return self.thinking_mode == "OLLAMA"


class OllamaRetryAttemptExecutor(QwenRetryAttemptExecutor):
    """Run any compatible Ollama model through the canonical retry/evidence kernel.

    ``thinking_mode='OLLAMA'`` preserves the exact bounded two-stage Qwen behavior.
    ``thinking_mode='NONE'`` forbids positive thinking budgets and omits the Ollama
    ``think`` request key entirely, so direct-only models are not sent an unproven
    model-specific control.
    """

    def __init__(
        self,
        *,
        adapter: QwenOllamaAdapter,
        base_profile: Profile,
        seed: int,
        capabilities: OllamaExecutionCapabilities,
    ) -> None:
        if not isinstance(capabilities, OllamaExecutionCapabilities):
            raise TypeError("capabilities must be OllamaExecutionCapabilities")
        super().__init__(adapter=adapter, base_profile=base_profile, seed=seed)
        self._capabilities = capabilities

    def _request(
        self,
        *,
        context: AttemptContext,
        profile: Profile,
        messages: list[dict[str, Any]],
        think: bool,
        num_predict: int,
        thinking_phase: bool,
    ) -> dict[str, Any]:
        payload = super()._request(
            context=context,
            profile=profile,
            messages=messages,
            think=think,
            num_predict=num_predict,
            thinking_phase=thinking_phase,
        )
        if self._capabilities.thinking_mode == "NONE":
            payload.pop("think", None)
        return payload

    def __call__(self, context: AttemptContext) -> AttemptOutcome:
        if not isinstance(context, AttemptContext):
            return super().__call__(context)
        profile = self._effective_profile(context)
        if profile.thinking and not self._capabilities.supports_thinking:
            raise ValueError(
                "positive thinking budget requires Ollama thinking capability"
            )
        return super().__call__(context)
