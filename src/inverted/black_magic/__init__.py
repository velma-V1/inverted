"""Additive causal evidence and architecture-discovery experiments."""

from __future__ import annotations

BASELINE_SHA = "035c2190403c506330b6b54fa244ce35a62f26bf"
ARMS = ("DIRECT", "CHECKED", "INVERTED")
HARVEST_CAPS = {
    "decision_harvest": 1200,
    "epistemic_harvest": 1200,
    "action_harvest": 1200,
}
TEST5_CAP = 2700
TEST6_CAP = 2700

__all__ = ["BASELINE_SHA", "ARMS", "HARVEST_CAPS", "TEST5_CAP", "TEST6_CAP"]
