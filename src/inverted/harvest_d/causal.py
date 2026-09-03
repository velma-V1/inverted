from __future__ import annotations

from dataclasses import dataclass

from .types import MechanismClass

@dataclass(frozen=True)
class CausalPair:
    state_hash: str
    mechanism: str
    region: str
    target_outcome: float
    sham_outcome: float
    sham_state_hash: str | None = None

    @property
    def valid_same_state(self) -> bool:
        return self.sham_state_hash is None or self.sham_state_hash == self.state_hash

    @property
    def delta(self) -> float:
        return self.target_outcome - self.sham_outcome

def classify_mechanism(pairs: list[CausalPair], margin: float = 0.0) -> MechanismClass:
    valid = [p for p in pairs if p.valid_same_state]
    if not valid or len(valid) != len(pairs):
        return MechanismClass.UNRESOLVED
    deltas = [p.delta for p in valid]
    pos = [d > margin for d in deltas]
    neg = [d < -margin for d in deltas]
    neutral = [abs(d) <= margin for d in deltas]
    if all(pos): return MechanismClass.REQUIRED
    if all(neg): return MechanismClass.HARMFUL
    if all(neutral): return MechanismClass.REDUNDANT
    if any(pos) and not any(neg): return MechanismClass.CONDITIONAL
    return MechanismClass.UNRESOLVED
