from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any, Iterable, Mapping
import zipfile


_REQUIRED_RUNS: tuple[tuple[str, str], ...] = (
    ("d3-frozen", "runs/frozen-harvest-d-d3-20260903"),
    ("post-d3-salvage", "runs/post-d3-analysis-r1"),
    ("r0-gate", "runs/harvest-d-d3-closure-r0-gate"),
    ("r1-model-free-gate", "runs/harvest-d-d3-closure-r1-model-free-gate"),
    ("r1-real", "runs/harvest-d-d3-closure-r1"),
    ("d4-r1-preservation-bundle", "runs/evidence-publish/harvest-d-d4-r1-20260904"),
)

_REPO_CONTEXT_ROOTS: tuple[tuple[str, str], ...] = (
    ("repo-configs", "configs"),
    ("repo-scripts", "scripts"),
    ("repo-harvest-d-source", "src/inverted/harvest_d"),
    ("repo-tests", "tests"),
    ("repo-research", "docs/research"),
    ("repo-specs", "docs/superpowers/specs"),
    ("repo-plans", "docs/superpowers/plans"),
)


@dataclass(frozen=True)
class _Source:
    label: str
    root: Path
    destination: Path
    required: bool


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _files(root: Path) -> tuple[Path, ...]:
    if root.is_file():
        return (root,)
    rows: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symlink is forbidden in data dump source: {path}")
        if path.is_file():
            rows.append(path)
    return tuple(sorted(rows, key=lambda p: p.as_posix().lower()))


