# SYSTEM_HARVEST_11 Production Execution Backend Design

## Goal

Build the first live-capable execution layer beneath the existing `CampaignOrchestrator` without weakening any evidence, preflight, resume, escalation, or completion invariant.

The backend may eventually launch the 11 frozen external systems, but this implementation phase must prove all production execution mechanics against synthetic local stand-ins only. No real agent/model task submission is part of this phase.

## Architectural boundary

The existing authority split remains unchanged:

- `CampaignOrchestrator` owns scheduling, execution IDs, semantic state, verification, escalation, and advancement.
- adapters own native launch declarations, observable surfaces, and expected artifacts.
- `AcquisitionRecorder` owns lossless persisted evidence.
- the new production backend owns only process/session execution and raw observable transport.

The new layer is:

`CampaignOrchestrator → ProductionExecutionBackend → ExecutionDriverRegistry → ProcessEngine → target process`

No driver or process engine may mark a cell correct, complete, skipped, or terminal.
## Arming state machine

Execution capability is mechanically gated by `ArmState`:

`BUILD → DRY_RUN → PREFLIGHT_PROBE → ARMED_LIVE`

Rules:

- `BUILD`: construction/introspection only; target executable spawn forbidden.
- `DRY_RUN`: launch envelopes may be resolved and validated; target executable spawn forbidden.
- `PREFLIGHT_PROBE`: only explicitly allowlisted non-inference identity/help/version probes may spawn.
- `ARMED_LIVE`: task-bearing execution may spawn, but only after all production preflight gates pass.

A backend created in any state below `ARMED_LIVE` must reject task-bearing execution before process creation.

The test suite must prove that BUILD/DRY_RUN cannot spawn even when given a valid executable, and that PREFLIGHT_PROBE rejects task text/model-request arguments.

There is no implicit promotion between states. Arming must be explicit, journaled by the caller, and represented in the launch envelope.

## Launch envelope

Every executable boundary is frozen into an immutable `LaunchEnvelope` before spawn.

Required fields include campaign/cell/execution/escalation IDs, adapter/system/mode IDs, exact argv tuple, cwd, fixture/workspace hashes, model/runtime identity, perturbations, timeout/stall policy, capture destinations, permission policy, arm state, source/version identity, environment inventory/fingerprints, and deterministic idempotency key.
Launch-envelope validation rejects unresolved `{placeholder}` tokens, empty argv, relative/unknown workspace paths, unhashed fixtures, undeclared adapter modes, shell-string commands, missing capture roots, duplicate idempotency keys, or an arm state insufficient for the requested action.

`LaunchSpec.argv` is expanded positionally into an argument vector. The backend must never concatenate it into a shell command. Shell execution is forbidden unless a future adapter explicitly declares a shell-required mode and a separate evidence-backed design approves it.

The envelope itself is canonical-JSON hashed and persisted before spawn. Any later process observation references that envelope hash.

## Workspace isolation and leases

Every executable cell receives a private content-addressed workspace materialized from its frozen fixture.

A `WorkspaceLease` contains source fixture path/hash, materialized workspace path, baseline tree hash, lease ID, owning cell/execution IDs, creation timestamp, and release/final-state metadata.

Requirements:

- no two mutable cells may share one lease;
- the fixture is copied/materialized, never mutated in place;
- baseline tree hash is verified before launch;
- after-state tree hash and changed-path inventory are captured before lease release;
- interrupted/recovery-uncertain leases remain preserved until reconciliation;
- cleanup is never required for evidence correctness.

The process engine may execute only inside the envelope's leased workspace or an explicitly declared immutable tool/runtime directory.

## Environment and secret handling

The persistent launch record stores environment variable names, presence, classification, and stable fingerprints—not raw secret values.
Secrets are injected only into the child environment immediately before spawn. Secret-bearing variables must be declared by name/classification and receive a stable redaction token plus salted fingerprint for lineage.

If stdout/stderr/native artifacts echo a declared secret, persistent capture must redact the secret before disk write while retaining a deterministic marker, location/order, source stream, and redaction lineage. The unredacted secret must never be persisted merely to improve fidelity.

Non-secret environment values may be persisted when allowed by policy; potentially identifying or sensitive values use the same redaction/fingerprint mechanism.

## Process engine

`ProcessEngine` is the only component allowed to create or control an OS process.

It accepts a validated `LaunchEnvelope` and returns ordered `ProcessObservation` records plus a `ProcessResult`.

The engine must:

- use direct argv process creation with `shell=False`;
- set explicit cwd and child environment;
- open raw capture sinks before task/stdin delivery;
- drain stdout and stderr concurrently from byte zero;
- preserve stream order per source with monotonic ordinals/timestamps;
- record PID/start identity/exit code/signal/termination reason;
- capture stdin bytes supplied by the driver after redaction policy;
- expose liveness/heartbeat/resource samples when observable;
- enforce declared wall-clock and no-progress bounds without assigning semantic correctness;
- distinguish normal exit, timeout/stall signal, explicit cancellation, and infrastructure interruption.

Process-engine tests use synthetic Python stand-ins only.
## Raw-firehose ordering

Before the driver sends task text or any inference-triggering RPC message, the engine must prove stdout/stderr/native capture destinations are created and durable.

For each observable record:

1. receive source bytes;
2. apply only mandatory secret/privacy redaction;
3. persist the resulting exact source bytes and hash;
4. emit a `BackendObservation` referencing the source identity and ordinal;
5. only afterward may higher layers parse or classify it.

