from __future__ import annotations

import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "arm"


class DockerWorkspace:
    def __init__(self, workspace: Path, arm: str, image: str = "alpine:3.22", network: str = "none"):
        self.workspace = Path(workspace).resolve()
        self.arm = arm
        self.image = image
        self.network = network
        self.name = f"ibrain-{_slug(arm)}-{uuid.uuid4().hex[:8]}"
        self.started = False

    def __enter__(self):
        self.start()
        return self

    def start(self) -> None:
        if self.started:
            return
        command = [
            "docker", "run", "-d", "--rm",
            "--name", self.name,
            "--network", self.network,
            "--mount", f"type=bind,source={self.workspace},target=/workspace",
            "-w", "/workspace",
            self.image, "sleep", "infinity",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if completed.returncode != 0:
            raise RuntimeError(f"docker start failed: {completed.stderr.strip()}")
        self.started = True

    def exec(self, command: list[str], timeout: int = 60) -> ExecResult:
        if not self.started:
            raise RuntimeError("container is not started")
        completed = subprocess.run(
            ["docker", "exec", self.name, *command],
            capture_output=True, text=True, timeout=timeout,
        )
        return ExecResult(completed.returncode, completed.stdout, completed.stderr)

    def stop(self) -> None:
        if not self.started:
            return
        subprocess.run(
            ["docker", "rm", "-f", self.name],
            capture_output=True, text=True, timeout=60,
        )
        self.started = False

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False
