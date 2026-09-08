"""Non-disclosing privacy scan/sanitization for tracked evidence.

The scanner reports only aggregate categories, file-relative paths, counts, and
hashes. It never returns or prints the matched private value. Sanitization is
limited to local user-profile path prefixes; scientific payload values and path
suffixes are otherwise preserved.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


_REDACTION = b"[REDACTED_USER_PROFILE]"
_EXCLUDED_NAMES = {
    "FILES-SHA256.csv",
    "SHA256SUMS.csv",
    "PRIVACY-TRACKED-SCAN.json",
    "PRIVACY-TRANSFORM.json",
}
_TEXT_SUFFIXES = {
    ".csv", ".json", ".jsonl", ".log", ".md", ".ps1", ".txt", ".toml",
    ".yaml", ".yml",
}

# Match only the local profile prefix. The remainder of the path survives the
# replacement, so scientific file identity below the profile root stays visible.
_PATTERNS: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    (
        "windows_user_profile",
        re.compile(rb"[A-Za-z]:\\+Users\\+[^\\/\s\"',}\]]+", re.IGNORECASE),
    ),
    (
        "windows_user_profile",
        re.compile(rb"[A-Za-z]:/Users/[^/\\\s\"',}\]]+", re.IGNORECASE),
    ),
    (
        "windows_user_profile",
        re.compile(rb"/mnt/[A-Za-z]/Users/[^/\\\s\"',}\]]+", re.IGNORECASE),
    ),
    (
        "posix_home_profile",
        re.compile(rb"/home/[^/\\\s\"',}\]]+"),
    ),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _eligible(path: Path) -> bool:
    if path.name in _EXCLUDED_NAMES:
        return False
    if path.suffix.lower() not in _TEXT_SUFFIXES:
        return False
    try:
        head = path.read_bytes()[:8192]
    except OSError:
        return False
    return b"\x00" not in head


def _iter_files(root: Path) -> Iterable[Path]:
    return (path for path in sorted(root.rglob("*")) if path.is_file() and _eligible(path))


def _counts(data: bytes) -> Counter[str]:
    counts: Counter[str] = Counter()
    for category, pattern in _PATTERNS:
        counts[category] += sum(1 for _ in pattern.finditer(data))
    return +counts


def scan_tree(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    category_totals: Counter[str] = Counter()
    files: list[dict[str, Any]] = []
    scanned = 0
    for path in _iter_files(root):
        scanned += 1
        data = path.read_bytes()
        counts = _counts(data)
        if not counts:
            continue
        category_totals.update(counts)
        files.append({
            "path": path.relative_to(root).as_posix(),
            "categories": dict(sorted(counts.items())),
            "total_matches": sum(counts.values()),
        })
    total = sum(category_totals.values())
    return {
        "schema_version": 1,
        "privacy_ok": total == 0,
        "files_scanned": scanned,
        "files_with_findings": len(files),
        "total_matches": total,
        "categories": dict(sorted(category_totals.items())),
        "files": files,
    }


def _sanitize_bytes(data: bytes) -> tuple[bytes, Counter[str]]:
    counts: Counter[str] = Counter()
    value = data
    for category, pattern in _PATTERNS:
        value, count = pattern.subn(_REDACTION, value)
        if count:
            counts[category] += count
    return value, +counts


def _reseal_outer_manifest(root: Path, manifest: Path) -> None:
    if not manifest.is_file():
        raise FileNotFoundError(f"outer evidence manifest missing: {manifest}")
    with manifest.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"path", "sha256", "bytes"} <= set(reader.fieldnames):
            raise ValueError("outer evidence manifest must contain path, sha256, bytes")
        fieldnames = list(reader.fieldnames)
        rows = [dict(row) for row in reader]

    for row in rows:
        raw = str(row.get("path") or "").replace("\\", "/")
        rel = Path(raw)
        if not raw or rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"invalid outer manifest path: {raw!r}")
        path = root / rel
        if not path.is_file():
            raise ValueError(f"outer manifest path is missing: {raw}")
        data = path.read_bytes()
        row["sha256"] = _sha256(data)
        row["bytes"] = str(len(data))

    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sanitize_tree(
    root: str | Path,
    *,
    outer_manifest: str | Path | None = None,
    ledger_path: str | Path | None = None,
    scan_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(root)
    ledger: list[dict[str, Any]] = []
    total_replacements = 0

    for path in _iter_files(root):
        before = path.read_bytes()
        after, counts = _sanitize_bytes(before)
        if not counts or after == before:
            continue
        path.write_bytes(after)
        count = sum(counts.values())
        total_replacements += count
        ledger.append({
            "path": path.relative_to(root).as_posix(),
            "categories": dict(sorted(counts.items())),
            "replacement_count": count,
            "pre_sha256": _sha256(before),
            "post_sha256": _sha256(after),
        })

    if ledger and outer_manifest is not None:
        _reseal_outer_manifest(root, Path(outer_manifest))

    report = scan_tree(root)
    result = {
        "schema_version": 1,
        "privacy_ok": report["privacy_ok"],
        "files_changed": len(ledger),
        "total_replacements": total_replacements,
        "categories": dict(sorted(Counter({
            category: sum(row["categories"].get(category, 0) for row in ledger)
            for category in {key for row in ledger for key in row["categories"]}
        }).items())),
        "transformations": ledger,
    }

    if ledger_path is not None:
        path = Path(ledger_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if scan_path is not None:
        path = Path(scan_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if not report["privacy_ok"]:
        raise ValueError("tracked evidence still contains private machine/profile path structures")
    return result


def _safe_summary(report: dict[str, Any]) -> str:
    return json.dumps({
        "privacy_ok": bool(report.get("privacy_ok")),
        "files_with_findings": int(report.get("files_with_findings", 0)),
        "total_matches": int(report.get("total_matches", 0)),
        "categories": report.get("categories", {}),
    }, sort_keys=True, separators=(",", ":"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan/sanitize tracked evidence without disclosing matched values.")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check")
    check.add_argument("--root", required=True)
    check.add_argument("--scan-out")

    sanitize = sub.add_parser("sanitize")
    sanitize.add_argument("--root", required=True)
    sanitize.add_argument("--outer-manifest")
    sanitize.add_argument("--ledger-out")
    sanitize.add_argument("--scan-out")

    args = parser.parse_args(argv)
    if args.command == "check":
        report = scan_tree(args.root)
        if args.scan_out:
            path = Path(args.scan_out)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(_safe_summary(report))
        return 0 if report["privacy_ok"] else 3

    result = sanitize_tree(
        args.root,
        outer_manifest=args.outer_manifest,
        ledger_path=args.ledger_out,
        scan_path=args.scan_out,
    )
    print(json.dumps({
        "privacy_ok": result["privacy_ok"],
        "files_changed": result["files_changed"],
        "total_replacements": result["total_replacements"],
        "categories": result["categories"],
    }, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
