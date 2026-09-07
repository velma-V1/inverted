from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import yaml


REQUIRED_TRUE_POLICIES = {
    "source_output_is_hypothesis",
    "causal_replay_required_for_behavior_promotion",
    "fresh_transfer_required_for_behavior_promotion",
}


@dataclass(frozen=True)
class HarvestSource:
    source_id: str
    kind: str
    target: str
    url: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class HarvestCatalog:
    version: int
    policy: dict[str, object]
    sources: tuple[HarvestSource, ...]
    secondary_sources: tuple[HarvestSource, ...]
    excluded_for_now: tuple[dict[str, str], ...]

    def get(self, source_id: str) -> HarvestSource:
        for source in (*self.sources, *self.secondary_sources):
            if source.source_id == source_id:
                return source
        raise KeyError(source_id)


def _validate_url(url: str | None) -> None:
    if not url:
        return
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("source url must use https")
    if parsed.username or parsed.password:
        raise ValueError("source url must not contain credentials")


def _parse_source(row: dict, section: str) -> HarvestSource:
    source_id = str(row.get("id", "")).strip()
    kind = str(row.get("kind", "")).strip()
    target = str(row.get("target", "")).strip()
    if not source_id:
        raise ValueError(f"{section} source missing id")
    if not kind:
        raise ValueError(f"{source_id} missing kind")
    if not target:
        raise ValueError(f"{source_id} missing target")
    url = row.get("url")
    _validate_url(url)
    metadata = {k: v for k, v in row.items() if k not in {"id", "kind", "target", "url"}}
    return HarvestSource(source_id, kind, target, url, metadata)


def load_harvest_catalog(path: Path) -> HarvestCatalog:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if payload.get("version") != 1:
        raise ValueError("unsupported harvest catalog version")

    policy = dict(payload.get("policy") or {})
    for key in REQUIRED_TRUE_POLICIES:
        if policy.get(key) is not True:
            raise ValueError(f"required harvest policy not enabled: {key}")

    sources = tuple(_parse_source(row, "primary") for row in payload.get("sources", []))
    secondary = tuple(_parse_source(row, "secondary") for row in payload.get("secondary_sources", []))
    excluded = tuple(dict(row) for row in payload.get("excluded_for_now", []))

    ids: list[str] = [s.source_id for s in (*sources, *secondary)]
    for row in excluded:
        source_id = str(row.get("id", "")).strip()
        if not source_id or not str(row.get("reason", "")).strip():
            raise ValueError("excluded source requires id and reason")
        ids.append(source_id)

    if len(ids) != len(set(ids)):
        raise ValueError("duplicate source id")
    return HarvestCatalog(1, policy, sources, secondary, excluded)
