import hashlib
from pathlib import Path

from inverted.test3_repo_evidence import _validated_original_bytes


def _pointer_for(payload: bytes) -> bytes:
    return (
        "version https://git-lfs.github.com/spec/v1\n"
        f"oid sha256:{hashlib.sha256(payload).hexdigest()}\n"
        f"size {len(payload)}\n"
    ).encode("ascii")


def test_validated_original_bytes_accepts_hash_proven_materialized_lfs_payload(tmp_path: Path):
    payload = (b"historical-report-payload\n" * 64) + b"end\n"
    pointer = _pointer_for(payload)
    path = tmp_path / "report.txt"
    path.write_bytes(payload)

    resolved, mode = _validated_original_bytes(
        path,
        expected_size=len(pointer),
        expected_sha256=hashlib.sha256(pointer).hexdigest(),
    )

    assert resolved == payload
    assert mode == "git_lfs_materialized"


def test_validated_original_bytes_rejects_materialized_lfs_payload_not_named_by_frozen_pointer(
    tmp_path: Path,
):
    intended = b"intended-historical-payload\n"
    pointer = _pointer_for(intended)
    path = tmp_path / "report.txt"
    path.write_bytes(b"different-payload\n")

    resolved, mode = _validated_original_bytes(
        path,
        expected_size=len(pointer),
        expected_sha256=hashlib.sha256(pointer).hexdigest(),
    )

    assert resolved is None
    assert mode == "mismatch"
