from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable
import zipfile

from .d4_evidence import validate_d4_evidence_root


R1_REQUIRED_FILES = (
    "00-HARVEST-D-D3-CLOSURE-R1-MASTER-INDEX.json",
    "closure_r1_plan.json",
    "closure_r1_readiness.json",
    "closure_r1_runtime_identity.json",
    "closure_r1_call_ledger.jsonl",
    "closure_r1_campaign_journal.jsonl",
    "closure_r1_normalized_calls.jsonl",
    "closure_r1_raw_model_requests.jsonl",
    "closure_r1_raw_model_responses.jsonl",
    "closure_r1_runtime_telemetry.jsonl",
    "closure_reproducibility_calibration.json",
    "closure_cost_calibration.json",
    "SHA256SUMS.csv",
)


_ALLOWED_R1_STATES = {
    "R1_CALIBRATION_COMPLETE",
    "R1_CALIBRATION_PARTIAL",
    "R1_CALIBRATION_INVALID_INFRASTRUCTURE",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return value


def _read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"{label} is unreadable: {path}") from exc
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label} contains invalid JSONL: {path}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{label} contains a non-object row: {path}")
        rows.append(value)
    return rows


def _tree_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _verify_sha256_manifest(root: Path, required_files: Iterable[str]) -> None:
    manifest_path = root / "SHA256SUMS.csv"
    try:
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        raise ValueError("R1 checksum manifest is unreadable") from exc
    if not rows or set(rows[0]) != {"sha256", "file"}:
        raise ValueError("R1 checksum manifest has an invalid schema")
    by_name = {str(row.get("file") or ""): row for row in rows}
    for required in required_files:
        if required == "SHA256SUMS.csv":
            continue
        if required not in by_name:
            raise ValueError(f"R1 checksum manifest does not cover required artifact: {required}")
    for name, row in by_name.items():
        if not name or Path(name).name != name:
            raise ValueError("R1 checksum manifest contains a non-root artifact path")
        path = root / name
        if not path.is_file():
            raise ValueError(f"R1 checksum artifact is missing: {name}")
        expected = str(row.get("sha256") or "").lower()
        actual = _sha256(path).lower()
        if actual != expected:
            raise ValueError(f"R1 checksum mismatch: {name}")


