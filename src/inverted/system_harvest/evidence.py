from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def content_hash(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


@dataclass(frozen=True)
class RawEvent:
    event_id: str
    campaign_id: str
    system_id: str
    example_id: str
    attempt_id: str
    event_type: str
    ordinal: int
    payload: Any
    parent_ids: tuple[str, ...]
    source_version: str
    content_sha256: str
    redactions: tuple[str, ...] = ()


def make_raw_event(*, campaign_id: str, system_id: str, example_id: str, attempt_id: str,
                   event_type: str, ordinal: int, payload: Any, parent_ids: tuple[str, ...],
                   source_version: str, redactions: tuple[str, ...] = ()) -> RawEvent:
    digest = content_hash(payload)
    identity = f"{campaign_id}|{system_id}|{example_id}|{attempt_id}|{event_type}|{ordinal}|{digest}"
    event_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return RawEvent(event_id, campaign_id, system_id, example_id, attempt_id, event_type,
                    ordinal, payload, tuple(parent_ids), source_version, digest, tuple(redactions))


def verify_event(event: RawEvent) -> bool:
    return content_hash(event.payload) == event.content_sha256
