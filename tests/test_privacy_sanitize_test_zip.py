from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest

from inverted.harvest_d.privacy_sanitize_test_zip import sanitize_zip


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_sanitizer_changes_only_exact_identifier_occurrences(tmp_path: Path) -> None:
    source = tmp_path / "test.zip"
    output = tmp_path / "test.sanitized.zip"

    untouched = b'{"test_id":"R1","model":"qwen3.5:9b-q8_0","prompt":"LiteralName is a literal test token"}\n'
    sensitive = (json.dumps({
        "source": r"C:\Users\TestUser\inverted\runs",
        "host": "DESKTOP-ABC123",
        "machine_guid": "11111111-2222-3333-4444-555555555555",
    }, separators=(",", ":")) + "\n").encode("utf-8")

    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("evidence/untouched.json", untouched)
        archive.writestr("evidence/provenance.json", sensitive)
        archive.writestr("payload.bin", b"\x00\x01SAFE-BINARY-EVIDENCE\xff")

    result = sanitize_zip(
        source_zip=source,
        output_zip=output,
        replacements={
            r"C:\Users\TestUser": r"C:\Users\[REDACTED_USER]",
            "DESKTOP-ABC123": "[REDACTED_HOST]",
            "11111111-2222-3333-4444-555555555555": "[REDACTED_MACHINE_GUID]",
        },
    )

    assert result["state"] == "PRIVACY_SANITIZED"
    assert result["changed_members"] == 1
    assert result["unchanged_members"] == 2
    assert result["remaining_matches"] == 0

    with zipfile.ZipFile(source) as before, zipfile.ZipFile(output) as after:
        assert before.namelist() == after.namelist()
        assert _sha(before.read("evidence/untouched.json")) == _sha(after.read("evidence/untouched.json"))
        assert _sha(before.read("payload.bin")) == _sha(after.read("payload.bin"))
        changed = after.read("evidence/provenance.json").decode("utf-8")
        assert "LiteralName" not in changed
        assert "DESKTOP-ABC123" not in changed
        assert "11111111-2222-3333-4444-555555555555" not in changed
        assert "[REDACTED_USER]" in changed
        assert "[REDACTED_HOST]" in changed


def test_sanitizer_recurses_into_nested_zip_without_changing_other_members(tmp_path: Path) -> None:
    inner_buffer = io.BytesIO()
    with zipfile.ZipFile(inner_buffer, "w", compression=zipfile.ZIP_STORED) as inner:
        inner.writestr("meta.json", json.dumps({"path": r"C:\Users\TestUser\run"}) + "\n")
        inner.writestr("raw.jsonl", '{"answer":"keep exactly"}\n')

    source = tmp_path / "outer.zip"
    output = tmp_path / "outer.sanitized.zip"
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as outer:
        outer.writestr("nested/source.zip", inner_buffer.getvalue())
        outer.writestr("test-output.json", '{"score":1}\n')

    result = sanitize_zip(
        source_zip=source,
        output_zip=output,
        replacements={r"C:\Users\TestUser": r"C:\Users\[REDACTED_USER]"},
    )
    assert result["remaining_matches"] == 0
    assert result["changed_members"] == 1

    with zipfile.ZipFile(source) as before, zipfile.ZipFile(output) as after:
        assert _sha(before.read("test-output.json")) == _sha(after.read("test-output.json"))
        with zipfile.ZipFile(io.BytesIO(after.read("nested/source.zip"))) as inner:
            assert "LiteralName" not in inner.read("meta.json").decode("utf-8")
            assert inner.read("raw.jsonl") == b'{"answer":"keep exactly"}\n'


def test_sanitizer_refuses_binary_member_with_exact_identifier(tmp_path: Path) -> None:
    source = tmp_path / "binary.zip"
    output = tmp_path / "binary.sanitized.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("payload.bin", b"\x00C:\\Users\\TestUser\\binary\xff")

    with pytest.raises(ValueError, match="binary member contains a privacy identifier"):
        sanitize_zip(
            source_zip=source,
            output_zip=output,
            replacements={r"C:\Users\TestUser": r"C:\Users\[REDACTED_USER]"},
        )
    assert not output.exists()


def test_sanitizer_refuses_in_place_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "test.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("a.txt", "safe")
    with pytest.raises(ValueError, match="in-place"):
        sanitize_zip(source_zip=source, output_zip=source, replacements={"x": "y"})