def _validate_r1_evidence_root(root: Path, *, expected_qwen_model: str, expected_qwen_digest: str) -> dict[str, Any]:
    root = root.resolve()
    missing = [name for name in R1_REQUIRED_FILES if not (root / name).is_file()]
    if missing:
        raise ValueError(f"R1 evidence package is incomplete; missing: {missing}")
    _verify_sha256_manifest(root, R1_REQUIRED_FILES)

    master = _read_json(root / "00-HARVEST-D-D3-CLOSURE-R1-MASTER-INDEX.json", "R1 master index")
    if str(master.get("protocol")) != "D3-CLOSURE-v2" or str(master.get("stage")) != "R1_CALIBRATION":
        raise ValueError("R1 evidence protocol/stage mismatch")
    if str(master.get("mode")) != "REAL_LOCAL":
        raise ValueError("R1 evidence must be REAL_LOCAL")
    if master.get("blind_retries_allowed") is not False:
        raise ValueError("R1 evidence permits or fails to prohibit blind retries")
    if int(master.get("planned_physical_calls", -1)) != 24 or int(master.get("max_physical_calls", -1)) != 24:
        raise ValueError("R1 evidence does not preserve the exact 24-call design/ceiling")
    calls = int(master.get("physical_model_calls", -1))
    if not 1 <= calls <= 24:
        raise ValueError("R1 evidence must contain between 1 and 24 physical calls")
    final_state = str(master.get("final_state") or "")
    if final_state not in _ALLOWED_R1_STATES:
        raise ValueError(f"R1 evidence has unsupported final_state: {final_state}")
    if final_state == "R1_CALIBRATION_COMPLETE" and calls != 24:
        raise ValueError("R1 COMPLETE evidence must contain exactly 24 physical calls")
    if final_state == "R1_CALIBRATION_PARTIAL" and calls >= 24:
        raise ValueError("R1 PARTIAL evidence must contain fewer than 24 physical calls")

    identity = _read_json(root / "closure_r1_runtime_identity.json", "R1 runtime identity")
    if set(identity) != {"SMALL_A", "QWEN"}:
        raise ValueError("R1 runtime identity must contain exactly SMALL_A and QWEN")
    qwen = identity.get("QWEN")
    small = identity.get("SMALL_A")
    if not isinstance(qwen, dict) or not isinstance(small, dict):
        raise ValueError("R1 runtime identity entries must be objects")
    if str(qwen.get("model_id")) != expected_qwen_model:
        raise ValueError("R1 Qwen model id does not match frozen D4 model")
    if str(qwen.get("model_digest")) != expected_qwen_digest:
        raise ValueError("R1 Qwen model digest does not match frozen D4 digest")
    if not str(small.get("model_id") or "") or not str(small.get("model_digest") or ""):
        raise ValueError("R1 SMALL_A runtime identity/digest is incomplete")

    ledger = _read_jsonl(root / "closure_r1_call_ledger.jsonl", "R1 call ledger")
    committed = [row for row in ledger if row.get("committed") is True]
    experiment_ids = [str(row.get("experiment_id") or "") for row in committed]
    if len(ledger) != calls or len(committed) != calls or len(set(experiment_ids)) != calls or any(not exp for exp in experiment_ids):
        raise ValueError("R1 call ledger does not contain exactly the uniquely committed physical calls")
    if any(int(row.get("attempt", 0)) != 1 for row in committed):
        raise ValueError("R1 evidence contains a retried physical call")
    expected_ids = set(experiment_ids)

    normalized = _read_jsonl(root / "closure_r1_normalized_calls.jsonl", "R1 normalized calls")
    if len(normalized) != calls or {str(row.get("experiment_id") or "") for row in normalized} != expected_ids:
        raise ValueError("R1 normalized-call evidence does not match the committed ledger")

    for filename, label in (
        ("closure_r1_raw_model_requests.jsonl", "R1 raw requests"),
        ("closure_r1_raw_model_responses.jsonl", "R1 raw responses"),
        ("closure_r1_runtime_telemetry.jsonl", "R1 runtime telemetry"),
    ):
        rows = _read_jsonl(root / filename, label)
        ids = {str(row.get("experiment_id") or "") for row in rows}
        if len(rows) != calls or ids != expected_ids:
            raise ValueError(f"{label} does not match the committed ledger")

    journal = _read_jsonl(root / "closure_r1_campaign_journal.jsonl", "R1 campaign journal")
    for experiment_id in expected_ids:
        states = [str(row.get("state") or "") for row in journal if str(row.get("experiment_id") or "") == experiment_id]
        if states.count("STARTED") != 1 or states.count("COMMITTED") != 1:
            raise ValueError(f"R1 journal is incomplete or ambiguous for {experiment_id}")

    evidence_class = {
        "R1_CALIBRATION_COMPLETE": "RAW_PERSISTED_REAL_LOCAL_CALIBRATION",
        "R1_CALIBRATION_PARTIAL": "RAW_PERSISTED_REAL_LOCAL_PARTIAL",
        "R1_CALIBRATION_INVALID_INFRASTRUCTURE": "RAW_PERSISTED_REAL_LOCAL_INVALID_INFRASTRUCTURE",
    }[final_state]
    return {
        "root": root,
        "physical_model_calls": calls,
        "final_state": final_state,
        "evidence_class": evidence_class,
        "qwen_model_id": str(qwen["model_id"]),
        "qwen_model_digest": str(qwen["model_digest"]),
        "small_model_id": str(small["model_id"]),
        "small_model_digest": str(small["model_digest"]),
        "source_fingerprint": _tree_fingerprint(root),
    }


def _write_deterministic_zip(source_root: Path, destination: Path, prefix: str) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for path in sorted(p for p in source_root.rglob("*") if p.is_file()):
            relative = path.relative_to(source_root).as_posix()
            info = zipfile.ZipInfo(f"{prefix}/{relative}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def _archive_record(path: Path) -> dict[str, Any]:
    return {"file": path.name, "sha256": _sha256(path), "size_bytes": path.stat().st_size}


def _write_archive_manifest(root: Path, records: Iterable[dict[str, Any]]) -> None:
    with (root / "SHA256SUMS-D4-R1-ARCHIVES.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sha256", "size_bytes", "file"])
        for record in records:
            writer.writerow([record["sha256"], record["size_bytes"], record["file"]])


