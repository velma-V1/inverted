from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
from typing import Mapping
import zipfile


_TEXT_EXTENSIONS = {
    ".csv", ".env", ".html", ".ini", ".json", ".jsonl", ".log", ".md",
    ".ps1", ".py", ".toml", ".tsv", ".txt", ".xml", ".yaml", ".yml",
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _string_variants(value: str) -> tuple[str, ...]:
    variants = {value}
    if "\\" in value:
        variants.add(value.replace("\\", "\\\\"))
        variants.add(value.replace("\\", "/"))
    if "/" in value:
        variants.add(value.replace("/", "\\"))
        variants.add(value.replace("/", "\\\\"))
    return tuple(sorted((v for v in variants if v), key=len, reverse=True))


def _replacement_pairs(replacements: Mapping[str, str]) -> tuple[tuple[bytes, bytes], ...]:
    pairs: list[tuple[bytes, bytes]] = []
    seen: set[tuple[bytes, bytes]] = set()
    for source, replacement in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        if not source:
            raise ValueError("empty privacy identifier is forbidden")
        replacement_by_shape = {
            "raw": replacement,
            "escaped": replacement.replace("\\", "\\\\"),
            "slash": replacement.replace("\\", "/"),
        }
        for source_variant in _string_variants(source):
            if "\\\\" in source_variant:
                target = replacement_by_shape["escaped"]
            elif "/" in source_variant:
                target = replacement_by_shape["slash"]
            else:
                target = replacement_by_shape["raw"]
            for encoding in ("utf-8", "utf-16-le", "utf-16-be"):
                pair = (source_variant.encode(encoding), target.encode(encoding))
                if pair not in seen:
                    seen.add(pair)
                    pairs.append(pair)
    pairs.sort(key=lambda pair: len(pair[0]), reverse=True)
    return tuple(pairs)


def _replace_bytes(data: bytes, pairs: tuple[tuple[bytes, bytes], ...]) -> tuple[bytes, int]:
    changed = data
    count = 0
    for source, replacement in pairs:
        occurrences = changed.count(source)
        if occurrences:
            changed = changed.replace(source, replacement)
            count += occurrences
    return changed, count


def _remaining_matches(data: bytes, pairs: tuple[tuple[bytes, bytes], ...]) -> int:
    return sum(data.count(source) for source, _ in pairs)


def _is_text_member(name: str) -> bool:
    path = Path(name)
    if path.suffix.lower() in _TEXT_EXTENSIONS or path.name.lower() in {
        "dockerfile", "makefile", "requirements.txt",
    }:
        return True

    normalized = "/" + name.replace("\\", "/").lstrip("./").lower()
    if "/.git/objects/" in normalized or normalized.endswith("/.git/index"):
        return False
    if "/.git/logs/" in normalized or "/.git/refs/" in normalized:
        return True
    return normalized.endswith((
        "/.git/head",
        "/.git/config",
        "/.git/packed-refs",
        "/.git/fetch_head",
        "/.git/orig_head",
        "/.git/merge_head",
        "/.git/commit_editmsg",
        "/.git/description",
        "/.git/info/exclude",
    ))


def _sanitize_member_name(name: str, replacements: Mapping[str, str]) -> tuple[str, int]:
    new_name = name
    count = 0
    for source, replacement in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        for variant in _string_variants(source):
            occurrences = new_name.count(variant)
            if not occurrences:
                continue
            if "\\\\" in variant:
                target = replacement.replace("\\", "\\\\")
            elif "/" in variant:
                target = replacement.replace("\\", "/")
            else:
                target = replacement
            new_name = new_name.replace(variant, target)
            count += occurrences
    return new_name, count


def _sanitize_zip_bytes(
    source_bytes: bytes,
    replacements: Mapping[str, str],
    *,
    depth: int,
    max_depth: int,
) -> tuple[bytes, dict[str, int]]:
    if depth > max_depth:
        raise ValueError(f"nested ZIP depth exceeds safety limit {max_depth}")

    pairs = _replacement_pairs(replacements)
    source_stream = io.BytesIO(source_bytes)
    output_stream = io.BytesIO()
    stats = {
        "changed_members": 0,
        "unchanged_members": 0,
        "redaction_occurrences": 0,
        "renamed_members": 0,
        "nested_zips": 0,
        "remaining_matches": 0,
        "binary_members_scanned": 0,
    }

    with zipfile.ZipFile(source_stream, "r") as source, zipfile.ZipFile(output_stream, "w") as output:
        archive_comment, archive_comment_changes = _replace_bytes(source.comment, pairs)
        output.comment = archive_comment
        stats["redaction_occurrences"] += archive_comment_changes

        for info in source.infolist():
            original_name = info.filename
            new_name, name_changes = _sanitize_member_name(original_name, replacements)
            new_info = copy.copy(info)
            new_info.filename = new_name

            new_comment, comment_changes = _replace_bytes(info.comment, pairs)
            new_info.comment = new_comment
            if _remaining_matches(info.extra, pairs):
                raise ValueError(f"ZIP extra metadata contains a privacy identifier: {original_name}")

            metadata_changes = name_changes + comment_changes
            stats["redaction_occurrences"] += metadata_changes
            if name_changes:
                stats["renamed_members"] += 1

            if info.is_dir():
                output.writestr(new_info, b"")
                if metadata_changes:
                    stats["changed_members"] += 1
                else:
                    stats["unchanged_members"] += 1
                continue

            original_data = source.read(info)
            new_data = original_data
            content_changes = 0

            if Path(original_name).suffix.lower() == ".zip":
                nested_data, nested_stats = _sanitize_zip_bytes(
                    original_data,
                    replacements,
                    depth=depth + 1,
                    max_depth=max_depth,
                )
                stats["nested_zips"] += 1 + nested_stats["nested_zips"]
                stats["redaction_occurrences"] += nested_stats["redaction_occurrences"]
                stats["binary_members_scanned"] += nested_stats["binary_members_scanned"]
                stats["remaining_matches"] += nested_stats["remaining_matches"]
                if nested_data != original_data:
                    new_data = nested_data
                    content_changes = 1
            elif _is_text_member(original_name):
                new_data, content_changes = _replace_bytes(original_data, pairs)
                stats["redaction_occurrences"] += content_changes
            else:
                stats["binary_members_scanned"] += 1
                binary_matches = _remaining_matches(original_data, pairs)
                if binary_matches:
                    raise ValueError(
                        f"binary member contains a privacy identifier and was not modified: {original_name}"
                    )

            output.writestr(new_info, new_data, compress_type=info.compress_type)

            if metadata_changes or content_changes:
                stats["changed_members"] += 1
            else:
                stats["unchanged_members"] += 1
                if _sha256_bytes(new_data) != _sha256_bytes(original_data):
                    raise AssertionError(f"unchanged member content hash changed: {original_name}")

    if stats["redaction_occurrences"] == 0:
        return source_bytes, stats

    sanitized = output_stream.getvalue()

    with zipfile.ZipFile(io.BytesIO(sanitized), "r") as archive:
        stats["remaining_matches"] += _remaining_matches(archive.comment, pairs)
        for info in archive.infolist():
            stats["remaining_matches"] += _remaining_matches(
                info.filename.encode("utf-8", errors="surrogatepass"), pairs
            )
            stats["remaining_matches"] += _remaining_matches(info.comment, pairs)
            stats["remaining_matches"] += _remaining_matches(info.extra, pairs)
            if info.is_dir():
                continue
            data = archive.read(info)
            if Path(info.filename).suffix.lower() == ".zip":
                continue
            stats["remaining_matches"] += _remaining_matches(data, pairs)

    return sanitized, stats


def sanitize_zip(
    *,
    source_zip: str | Path,
    output_zip: str | Path,
    replacements: Mapping[str, str],
    max_nested_depth: int = 8,
) -> dict[str, object]:
    source = Path(source_zip).resolve()
    output = Path(output_zip).resolve()
    if source == output:
        raise ValueError("in-place ZIP overwrite is forbidden")
    if not source.is_file():
        raise ValueError(f"source ZIP does not exist: {source.name}")
    if output.exists():
        raise ValueError(f"sanitized output already exists: {output.name}")
    if not replacements:
        raise ValueError("at least one exact privacy identifier is required")

    source_bytes = source.read_bytes()
    sanitized_bytes, stats = _sanitize_zip_bytes(
        source_bytes,
        replacements,
        depth=0,
        max_depth=max_nested_depth,
    )
    if stats["remaining_matches"]:
        raise ValueError(
            f"privacy verification failed: {stats['remaining_matches']} exact identifier matches remain"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(sanitized_bytes)

    return {
        "state": "PRIVACY_SANITIZED",
        "source_file": source.name,
        "output_file": output.name,
        "source_sha256": _sha256_file(source),
        "output_sha256": _sha256_file(output),
        **stats,
    }


def _parse_replacements(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--replace must use EXACT=PLACEHOLDER")
        source, replacement = value.split("=", 1)
        if not source or source in result:
            raise ValueError("replacement sources must be unique and non-empty")
        result[source] = replacement
    return result


def _load_replacements(path: str | None, inline: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    if path:
        parsed = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        if not isinstance(parsed, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in parsed.items()):
            raise ValueError("replacements JSON must be an object of exact-string to placeholder-string values")
        result.update(parsed)
    for source, replacement in _parse_replacements(inline).items():
        if source in result:
            raise ValueError("duplicate replacement source")
        result[source] = replacement
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Surgically remove exact personal/PC identifiers from a test ZIP")
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--replacements-json")
    parser.add_argument("--replace", action="append", default=[])
    parser.add_argument("--max-nested-depth", type=int, default=8)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = sanitize_zip(
            source_zip=args.source,
            output_zip=args.output,
            replacements=_load_replacements(args.replacements_json, args.replace),
            max_nested_depth=args.max_nested_depth,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"PRIVACY SANITIZE ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
