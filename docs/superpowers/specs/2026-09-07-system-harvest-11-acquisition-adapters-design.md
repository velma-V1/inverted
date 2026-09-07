# SYSTEM_HARVEST_11 Acquisition Adapters Design

## Status

Owner-approved implementation target. This extends the one-pass evidence harvest contract without changing the separate INVERTED causal-testing template.

## Mission

Implement eleven system-specific acquisition adapters that preserve each target system's richest native evidence surface while feeding the common SYSTEM_HARVEST_11 forensic store without lossy coercion.

The adapters do not run the real harvest during implementation. Unit/contract tests use fixtures and synthetic native events only.

## Architecture

Each adapter is a thin native collector around a shared forensic contract:

`TARGET NATIVE SURFACES -> RAW PRESERVATION -> COMMON LINEAGE -> SIDECAR STATE -> ESCALATION CAPSULE -> COVERAGE GATE`

Native artifacts remain immutable and byte-for-byte preservable. Common normalized records reference native artifacts; they never replace them.
## Evidence origin classes

Every declared signal is classified as exactly one of:

- `NATIVE` — produced directly by the target system.
- `SIDECAR` — captured externally without modifying target behavior.
- `DERIVED` — computed from preserved raw evidence with lineage.
- `INSTRUMENTED` — requires target modification/injection; must be explicitly labeled and hashed.
- `INACCESSIBLE` — target cannot expose the datum; requires evidence-backed justification.
- `NOT_APPLICABLE` — concept does not exist for the target; requires reason.

Passive/native capture is preferred. Instrumented mode is allowed only when the missing datum has high decision value and observer effects can be measured.

## Common lifecycle

Every adapter supports the same acquisition phases:

1. `DISCOVER` — executable, version, source, config and capability discovery.
2. `PREFLIGHT` — verify required capture surfaces before inference.
3. `SNAPSHOT_BEFORE` — workspace/git/process/environment/config/instruction state.
4. `LAUNCH` — target-native headless/event/RPC/trajectory mode.
5. `STREAM_CAPTURE` — raw native events plus stdout/stderr and sidecar telemetry.
6. `CHECKPOINT` — continuously persist reconstructable execution state.
7. `FAILURE_BOUNDARY` — freeze the 25-section escalation capsule before recovery mutation.
8. `CONTINUE_ESCALATE` — hand exact boundary to the escalation model.
9. `SNAPSHOT_AFTER` — state/files/git/process/resource delta.
10. `EXPORT` — native artifacts, lineage graph, manifests and coverage report.
## Frozen adapter registry

Exactly eleven adapter IDs are registered:

`codex`, `claude_code`, `prime_agent`, `pi`, `oh_my_cli`, `swe_agent`, `mini_swe_agent`, `aider`, `aegisevo`, `openhands`, `kimi_cli`.

Registry order must map exactly to the frozen campaign system order. Missing, extra, duplicate or aliased adapters fail validation.

## Native surfaces to preserve

- **Codex:** structured CLI/event output when available, session artifacts, command/file/MCP/web/task events, stderr diagnostics.
- **Claude Code / Agent SDK:** lifecycle hooks, transcript/session artifacts, tool events, permission decisions, compaction/session metadata when exposed.
- **Prime Agent:** RPC/ACP/JSONL streams, session persistence, command responses, streamed agent/tool events.
- **Pi:** RPC/JSON modes, JSONL sessions, AgentSession/RPC events, state/compact/abort events, extension/tool activity.
- **oh-my-cli:** durable JSONL sessions, versioned JSON event streams, checkpoints, summaries/scorecards, policy/approval/tool/provider/MCP evidence archives.
- **SWE-agent:** `.traj` trajectory, logs, config, action/observation/state/response fields, hooks and replay metadata.
- **mini-SWE-agent:** `.traj.json` full history, config, messages, model statistics, exit/result metadata.
- **Aider:** input/chat/LLM histories, repo-map/context artifacts, diffs, git state, model/config metadata and analytics where locally exposed.
- **AegisEvo:** deterministic demo/evidence/lineage/control-plane telemetry plus a required `INSTRUMENTED` provider-neutral live-model-gateway stream; the adapter must not misclassify current live-model capability as `NOT_APPLICABLE`, and it must not invent an unverified live-harness CLI.
- **OpenHands:** EventStream/trajectory/session events, actions/observations, runtime state, tool execution, conversation/state exports where exposed.
- **Kimi CLI:** lifecycle hooks, session/context events, tool events, compaction events, permission/notification state and CLI artifacts.

System-specific adapters may add new surfaces at discovery time; the registry schema is a floor, not a ceiling.
## Shared passive sidecar

Every adapter composes with a shared sidecar that can capture, without target modification:

- executable/version/source identity;
- working directory and workspace tree manifest;
- git HEAD, branch, index, dirty/untracked state and diffs;
- filesystem before/after content hashes and mutation journal;
- process tree, command line, exit status and stdout/stderr;
- environment-variable names plus redacted value fingerprints;
- selected runtime/resource telemetry;
- timestamps and monotonic event ordering;
- task, run, session, model and escalation lineage IDs.

Secret values are never persisted in plaintext. Redaction preserves type, position and stable fingerprint when safe.

## Adapter contract

Each adapter must expose:

- immutable `AdapterDescriptor`;
- declared native artifacts and event surfaces;
- supported execution/capture modes;
- evidence-origin classification for every surface;
- required environment/config discovery hints;
- a fixture parser that preserves raw native records;
- `build_acquisition_plan(...)` producing launch/capture instructions without executing them;
- channel-coverage declaration against the campaign's mandatory evidence channels;
- preflight blockers for unavailable required surfaces;
- source/reference provenance for claims about the adapter's capture interface.

A plan is declarative. Constructing or validating an adapter must never launch a model, network request, shell command or target agent.
## Physical acquisition integrity additions

Preflight is a hard gate: the installed/frozen target version must prove required artifact classes and acquisition surfaces exist before any inference-bearing run begins.

Native stream acquisition preserves both exact wire bytes/text and decoded payloads. Parser failures never delete or repair the original record. Raw stream/artifact writes are flushed and fsync-backed before the journal records their hashes.

Artifact manifests operate on file identity, not merely artifact class, because one native evidence class may legitimately emit many files. Unknown emitted artifacts are retained and surfaced as discoveries for gap closure.

The observability matrix is generated from executable adapter declarations so later analysts can distinguish native, sidecar, derived and instrumented evidence without reconstructing adapter code history.
