from __future__ import annotations

import json
from pathlib import Path


def write_json(path: Path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def append_jsonl(path: Path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, default=str) + "\n")

import hashlib

MANIFEST_NAME = "sha256_manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_hashes(root: Path) -> dict[str, str]:
    root = Path(root)
    result = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel != MANIFEST_NAME:
            result[rel] = sha256_file(path)
    return result


def write_manifest(root: Path) -> Path:
    path = Path(root) / MANIFEST_NAME
    write_json(path, {"algorithm": "sha256", "files": collect_hashes(root)})
    return path


def verify_manifest(root: Path) -> list[str]:
    root = Path(root)
    payload = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    actual = collect_hashes(root)
    expected = payload.get("files", {})
    return sorted(rel for rel in set(actual) | set(expected) if actual.get(rel) != expected.get(rel))
