from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any

import httpx


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def collect_ollama_provenance(
    base_url: str,
    models: list[str] | tuple[str, ...],
    *,
    transport: httpx.BaseTransport | None = None,
    timeout_s: float = 20.0,
) -> dict[str, Any]:
    """Capture Ollama/model identity without performing inference.

    Only /api/version, /api/tags, /api/show, and /api/ps are queried. No
    /api/chat or /api/generate request is issued.
    """
    base = base_url.rstrip("/")
    client = httpx.Client(transport=transport, timeout=timeout_s)
    try:
        version_response = client.get(f"{base}/api/version")
        version_response.raise_for_status()
        version_payload = version_response.json()

        tags_response = client.get(f"{base}/api/tags")
        tags_response.raise_for_status()
        tags_payload = tags_response.json()

        ps_response = client.get(f"{base}/api/ps")
        ps_response.raise_for_status()
        ps_payload = ps_response.json()

        tag_rows = {str(row.get("name") or row.get("model")): row for row in (tags_payload.get("models") or [])}
        model_rows: dict[str, Any] = {}
        for model in models:
            show_response = client.post(f"{base}/api/show", json={"model": model})
            show_response.raise_for_status()
            show_payload = show_response.json()
            tag = tag_rows.get(model, {})
            model_rows[model] = {
                "requested_name": model,
                "tag_name": tag.get("name") or tag.get("model"),
                "tag_digest": tag.get("digest"),
                "tag_size": tag.get("size"),
                "tag_modified_at": tag.get("modified_at"),
                "tag_details": tag.get("details"),
                "show_details": show_payload.get("details"),
                "model_info": show_payload.get("model_info"),
                "capabilities": show_payload.get("capabilities"),
                "parameters": show_payload.get("parameters"),
                "template_sha256": _canonical_sha256(show_payload.get("template")),
                "system_sha256": _canonical_sha256(show_payload.get("system")),
                "show_payload_sha256": _canonical_sha256(show_payload),
            }

        return {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "base_url": base,
            "server_version": version_payload.get("version"),
            "version_payload": version_payload,
            "tags_payload_sha256": _canonical_sha256(tags_payload),
            "loaded_models": ps_payload.get("models") or [],
            "loaded_models_payload_sha256": _canonical_sha256(ps_payload),
            "models": model_rows,
            "zero_inference_endpoints": ["/api/version", "/api/tags", "/api/show", "/api/ps"],
        }
    finally:
        client.close()
