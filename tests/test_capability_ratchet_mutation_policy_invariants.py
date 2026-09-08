from __future__ import annotations

import pytest

from inverted.capability_ratchet.mutation_core import MutationPolicy


def test_stage6_policy_cannot_relax_protected_negative_transfer_veto() -> None:
    with pytest.raises(ValueError, match="protected"):
        MutationPolicy(max_protected_failures=1)