Parser errors, malformed JSONL, partial UTF-8 fragments, unknown native events, duplicate-looking events, and unexpected files are evidence and must not be filtered before persistence.

## Execution drivers

Drivers translate adapter-native launch/session semantics into `ProcessEngine` operations. They have no scheduling or correctness authority.

Driver families:

- `OneShotStructuredDriver`: Codex, Claude Code, Kimi CLI, OpenHands.
- `RpcSessionDriver`: Prime Agent, Pi.
- `TrajectoryDriver`: SWE-agent, mini-SWE-agent.
- `HistoryEditDriver`: Aider.
- `EvidenceControlPlaneDriver`: AegisEvo.
- `DurableEvidenceDriver`: oh-my-cli.

All 11 systems still receive individual driver descriptors/modules so resume commands, stdin protocol, session discovery, artifact watchers, and native limitations remain explicit and inspectable.

A driver must report native resume support as `NATIVE`, `RECONSTRUCTABLE`, or `UNAVAILABLE`; it may not invent a resumable session when the target does not expose one.
## Resume, escalation, and crash reconciliation

The production backend implements the existing `ExecutionBackend` methods: `execute`, `resume`, and `continue_from_escalation`.

`resume` must preserve the original logical execution ID and escalation level. It may attach to a living process/session, invoke a target-native resume command, or reconstruct from a preserved workspace/session artifact according to the driver's declared resume capability.

`continue_from_escalation` receives the verified capsule ID and selected model identity. It must consume the capsule-derived continuation package and preserve `CONTINUE_FROM_FAILURE_BOUNDARY`; it cannot silently replace the task with a fresh baseline prompt.

When a semantic failure/stall boundary is declared upstream, the engine/driver must stop submitting new actions, drain already-produced output, capture current process/session/workspace state, and leave enough state intact for capsule construction.

Where OS/runtime support allows safe suspension, the process may be suspended while the capsule is persisted. Suspension is an optimization, not an evidence requirement; unsupported suspension is recorded explicitly.

Crash ambiguity is handled conservatively. If the harness cannot prove whether an external task/action was accepted before failure, it must not resend automatically. The backend returns an infrastructure/reconciliation state that drives the existing orchestrator to `RECOVERY_UNCERTAIN` until native process/session/artifact evidence resolves what occurred.

## Production backend

`ProductionExecutionBackend` binds `ExecutionCell` metadata, adapter descriptors, driver registry, workspace leases, arming state, environment policy, and process engine into the existing `ExecutionBackend` protocol.

The backend itself must not import provider SDKs or model APIs. Target communication occurs through the adapter/driver's declared executable/native protocol.
## Driver registry and applicability

The production driver registry is frozen to the same 11 adapter IDs as `ADAPTER_IDS`. Registry validation requires one driver descriptor per adapter, a supported launch mode present in the adapter descriptor, explicit resume capability, and declared artifact-watch strategy.

A missing or stale driver blocks live readiness for that system; the backend must not fall back to a generic shell command.

AegisEvo remains special: deterministic-fixture execution may use its declared cargo demo path, while live-model-gateway execution requires an explicitly instrumented driver mode and cannot be inferred from the deterministic mode.

## Synthetic acceptance harness

No real agent executable is used for production-backend acceptance. A local synthetic target executable must simulate:

- stdout/stderr interleaving;
- JSONL and malformed records;
- task-on-stdin behavior;
- session handle emission and native resume;
- delayed/no-progress behavior;
- nonzero exit and abrupt disappearance;
- artifact creation/mutation;
- echoed secret material requiring redaction;
- partial output before interruption;
- duplicate invocation/idempotency pressure.

All 11 driver descriptors are exercised against compatible synthetic stand-ins so driver selection, launch-envelope expansion, capture, artifact discovery, and resume classification are tested without invoking external agents.

## Live-readiness gate

This implementation may report `PRODUCTION_BACKEND_READY` only when the synthetic suite, complete `system_harvest` suite, package compile/static audit, driver registry validation, and full repository regression are green.

It may not report `LIVE_HARVEST_READY` or start the real campaign. That requires a separate live-readiness audit of installed executable versions, auth state, permissions, cost/budget controls, model selections, fixtures, and per-system preflight observations.
## TDD acceptance requirements

The production-backend implementation must prove at minimum:

- BUILD and DRY_RUN cannot spawn a target process;
- PREFLIGHT_PROBE runs only explicit non-inference probes;
- unresolved launch placeholders or shell strings block launch;
- launch envelope and workspace baseline are durable before spawn;
- capture sinks are open before task/stdin delivery;
- stdout/stderr bytes are preserved in source order with hashes;
- declared secrets are never persisted plaintext, including echoed output;
- timeouts/stalls are execution outcomes, not semantic correctness verdicts;
- infrastructure resume keeps the same logical execution ID/level;
- ambiguous crash state cannot trigger blind resend;
- escalation continuation consumes capsule identity and preserves boundary-continuation semantics;
- duplicate idempotency keys cannot launch twice;
- mutable workspaces are never shared across cells;
- unexpected native artifacts remain discoveries;
- all 11 driver descriptors validate against the frozen adapter registry;
- synthetic stand-ins exercise every driver family and all 11 registered drivers;
- implementation/testing launches zero real harvest agents or model-provider calls.

## Non-goals

This phase does not run the 32-case behavioral battery, execute the 12 perturbations against real systems, select production escalation models, spend model/API budget, modify the INVERTED causal system-testing template, or repair unrelated concurrent repository work.

The outcome is a hardened live-capable backend that remains mechanically disarmed until a separate live-readiness phase explicitly arms it.
