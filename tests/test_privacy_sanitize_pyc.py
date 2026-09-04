from __future__ import annotations

import importlib.util
import io
import marshal
from pathlib import Path
import struct
import zipfile

from inverted.harvest_d.privacy_sanitize_test_zip import sanitize_zip


def _make_pyc_with_filename(filename: str) -> bytes:
    code = compile("VALUE = 1\n", filename, "exec")
    header = importlib.util.MAGIC_NUMBER + struct.pack("<III", 0, 0, 0)
    return header + marshal.dumps(code)


def test_pyc_embedded_profile_path_is_sanitized_without_changing_file_length(tmp_path: Path) -> None:
    source = tmp_path / "pyc.zip"
    output = tmp_path / "pyc.sanitized.zip"
    pyc = _make_pyc_with_filename(r"C:\Users\TestUser\inverted\tests\test_x.py")

    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("repo/tests/__pycache__/test_x.cpython-314.pyc", pyc)
        archive.writestr("evidence.json", b'{"score":1}\n')

    result = sanitize_zip(
        source_zip=source,
        output_zip=output,
        replacements={r"C:\Users\TestUser": r"C:\Users\[REDACTED_USER]"},
    )

    assert result["remaining_matches"] == 0
    with zipfile.ZipFile(source) as before, zipfile.ZipFile(output) as after:
        old_pyc = before.read("repo/tests/__pycache__/test_x.cpython-314.pyc")
        new_pyc = after.read("repo/tests/__pycache__/test_x.cpython-314.pyc")
        assert len(new_pyc) == len(old_pyc)
        assert b"C:\\Users\\TestUser" not in new_pyc
        assert after.read("evidence.json") == before.read("evidence.json")


def test_non_pyc_binary_with_identifier_still_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "binary.zip"
    output = tmp_path / "binary.sanitized.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("payload.bin", b"\x00C:\\Users\\TestUser\\binary\xff")

    try:
        sanitize_zip(
            source_zip=source,
            output_zip=output,
            replacements={r"C:\Users\TestUser": r"C:\Users\[REDACTED_USER]"},
        )
    except ValueError as exc:
        assert "binary member contains a privacy identifier" in str(exc)
    else:
        raise AssertionError("expected non-pyc binary member to fail closed")
