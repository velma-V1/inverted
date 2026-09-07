from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from .adapters.base import AcquisitionAdapter, CapturedNativeRecord
from .adapters.manifest import (
    AcquiredArtifact,
    ArtifactManifest,
    ArtifactManifestReport,
    capture_artifact_bytes,
    evaluate_artifact_manifest,
)
from .adapters.preflight import PreflightReport
from .journal import HarvestJournal


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "artifact"


class AcquisitionRecorder:
    """Persist exact native acquisition evidence without executing a target agent."""
    def __init__(self, campaign_id: str, run_id: str, task_id: str,
                 adapter: AcquisitionAdapter, run_dir: str | Path,
                 preflight_report: PreflightReport):
        if not preflight_report.ready:
            raise ValueError("preflight must be ready before acquisition recording starts")
        self.campaign_id = campaign_id
        self.run_id = run_id
        self.task_id = task_id
        self.adapter = adapter
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.raw_root = self.run_dir / "01_RAW" / adapter.descriptor.adapter_id
        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.journal = HarvestJournal(self.run_dir / "journal.jsonl", campaign_id)
        self._artifacts: list[AcquiredArtifact] = []
        self._stream_paths: dict[str, Path] = {}

    def stream_path(self, artifact_id: str) -> Path:
        existing = self._stream_paths.get(artifact_id)
        if existing is not None:
            return existing
        path = self.raw_root / "streams" / f"{_safe_name(artifact_id)}.raw"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._stream_paths[artifact_id] = path
        return path

    def record_native_text(self, artifact_id: str, raw_text: str, *,
                           source_path: str, ordinal: int,
                           format: str) -> CapturedNativeRecord:
        record = self.adapter.ingest_native_text(
            raw_text, source_path=source_path, ordinal=ordinal, format=format,
        )
        path = self.stream_path(artifact_id)
        with path.open("ab") as handle:
            handle.write(raw_text.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        self.journal.append("NATIVE_STREAM_RECORD", {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "adapter_id": self.adapter.descriptor.adapter_id,
            "artifact_id": artifact_id,
            "source_path": source_path,
            "ordinal": ordinal,
            "format": format,
            "raw_sha256": record.raw_sha256,
            "content_sha256": record.content_sha256,
            "parse_error": record.parse_error,
        })
        return record

    def record_native_bytes(self, artifact_id: str, raw: bytes, *,
                            source_path: str, ordinal: int,
                            format: str) -> str:
        path = self.stream_path(artifact_id)
        with path.open("ab") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        digest = hashlib.sha256(raw).hexdigest()
        self.journal.append("NATIVE_STREAM_BYTES_RECORD", {
            "run_id": self.run_id, "task_id": self.task_id,
            "adapter_id": self.adapter.descriptor.adapter_id,
            "artifact_id": artifact_id, "source_path": source_path,
            "ordinal": ordinal, "format": format,
            "raw_sha256": digest, "size_bytes": len(raw),
        })
        return digest

    def record_artifact_bytes(self, artifact_id: str, raw: bytes, *,
                              source_path: str, format: str | None = None) -> AcquiredArtifact:
        known = {item.artifact_id for item in self.adapter.descriptor.native_artifacts}
        category = "planned" if artifact_id in known else "discovered"
        source_digest = hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:12]
        filename = f"{source_digest}-{_safe_name(Path(source_path).name or artifact_id)}"
        path = self.raw_root / "artifacts" / category / _safe_name(artifact_id) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"raw artifact path already exists: {path}")
        with path.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        item = capture_artifact_bytes(
            self.adapter, artifact_id, raw,
            source_path=source_path, preserved_path=str(path), format=format,
        )
        self._artifacts.append(item)
        self.journal.append("NATIVE_ARTIFACT_PRESERVED", {
            "run_id": self.run_id, "task_id": self.task_id,
            "adapter_id": self.adapter.descriptor.adapter_id,
            "artifact_id": artifact_id, "source_path": source_path,
            "preserved_path": str(path), "sha256": item.sha256,
            "size_bytes": item.size_bytes, "planned": item.planned,
        })
        return item

    def finalize_manifest(self) -> tuple[ArtifactManifest, ArtifactManifestReport]:
        artifacts = list(self._artifacts)
        formats = {item.artifact_id: item.format for item in self.adapter.descriptor.native_artifacts}
        for artifact_id, path in sorted(self._stream_paths.items()):
            raw = path.read_bytes()
            artifacts.append(capture_artifact_bytes(
                self.adapter, artifact_id, raw,
                source_path=f"stream:{artifact_id}",
                preserved_path=str(path), format=formats.get(artifact_id, "binary"),
            ))
        manifest = ArtifactManifest(
            adapter_id=self.adapter.descriptor.adapter_id,
            system_id=self.adapter.descriptor.system_id,
            run_id=self.run_id, artifacts=tuple(artifacts),
        )
        report = evaluate_artifact_manifest(self.adapter, manifest)
        self.journal.append("ARTIFACT_MANIFEST_EVALUATED", {
            "run_id": self.run_id, "task_id": self.task_id,
            "adapter_id": self.adapter.descriptor.adapter_id,
            "artifact_count": len(manifest.artifacts),
            "complete": report.complete,
            "blockers": list(report.blockers),
            "discovered_artifact_ids": list(report.discovered_artifact_ids),
        })
        return manifest, report
