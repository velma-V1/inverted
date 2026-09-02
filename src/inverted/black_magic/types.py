from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


def json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def stable_hash(*parts: Any) -> str:
    payload = json.dumps(json_safe(parts), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: Any, length: int = 16) -> str:
    return f"{prefix}-{stable_hash(*parts)[:int(length)]}"


def stable_int(*parts: Any) -> int:
    return int(stable_hash(*parts)[:16], 16)
