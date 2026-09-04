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


def test_clean_nested_zip_remains_byte_identical_when_other_member_is_redacted(tmp_path: Path) -> None:
    inner_buffer = io.BytesIO()
    with zipfile.ZipFile(inner_buffer, "w", compression=zipfile.ZIP_DEFLATED) as inner:
        inner.writestr("raw.jsonl", '{"answer":"keep exactly"}\n')
    clean_nested = inner_buffer.getvalue()

    source = tmp_path / "outer-clean-nested.zip"
    output = tmp_path / "outer-clean-nested.sanitized.zip"
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as outer:
        outer.writestr("nested/source.zip", clean_nested)
        outer.writestr("meta.json", json.dumps({"path": r"C:\Users\TestUser\run"}) + "\n")

    sanitize_zip(
        source_zip=source,
        output_zip=output,
        replacements={r"C:\Users\TestUser": r"C:\Users\[REDACTED_USER]"},
    )

    with zipfile.ZipFile(output) as archive:
        assert archive.read("nested/source.zip") == clean_nested


def test_extensionless_git_reflog_is_sanitized_as_text(tmp_path: Path) -> None:
    source = tmp_path / "git-log.zip"
    output = tmp_path / "git-log.sanitized.zip"
    reflog = b"0000000 1111111 TestUser <owner@example.com> 1700000000 -0400\tcommit from C:\\Users\\TestUser\\inverted\n"
    git_object = b"\x00C:\\Users\\TestUser\\must-not-be-rewritten\xff"

    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("repo/.git/logs/HEAD", reflog)
        archive.writestr("repo/.git/objects/aa/binary", git_object)

    with pytest.raises(ValueError, match="binary member contains a privacy identifier"):
        sanitize_zip(
            source_zip=source,
            output_zip=output,
            replacements={
                r"C:\Users\TestUser": r"C:\Users\[REDACTED_USER]",
                "owner@example.com": "[REDACTED_GIT_EMAIL]",
            },
        )

    # Remove the deliberately unsafe Git object and prove the extensionless reflog itself is redacted.
    source_ok = tmp_path / "git-log-text-only.zip"
    output_ok = tmp_path / "git-log-text-only.sanitized.zip"
    with zipfile.ZipFile(source_ok, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("repo/.git/logs/HEAD", reflog)

    result = sanitize_zip(
        source_zip=source_ok,
        output_zip=output_ok,
        replacements={
            r"C:\Users\TestUser": r"C:\Users\[REDACTED_USER]",
            "owner@example.com": "[REDACTED_GIT_EMAIL]",
        },
    )
    assert result["remaining_matches"] == 0
    with zipfile.ZipFile(output_ok) as archive:
        text = archive.read("repo/.git/logs/HEAD").decode("utf-8")
    assert r"C:\Users\TestUser" not in text
    assert "owner@example.com" not in text
    assert "[REDACTED_USER]" in text
    assert "[REDACTED_GIT_EMAIL]" in text


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
