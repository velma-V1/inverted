from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class EnvironmentSnapshot:
    persistent_json: str
    fingerprints: dict[str, str]
    redaction_tokens: dict[str, str]


@dataclass(frozen=True)
class RedactionEvent:
    variable_name: str
    token: str
    original_offset: int
    original_length: int
    source: str


@dataclass(frozen=True)
class RedactedBytes:
    persisted_bytes: bytes
    redactions: tuple[RedactionEvent, ...]


class EnvironmentPolicy:
    def __init__(self, *, secret_names: tuple[str, ...], salt: str):
        if not salt:
            raise ValueError("environment fingerprint salt must be non-empty")
        self.secret_names = tuple(dict.fromkeys(secret_names))
        self.salt = salt
    def _fingerprint(self, name: str, value: str) -> str:
        raw = f"{self.salt}\0{name}\0{value}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _token(self, name: str, fingerprint: str) -> str:
        return f"<REDACTED:{name}:{fingerprint[:12]}>"

    def snapshot(self, env: Mapping[str, str]) -> EnvironmentSnapshot:
        fingerprints: dict[str, str] = {}
        tokens: dict[str, str] = {}
        rows: list[dict[str, object]] = []
        secrets = set(self.secret_names)
        for name in sorted(env):
            value = str(env[name])
            fingerprint = self._fingerprint(name, value)
            fingerprints[name] = fingerprint
            secret = name in secrets
            row: dict[str, object] = {
                "name": name, "present": True, "secret": secret, "fingerprint": fingerprint,
            }
            if secret:
                token = self._token(name, fingerprint)
                tokens[name] = token
                row["redaction_token"] = token
            else:
                row["value"] = value
            rows.append(row)
        payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return EnvironmentSnapshot(payload, fingerprints, tokens)

    def redact_bytes(self, data: bytes, env: Mapping[str, str], *, source: str) -> RedactedBytes:
        snapshot = self.snapshot(env)
        output = data
        events: list[RedactionEvent] = []
        for name in self.secret_names:
            value = str(env.get(name, ""))
            if not value:
                continue
            needle = value.encode("utf-8")
            token_text = snapshot.redaction_tokens[name]
            token = token_text.encode("utf-8")
            start = 0
            while True:
                index = output.find(needle, start)
                if index < 0:
                    break
                events.append(RedactionEvent(name, token_text, index, len(needle), source))
                output = output[:index] + token + output[index + len(needle):]
                start = index + len(token)
        return RedactedBytes(output, tuple(events))
