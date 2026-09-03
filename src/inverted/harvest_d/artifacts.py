from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

class ArtifactWriter:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def write_json(self, name: str, value: object) -> Path:
        path = self._path(name)
        path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def write_jsonl(self, name: str, rows: Iterable[object]) -> Path:
        path = self._path(name)
        with path.open("w", encoding="utf-8", newline="") as f:
            for row in rows: f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
        return path

    def write_csv(self, name: str, rows: Iterable[Mapping[str, object]], *, fieldnames: Sequence[str]) -> Path:
        path = self._path(name)
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(fieldnames)); writer.writeheader()
            for row in rows: writer.writerow(row)
        return path

    def write_text(self, name: str, text: str) -> Path:
        path = self._path(name); path.write_text(text, encoding="utf-8"); return path

    def finalize(self) -> Path:
        rows = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.name == "SHA256SUMS.csv": continue
            data = path.read_bytes()
            rows.append({"file": path.relative_to(self.root).as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        return self.write_csv("SHA256SUMS.csv", rows, fieldnames=("file", "bytes", "sha256"))
