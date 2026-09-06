from __future__ import annotations

import hashlib
import json
from pathlib import Path

MANIFEST_NAME = "manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prompt_fingerprint(prompt: str) -> str:
    normalized = " ".join(prompt.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def collect_hashes(root: Path) -> dict[str, str]:
    root = Path(root)
    result = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel != MANIFEST_NAME:
            result[rel] = sha256_file(path)
    return result


def freeze_task(root: Path) -> dict[str, str]:
    root = Path(root)
    hashes = collect_hashes(root)
    payload = {"algorithm": "sha256", "files": hashes}
    (root / MANIFEST_NAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return hashes


def verify_task(root: Path) -> list[str]:
    root = Path(root)
    manifest = root / MANIFEST_NAME
    if not manifest.exists():
        return [MANIFEST_NAME]
    expected = json.loads(manifest.read_text(encoding="utf-8"))["files"]
    actual = collect_hashes(root)
    mismatches = []
    for rel in sorted(set(expected) | set(actual)):
        if expected.get(rel) != actual.get(rel):
            mismatches.append(rel)
    return mismatches
