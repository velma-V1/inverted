"""High-value assistant capability and trust experiments.

This package is intentionally additive and independent of the original
architecture benchmark. Existing benchmark semantics are never imported as
mutable state or rewritten by these experiments.
"""

from __future__ import annotations

TEST_CALL_CAPS = {
    "long_horizon": 1152,
    "evidence_trust": 1080,
    "authority": 1152,
    "ground_truth_isolation": 1080,
}

TEST_NAMES = tuple(TEST_CALL_CAPS)
ARMS = ("DIRECT", "CHECKED", "INVERTED")

__all__ = ["TEST_CALL_CAPS", "TEST_NAMES", "ARMS"]
