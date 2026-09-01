from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_int(*parts: Any) -> int:
    text = "|".join(json.dumps(part, sort_keys=True, default=str) for part in parts)
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def stable_id(prefix: str, *parts: Any, length: int = 16) -> str:
    text = "|".join(json.dumps(part, sort_keys=True, default=str) for part in parts)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}-{digest}"


def json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def flatten_scalars(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key in sorted(value):
            child = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(flatten_scalars(value[key], child))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            child = f"{prefix}[{index}]"
            rows.extend(flatten_scalars(item, child))
    else:
        rows.append((prefix, value))
    return rows