def _copy_source(source: _Source, staging: Path) -> tuple[int, int]:
    if not source.root.exists():
        if source.required:
            raise ValueError(f"required evidence root is missing: {source.root}")
        return 0, 0
    files = _files(source.root)
    if source.required and not files:
        raise ValueError(f"required evidence root is empty: {source.root}")
    count = 0
    total = 0
    for original in files:
        relative = original.name if source.root.is_file() else original.relative_to(source.root)
        destination = staging / source.destination / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        before = _sha256(original)
        shutil.copy2(original, destination)
        copied = _sha256(destination)
        after = _sha256(original)
        if before != copied or before != after:
            raise ValueError(f"source mutation or copy corruption observed: {original}")
        count += 1
        total += original.stat().st_size
    return count, total


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[Mapping[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _inventory(staging: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in _files(staging):
        rel = path.relative_to(staging).as_posix()
        if rel in {"FILE_INVENTORY.csv", "SHA256_MANIFEST.csv"}:
            continue
        rows.append({"file": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)})
    return rows


def _deterministic_zip(source_root: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in _files(source_root):
            rel = path.relative_to(source_root).as_posix()
            info = zipfile.ZipInfo(f"post-r1-data-dump/{rel}")
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def build_post_r1_data_dump(
    *,
    repo_root: str | Path,
    d4_root: str | Path,
    output_root: str | Path,
    r1_execution_commit: str,
    publisher_commit: str,
    git_metadata: Mapping[str, Any],
    source_archives: Mapping[str, str | Path] | None,
) -> dict[str, object]:
    repo = Path(repo_root).resolve()
    d4 = Path(d4_root).resolve()
    out = Path(output_root).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"data dump output is append-only; choose an empty output root: {out}")
    out.mkdir(parents=True, exist_ok=True)
    staging = out / "staging"
    staging.mkdir()

    sources: list[_Source] = [
        _Source(label, repo / rel, Path("payload") / label, True)
        for label, rel in _REQUIRED_RUNS
    ]
    sources.append(_Source("d4-original", d4, Path("payload") / "d4-original", True))
    for label, rel in _REPO_CONTEXT_ROOTS:
        sources.append(_Source(label, repo / rel, Path("repo-context") / label, False))
    for label, path in sorted((source_archives or {}).items()):
        sources.append(_Source(f"source-archive:{label}", Path(path).resolve(), Path("repo-snapshots") / Path(path).name, True))

    discovered: list[dict[str, object]] = []
    missing_optional: list[str] = []
    for source in sources:
        if not source.root.exists() and not source.required:
            missing_optional.append(source.label)
            discovered.append({
                "label": source.label,
                "source_path": str(source.root),
                "destination": source.destination.as_posix(),
                "required": False,
                "state": "MISSING_OPTIONAL",
                "file_count": 0,
                "size_bytes": 0,
            })
            continue
        count, size = _copy_source(source, staging)
        discovered.append({
            "label": source.label,
            "source_path": str(source.root),
            "destination": source.destination.as_posix(),
            "required": source.required,
            "state": "COLLECTED",
            "file_count": count,
            "size_bytes": size,
        })

    provenance = {
        "state": "POST_R1_DATA_DUMP_COMPLETE",
        "scope": "Harvest D Closure through R1; pre-R2 forensic export",
        "r1_execution_commit": str(r1_execution_commit),
        "publisher_commit": str(publisher_commit),
        "git": dict(git_metadata),
        "required_evidence_roots": [rel for _, rel in _REQUIRED_RUNS] + [str(d4)],
        "missing_optional_sources": missing_optional,
        "model_inference_performed": False,
        "source_mutation_observed": False,
        "data_collection_is_cheap_retesting_is_not": True,
        "ready_for_r2": False,
    }
    _write_json(staging / "PROVENANCE.json", provenance)
    (staging / "PROVENANCE.txt").write_text(
        "INVERTED Harvest D post-R1 forensic data dump\n"
        f"R1 execution commit: {r1_execution_commit}\n"
        f"Publisher commit: {publisher_commit}\n"
        "Model inference performed: false\n"
        "Source mutation observed: false\n"
        "Purpose: freeze all available evidence before R2 design/execution.\n",
        encoding="utf-8",
    )
    _write_csv(
        staging / "DISCOVERED_SOURCE_ARTIFACTS.csv",
        ["label", "source_path", "destination", "required", "state", "file_count", "size_bytes"],
        discovered,
    )

    index_lines = [
        "# INVERTED — Harvest D Post-R1 Full Data Dump",
        "",
        "Status: COMPLETE FORENSIC EXPORT / R2 NOT YET AUTHORIZED",
        "",
        f"R1 execution commit: `{r1_execution_commit}`",
        f"Publisher commit: `{publisher_commit}`",
        "",
        "## Evidence layers",
        "",
        "1. Immutable/raw persisted run evidence and requests/responses.",
        "2. Normalized event/call/telemetry evidence.",
        "3. Post-D3 causal/forensic salvage and provenance surfaces.",
        "4. Derived R0/R1 decision, coverage, reproducibility, and cost artifacts.",
        "",
        "## Source roots",
        "",
    ]
    for row in discovered:
        index_lines.append(
            f"- `{row['label']}` — {row['state']} — {row['file_count']} files — {row['size_bytes']} bytes"
        )
    index_lines.extend([
        "",
        "## Integrity",
        "",
        "- Every payload file is inventoried and SHA-256 hashed.",
        "- Source files are hashed before copy, copied, verified, and rehashed after copy.",
        "- Collection performs zero model inference.",
        "- R2 remains unauthorized until this dump is independently inspected.",
        "",
    ])
    (staging / "DATA_DUMP_INDEX.md").write_text("\n".join(index_lines), encoding="utf-8")

    first_inventory = _inventory(staging)
    _write_csv(staging / "FILE_INVENTORY.csv", ["file", "size_bytes", "sha256"], first_inventory)
    manifest_rows = _inventory(staging)
    _write_csv(staging / "SHA256_MANIFEST.csv", ["sha256", "size_bytes", "file"], (
        {"sha256": row["sha256"], "size_bytes": row["size_bytes"], "file": row["file"]}
        for row in manifest_rows
    ))

    zip_path = out / "INVERTED-HARVEST-D-POST-R1-FULL-DUMP.zip"
    _deterministic_zip(staging, zip_path)
    zip_sha = _sha256(zip_path)
    sha_file = out / "INVERTED-HARVEST-D-POST-R1-FULL-DUMP.sha256"
    sha_file.write_text(f"{zip_sha}  {zip_path.name}\n", encoding="utf-8")

    return {
        "state": "POST_R1_DATA_DUMP_COMPLETE",
        "staging_root": str(staging),
        "zip_path": str(zip_path),
        "zip_sha256": zip_sha,
        "sha256_file": str(sha_file),
        "source_count": len(discovered),
        "missing_optional_sources": missing_optional,
        "model_inference_performed": False,
        "source_mutation_observed": False,
        "ready_for_r2": False,
    }


def _parse_source_archives(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--source-archive must use LABEL=PATH")
        label, raw_path = value.split("=", 1)
        label = label.strip()
        if not label or label in result:
            raise ValueError("source archive labels must be unique and non-empty")
        result[label] = Path(raw_path).resolve()
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect complete zero-inference Harvest D post-R1 forensic data dump")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--d4-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--r1-execution-commit", required=True)
    parser.add_argument("--publisher-commit", required=True)
    parser.add_argument("--git-metadata-file", required=True)
    parser.add_argument("--source-archive", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        metadata = json.loads(Path(args.git_metadata_file).read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            raise ValueError("git metadata file must contain a JSON object")
        result = build_post_r1_data_dump(
            repo_root=args.repo_root,
            d4_root=args.d4_root,
            output_root=args.output_root,
            r1_execution_commit=args.r1_execution_commit,
            publisher_commit=args.publisher_commit,
            git_metadata=metadata,
            source_archives=_parse_source_archives(args.source_archive),
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"POST-R1 DATA DUMP ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
