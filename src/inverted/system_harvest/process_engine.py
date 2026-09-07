from __future__ import annotations

import hashlib
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping

from .environment import EnvironmentPolicy, RedactionEvent
from .launch import LaunchEnvelope, LaunchEnvelopeError, validate_launch_envelope


class ProcessTermination(str, Enum):
    EXITED = "EXITED"
    NONZERO_EXIT = "NONZERO_EXIT"
    TIMEOUT = "TIMEOUT"
    NO_PROGRESS = "NO_PROGRESS"
    CANCELLED = "CANCELLED"
    INFRA_INTERRUPTED = "INFRA_INTERRUPTED"


@dataclass(frozen=True)
class ProcessSessionHandle:
    pid: int
    execution_id: str
    envelope_sha256: str


@dataclass(frozen=True)
class ProcessObservation:
    source: str
    source_ordinal: int
    global_ordinal: int
    persisted_bytes: bytes
    persisted_sha256: str
    redactions: tuple[RedactionEvent, ...]
    monotonic_ns: int

@dataclass(frozen=True)
class ProcessResult:
    termination: ProcessTermination
    exit_code: int | None
    pid: int | None
    observations: tuple[ProcessObservation, ...]
    stdout_capture_path: str
    stderr_capture_path: str
    capture_opened_before_stdin: bool
    semantic_verdict: None = None


class _StreamingRedactor:
    def __init__(self, policy: EnvironmentPolicy, env: Mapping[str, str], source: str):
        snapshot = policy.snapshot(env)
        self.source = source
        self.patterns: list[tuple[str, bytes, bytes]] = []
        for name in policy.secret_names:
            value = str(env.get(name, ""))
            if value:
                self.patterns.append((name, value.encode("utf-8"), snapshot.redaction_tokens[name].encode("utf-8")))
        self.patterns.sort(key=lambda item: len(item[1]), reverse=True)
        self.max_len = max((len(item[1]) for item in self.patterns), default=0)
        self.buffer = b""
        self.raw_offset = 0

    def feed(self, chunk: bytes, *, final: bool = False) -> tuple[bytes, tuple[RedactionEvent, ...]]:
        self.buffer += chunk
        output = bytearray()
        events: list[RedactionEvent] = []
        index = 0
        while index < len(self.buffer):
            matched = None
            for name, needle, token in self.patterns:
                if self.buffer.startswith(needle, index):
                    matched = (name, needle, token)
                    break
            if matched is not None:
                name, needle, token = matched
                fingerprint = hashlib.sha256(token).hexdigest()[:12]
                token_text = token.decode("utf-8")
                events.append(RedactionEvent(name, token_text, self.raw_offset + index, len(needle), self.source))
                output.extend(token)
                index += len(needle)
                continue
            remaining = len(self.buffer) - index
            if not final and self.max_len and remaining < self.max_len:
                break
            output.append(self.buffer[index])
            index += 1
        self.raw_offset += index
        self.buffer = self.buffer[index:]
        if final and self.buffer:
            output.extend(self.buffer)
            self.raw_offset += len(self.buffer)
            self.buffer = b""
        return bytes(output), tuple(events)


