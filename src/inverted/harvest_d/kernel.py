from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import uuid
from typing import Any

from .types import stable_hash


class KernelViolation(RuntimeError):
    pass


class EffectStatus(str, Enum):
    NOT_COMMITTED = "NOT_COMMITTED"
    COMMITTED = "COMMITTED"
    UNKNOWN = "UNKNOWN"


class TransactionStatus(str, Enum):
    PREPARED = "PREPARED"
    CLOSED = "CLOSED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass(frozen=True)
class CanonicalState:
    version: int
    data: dict[str, Any]
    valid: bool = True


@dataclass
class AuthorityLease:
    authority_id: str
    action_hash: str
    remaining: int = 1

    @property
    def consumed(self) -> bool:
        return self.remaining <= 0


@dataclass(frozen=True)
class ProofCarryingAction:
    action_id: str
    payload: dict[str, Any]
    state_version: int
    authority_id: str

    @property
    def action_hash(self) -> str:
        return stable_hash(self.payload)


@dataclass(frozen=True)
class TransactionRecord:
    tx_id: str
    action: ProofCarryingAction
    effect_status: EffectStatus = EffectStatus.NOT_COMMITTED
    status: TransactionStatus = TransactionStatus.PREPARED
    effect_id: str | None = None


class TrustedKernel:
    def __init__(self, state: CanonicalState) -> None:
        self.state = state
        self._authorities: dict[str, AuthorityLease] = {}
        self._transactions: dict[str, TransactionRecord] = {}
        self._committed_effects: set[str] = set()

    def issue_authority(self, payload: dict[str, Any], budget: int = 1) -> AuthorityLease:
        if budget < 1:
            raise KernelViolation("authority budget must be positive")
        authority_id = f"auth-{uuid.uuid4().hex}"
        lease = AuthorityLease(authority_id=authority_id, action_hash=stable_hash(payload), remaining=budget)
        self._authorities[authority_id] = lease
        return lease

    def prepare(self, action: ProofCarryingAction) -> TransactionRecord:
        if not self.state.valid:
            raise KernelViolation("canonical state is invalid")
        if action.state_version != self.state.version:
            raise KernelViolation("stale state version")
        lease = self._authorities.get(action.authority_id)
        if lease is None:
            raise KernelViolation("unknown authority")
        if lease.consumed:
            raise KernelViolation("authority already consumed")
        if lease.action_hash != action.action_hash:
            raise KernelViolation("authority does not bind to canonical action")
        lease.remaining -= 1
        tx_id = f"tx-{uuid.uuid4().hex}"
        tx = TransactionRecord(tx_id=tx_id, action=action)
        self._transactions[tx_id] = tx
        return tx

    def transaction(self, tx_id: str) -> TransactionRecord:
        try:
            return self._transactions[tx_id]
        except KeyError as exc:
            raise KernelViolation(f"unknown transaction {tx_id}") from exc

    def commit_effect(self, tx_id: str, effect_id: str) -> TransactionRecord:
        tx = self.transaction(tx_id)
        if tx.status is not TransactionStatus.PREPARED:
            raise KernelViolation("transaction is not open")
        if tx.effect_status is EffectStatus.UNKNOWN:
            raise KernelViolation("unknown effect must be reconciled")
        if effect_id in self._committed_effects:
            raise KernelViolation("duplicate external effect")
        self._committed_effects.add(effect_id)
        updated = replace(tx, effect_status=EffectStatus.COMMITTED, effect_id=effect_id)
        self._transactions[tx_id] = updated
        return updated

    def mark_effect_unknown(self, tx_id: str) -> TransactionRecord:
        tx = self.transaction(tx_id)
        updated = replace(tx, effect_status=EffectStatus.UNKNOWN)
        self._transactions[tx_id] = updated
        return updated

    def retry(self, tx_id: str) -> None:
        tx = self.transaction(tx_id)
        if tx.effect_status is EffectStatus.UNKNOWN:
            raise KernelViolation("blind retry forbidden while external effect is unknown")
        raise KernelViolation("retry requires an explicit new authorized transition")

    def reconcile(self, tx_id: str, committed: bool, effect_id: str | None = None) -> TransactionRecord:
        tx = self.transaction(tx_id)
        if tx.effect_status is not EffectStatus.UNKNOWN:
            raise KernelViolation("reconciliation requires UNKNOWN effect state")
        if committed:
            if not effect_id:
                raise KernelViolation("committed reconciliation requires effect_id")
            if effect_id in self._committed_effects:
                raise KernelViolation("duplicate external effect")
            self._committed_effects.add(effect_id)
            updated = replace(tx, effect_status=EffectStatus.COMMITTED, effect_id=effect_id)
        else:
            updated = replace(tx, effect_status=EffectStatus.NOT_COMMITTED, effect_id=None)
        self._transactions[tx_id] = updated
        return updated

    def rollback(self, tx_id: str) -> TransactionRecord:
        tx = self.transaction(tx_id)
        if tx.effect_status is EffectStatus.UNKNOWN:
            raise KernelViolation("cannot rollback unknown external effect without reconciliation")
        updated = replace(tx, status=TransactionStatus.ROLLED_BACK)
        self._transactions[tx_id] = updated
        return updated

    def close(self, tx_id: str) -> TransactionRecord:
        tx = self.transaction(tx_id)
        if tx.effect_status is EffectStatus.UNKNOWN:
            raise KernelViolation("cannot close unknown external effect")
        updated = replace(tx, status=TransactionStatus.CLOSED)
        self._transactions[tx_id] = updated
        return updated

    def can_complete(self) -> bool:
        if not self.state.valid:
            return False
        return all(tx.effect_status is not EffectStatus.UNKNOWN and tx.status is not TransactionStatus.PREPARED for tx in self._transactions.values())