def build_d4_r1_evidence_bundle(
    *,
    d4_root: str | Path,
    r1_root: str | Path,
    output_root: str | Path,
    implementation_commit: str,
    expected_qwen_model: str,
) -> dict[str, Any]:
    d4_root = Path(d4_root).resolve()
    r1_root = Path(r1_root).resolve()
    output_root = Path(output_root).resolve()
    if not str(implementation_commit).strip():
        raise ValueError("implementation_commit is required")
    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError("evidence bundle output directory must be empty")
    output_root.mkdir(parents=True, exist_ok=True)

    before_d4 = _tree_fingerprint(d4_root)
    before_r1 = _tree_fingerprint(r1_root)
    d4 = validate_d4_evidence_root(d4_root, expected_model=expected_qwen_model)
    r1 = _validate_r1_evidence_root(
        r1_root,
        expected_qwen_model=expected_qwen_model,
        expected_qwen_digest=d4.model_digest,
    )

    d4_zip = output_root / "D4-COMPLETE-CAMPAIGN.zip"
    r1_zip = output_root / "R1-CALIBRATION-CAMPAIGN.zip"
    _write_deterministic_zip(d4_root, d4_zip, "harvest-d-d4-qwen-policy")
    _write_deterministic_zip(r1_root, r1_zip, "harvest-d-d3-closure-r1")
    d4_archive = _archive_record(d4_zip)
    r1_archive = _archive_record(r1_zip)
    _write_archive_manifest(output_root, (d4_archive, r1_archive))

    if _tree_fingerprint(d4_root) != before_d4 or _tree_fingerprint(r1_root) != before_r1:
        raise RuntimeError("source evidence mutated during bundling")

    result: dict[str, Any] = {
        "state": "EVIDENCE_BUNDLE_COMPLETE",
        "implementation_commit": str(implementation_commit),
        "d4": {
            "evidence_class": "RAW_PERSISTED_REAL_LOCAL_CAMPAIGN",
            "physical_model_calls": d4.physical_model_calls,
            "policy_id": d4.policy_id,
            "model_id": d4.model_id,
            "model_digest": d4.model_digest,
            "source_fingerprint": before_d4,
        },
        "r1": {
            "evidence_class": r1["evidence_class"],
            "physical_model_calls": r1["physical_model_calls"],
            "final_state": r1["final_state"],
            "qwen_model_id": r1["qwen_model_id"],
            "qwen_model_digest": r1["qwen_model_digest"],
            "small_model_id": r1["small_model_id"],
            "small_model_digest": r1["small_model_digest"],
            "source_fingerprint": before_r1,
        },
        "archives": {"d4": d4_archive, "r1": r1_archive},
        "source_mutation_observed": False,
        "model_inference_performed": False,
    }
    (output_root / "evidence_provenance.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    index = f"""# HARVEST D — D4 + R1 EVIDENCE INDEX

Implementation commit:

    {implementation_commit}

## D4 Qwen policy campaign

Evidence state:

    RAW_PERSISTED_REAL_LOCAL_CAMPAIGN

Physical model calls:

    {d4.physical_model_calls}

Frozen policy:

    {d4.policy_id}

Model:

    {d4.model_id}

Model digest:

    {d4.model_digest}

Archive:

    D4-COMPLETE-CAMPAIGN.zip

SHA-256:

    {d4_archive['sha256'].upper()}

## R1 calibration

Evidence state:

    {r1['evidence_class']}

Final state:

    {r1['final_state']}

Physical model calls:

    {r1['physical_model_calls']}

Qwen model digest:

    {r1['qwen_model_digest']}

SMALL_A model digest:

    {r1['small_model_digest']}

Archive:

    R1-CALIBRATION-CAMPAIGN.zip

SHA-256:

    {r1_archive['sha256'].upper()}

## Integrity

- Source evidence was validated before archiving.
- D4 and R1 Qwen model digests match exactly.
- Every committed R1 physical call has one STARTED and one COMMITTED journal event.
- Blind retries are forbidden and every committed call has attempt=1.
- Raw requests, raw responses, normalized calls, runtime telemetry, and call ledger counts agree.
- Source directories were fingerprinted before and after packaging and were not mutated.
- Packaging performs zero model inference.
"""
    (output_root / "00-HARVEST-D-D4-R1-EVIDENCE-INDEX.md").write_text(index, encoding="utf-8")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and package immutable Harvest-D D4 + R1 evidence")
    parser.add_argument("--d4-root", required=True)
    parser.add_argument("--r1-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--implementation-commit", required=True)
    parser.add_argument("--expected-qwen-model", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = build_d4_r1_evidence_bundle(
            d4_root=args.d4_root,
            r1_root=args.r1_root,
            output_root=args.output_root,
            implementation_commit=args.implementation_commit,
            expected_qwen_model=args.expected_qwen_model,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"D4/R1 EVIDENCE BUNDLE ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