class ProcessEngine:
    def _validate_runnable(self, envelope: LaunchEnvelope) -> None:
        report = validate_launch_envelope(envelope)
        if not report.valid:
            raise LaunchEnvelopeError("; ".join(report.blockers))
        if envelope.action_kind == "TASK" and not envelope.arm_state.task_execution_allowed:
            raise LaunchEnvelopeError("task execution is not armed")
        if envelope.action_kind == "PREFLIGHT_PROBE" and not envelope.arm_state.probe_execution_allowed:
            raise LaunchEnvelopeError("preflight probe is not armed")

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        try:
            process.terminate()
            process.wait(timeout=1.0)
        except Exception:
            try:
                process.kill()
                process.wait(timeout=1.0)
            except Exception:
                pass

    def run(self, envelope: LaunchEnvelope, *, environment: Mapping[str, str], stdin_bytes: bytes,
            environment_policy: EnvironmentPolicy, read_chunk_size: int = 4096) -> ProcessResult:
        self._validate_runnable(envelope)
        if read_chunk_size <= 0:
            raise ValueError("read_chunk_size must be positive")
        capture_root = Path(envelope.run_dir) / "process"
        capture_root.mkdir(parents=True, exist_ok=True)
        stdout_path = capture_root / "stdout.bin"
        stderr_path = capture_root / "stderr.bin"
        observations: list[ProcessObservation] = []
        observation_lock = threading.Lock()
        activity_lock = threading.Lock()
        global_counter = [0]
        last_activity = [time.monotonic()]

        def persist(source: str, source_ordinal: int, data: bytes,
                    redactions: tuple[RedactionEvent, ...], sink) -> None:
            if not data:
                return
            sink.write(data)
            sink.flush()
            os.fsync(sink.fileno())
            with observation_lock:
                ordinal = global_counter[0]
                global_counter[0] += 1
                observations.append(ProcessObservation(
                    source=source, source_ordinal=source_ordinal, global_ordinal=ordinal,
                    persisted_bytes=data, persisted_sha256=hashlib.sha256(data).hexdigest(),
                    redactions=redactions, monotonic_ns=time.monotonic_ns(),
                ))

        with stdout_path.open("wb") as stdout_sink, stderr_path.open("wb") as stderr_sink:
            capture_ready = not stdout_sink.closed and not stderr_sink.closed
            try:
                process = subprocess.Popen(
                    envelope.argv, cwd=envelope.cwd, env={str(k): str(v) for k, v in environment.items()},
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    shell=False, bufsize=0,
                )
            except OSError:
                return ProcessResult(
                    ProcessTermination.INFRA_INTERRUPTED, None, None, (), str(stdout_path),
                    str(stderr_path), capture_ready,
                )

            def reader(pipe, sink, source: str) -> None:
                redactor = _StreamingRedactor(environment_policy, environment, source)
                source_ordinal = 0
                while True:
                    chunk = pipe.read(read_chunk_size)
                    if not chunk:
                        break
                    with activity_lock:
                        last_activity[0] = time.monotonic()
                    data, events = redactor.feed(chunk)
                    if data:
                        persist(source, source_ordinal, data, events, sink)
                        source_ordinal += 1
                data, events = redactor.feed(b"", final=True)
                if data:
                    persist(source, source_ordinal, data, events, sink)
            stdout_thread = threading.Thread(target=reader, args=(process.stdout, stdout_sink, "stdout"), daemon=True)
            stderr_thread = threading.Thread(target=reader, args=(process.stderr, stderr_sink, "stderr"), daemon=True)
            stdout_thread.start()
            stderr_thread.start()

            try:
                if process.stdin is not None:
                    if stdin_bytes:
                        process.stdin.write(stdin_bytes)
                        process.stdin.flush()
                    process.stdin.close()
            except (BrokenPipeError, OSError):
                pass

            started = time.monotonic()
            termination: ProcessTermination | None = None
            while True:
                code = process.poll()
                if code is not None:
                    break
                now = time.monotonic()
                if now - started >= envelope.timeout_seconds:
                    termination = ProcessTermination.TIMEOUT
                    self._terminate(process)
                    break
                if envelope.no_progress_seconds is not None:
                    with activity_lock:
                        idle_for = now - last_activity[0]
                    if idle_for >= envelope.no_progress_seconds:
                        termination = ProcessTermination.NO_PROGRESS
                        self._terminate(process)
                        break
                time.sleep(0.01)

            stdout_thread.join(timeout=2.0)
            stderr_thread.join(timeout=2.0)
            exit_code = process.poll()
            if exit_code is None:
                self._terminate(process)
                exit_code = process.poll()
                if termination is None:
                    termination = ProcessTermination.INFRA_INTERRUPTED
            if termination is None:
                termination = ProcessTermination.EXITED if exit_code == 0 else ProcessTermination.NONZERO_EXIT

        ordered = tuple(sorted(observations, key=lambda item: item.global_ordinal))
        return ProcessResult(
            termination, exit_code, process.pid, ordered,
            str(stdout_path), str(stderr_path), capture_ready,
        )
