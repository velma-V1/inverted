# SYSTEM_HARVEST_11 Acquisition Orchestrator Design

## Goal

Build the deterministic campaign runner that executes the frozen 11-system harvest through the existing adapter, recorder, journal, escalation, coverage, and completion contracts.

The orchestrator owns scheduling and state progression only. It must not redefine evidence formats, retry/escalation semantics, adapter capture surfaces, or completion authority already implemented elsewhere.

## Core architecture

The runner is event-sourced and split into four responsibilities:

1. `CampaignSchedule` freezes every required execution cell before inference.
2. `CampaignOrchestrator` advances cells through an explicit state machine.
3. `ExecutionBackend` performs one target-system execution boundary and emits observable events.
4. Existing `AcquisitionRecorder`, journal, escalation-capsule, coverage, and completion components remain authoritative for evidence and closure.

Initial implementation uses only a deterministic fake backend. Real subprocess/API backends are out of scope until orchestration invariants pass without live inference.
## Frozen execution schedule

The campaign must not infer its work dynamically from list position or filesystem discovery. A pre-run `ScenarioManifest` expands into immutable `ExecutionCell` records.

Each cell carries stable identifiers for:

- system and adapter;
- behavioral scenario;
- zero or more declared perturbations;
- workspace/fixture identity and immutable input hash;
- task contract and original instructions;
- active ingredients/layers;
- adapter execution mode;
- target model/runtime identity when applicable;
- verification contract;
- seed/configuration identity;
- required native artifacts/evidence channels;
- escalation route identity.

The schedule compiler rejects duplicate cell IDs, unknown systems/cases/perturbations, missing frozen behavioral cases, missing required perturbation coverage, unhashed fixtures, or cells with no verification contract.

### Applicability coverage

For every one of the 11 systems × every one of the 32 frozen behavioral cases, the scenario manifest must contain either an executable baseline cell or an explicit evidence-backed `NOT_APPLICABLE`/`INACCESSIBLE` compatibility record. Omission is forbidden.

Likewise, every one of the 12 frozen perturbation classes must have declared matched coverage for every system where the perturbation is semantically applicable, or an explicit evidence-backed incompatibility record. Applicability records are themselves part of the immutable schedule and may not be invented after seeing results merely to avoid a difficult case.

This makes the minimum schedule coverage auditable instead of relying on prose such as “where compatible.”
## Cell state machine

A cell may occupy only these durable states:

`PLANNED → PREFLIGHT_READY → SNAPSHOT_BEFORE_CAPTURED → EXECUTING → VERIFYING → SNAPSHOT_AFTER_CAPTURED → COMPLETE`

Failure paths are explicit:

- `EXECUTING → INFRA_INTERRUPTED → EXECUTING` resumes the same logical execution identity.
- `VERIFYING → FAILURE_BOUNDARY_CAPTURE → ESCALATION_PENDING → EXECUTING` continues the same task at the next escalation level.
- `EXECUTING → STALL_BOUNDARY_CAPTURE → ESCALATION_PENDING → EXECUTING` uses the same escalation path.
- Any unresolved evidence/manifest/gap state leaves the cell nonterminal.

`COMPLETE` is legal only after post-state capture, verification, required artifact-manifest validation, evidence-channel coverage, and escalation-chain verification when escalation occurred.

No state transition may be inferred from process exit alone. Every transition must be represented by a durable journal event.
## Evidence-first execution ordering

The orchestrator applies a strict write-ahead rule:

1. receive raw observable bytes/event from backend;
2. persist exact raw evidence and hash;
3. append lineage/journal record;
4. only then parse, normalize, classify, verify, or mutate scheduler state.

Parser failure never destroys the source record. Unknown event types and unexpected artifacts are preserved as discoveries.

No recovery action, retry-like action, escalation prompt, workspace reset, or next-cell transition may occur before the causally prior raw evidence is durably recorded.

The one-pass evidence standard remains an evidence-severity rule, not a prohibition on scientifically justified future replay or rerun.
## Execution backend contract

`ExecutionBackend` is injected into the orchestrator and has no scheduling authority. It may only:

- start or resume one declared cell execution;
- emit ordered observable stream records and sidecar observations;
- report explicit infrastructure interruption, stall signal, or process completion;
- expose backend/session handles needed for exact resume;
- accept a validated escalation continuation package.

The orchestrator owns execution IDs, state transitions, escalation levels, and advancement. A backend cannot mark a cell complete.

The first implementation uses `FakeExecutionBackend` scripts that deterministically emit success, incorrect result, stall, interruption, malformed records, discoveries, and recursive escalation sequences. No production subprocess or network backend is introduced in this phase.
## Verification and semantic failure authority

Backend exit status is evidence, not correctness authority. Each scenario supplies an explicit `VerificationContract` defining deterministic checks, expected postconditions, permitted semantic judges when unavoidable, and evidence required for the verdict.

A cell becomes `INCORRECT` only from a recorded verifier verdict. If a semantic model judge is used, its full observable request/response/configuration is captured as evidence and the verdict remains separately labeled model-derived.

Verification itself is part of the trajectory:

`ACTION → EXPECTED POSTCONDITION → OBSERVED POSTCONDITION → VERIFIER → VERDICT`

Missing or indeterminate verification does not become PASS; it opens a coverage/gap item and blocks cell completion.
## Stall detection

Stall policy is frozen before a cell starts. It may use declared heartbeat/event silence, repeated identical action signatures, no-progress state hashes, backend watchdog signals, or explicit target-system stall events.

Every stall threshold and detector input is stored in the cell definition. A stall verdict records:

- last-progress event and monotonic timestamp;
- detector rule and threshold;
- repeated/no-progress evidence;
- process/backend liveness state;
- pending action and task position.

A stall verdict triggers the same failure-boundary capsule path as an incorrect result. The harness never kills or mutates the execution before the boundary evidence is durably captured.
## Escalation continuation

On `INCORRECT` or `STALL`, the orchestrator must:

1. freeze pre/post failure state and all 25 required capsule sections;
2. build and verify the `EscalationCapsule`;
3. persist the capsule and its content hash;
4. record the escalation-router decision;
5. only then allow the next escalation model/backend continuation.

`EscalationRouter` is injected and deterministic for a given recorded state. Its decision record contains eligible models, selected model, reason/rule, capability tier, runtime identity, and parent capsule ID.

Recursive failure creates a child capsule linked to the previous capsule. The only normal escalation resume mode is the existing literal contract `CONTINUE_FROM_FAILURE_BOUNDARY`. Escalation never implies a clean restart. A restart is legal only when captured evidence proves continuation impossible or unsafe; that restart decision becomes an explicit causal event.
## Crash-safe resume and idempotency

Every orchestration mutation uses write-ahead journal semantics. The journal contains stable campaign/cell/execution/event IDs and sufficient state to reconstruct the scheduler after process or machine interruption.

On restart the orchestrator replays the journal, verifies sequence/hash integrity, reconstructs the last durable cell state, and resumes the same logical execution identity.

Idempotency keys prevent duplicated launches, duplicated escalation capsules, duplicated artifact finalization, or double advancement when a crash occurs between an external action and local acknowledgement.

Infrastructure interruption is not semantic failure and does not increment escalation level. If an external action's completion cannot be established after restart, the cell becomes `RECOVERY_UNCERTAIN` and remains incomplete until state reconciliation proves whether the action occurred.
## Global preflight and non-interactive readiness

Before the first inference-capable cell launches, global preflight must prove:

- all 11 adapters are registered and individually preflight-ready;
- required executables/versions/source identities are frozen;
- credentials/auth state needed by the declared modes are available without storing secrets;
- workspaces/fixtures exist and their hashes match the schedule;
- disk capacity and evidence destinations are writable;
- journal/capsule/artifact integrity checks work;
- required verifier dependencies are available;
- escalation routes resolve to declared models/backends;
- interactive permission/confirmation behavior has a predeclared harness policy.

Any blocker prevents campaign launch before compute is spent. Mid-run unplanned human-input prompts are evidence-bearing failures of preflight/adapter coverage, not reasons to silently wait forever.
## Adaptive gap closure without schedule corruption

The baseline schedule is immutable once campaign execution begins. New high-value discoveries do not mutate or renumber baseline cells.

Instead the orchestrator may append `SupplementalCell` records to an append-only gap-closure queue. Each supplemental cell must include:

- originating evidence/event IDs;
- discovery/contradiction/unknown that justified it;
- decision value;
- system(s) affected;
- scenario/perturbation definition;
- fixture/input hashes;
- explicit closure condition.

Supplemental work becomes mandatory once admitted. Campaign completion is blocked until every admitted supplemental cell reaches a valid terminal evidence state or is explicitly classified `INACCESSIBLE`/`NOT_APPLICABLE` with supporting evidence.
## Campaign completion authority

The orchestrator may report `COMPLETED` only when all of the following are true:

1. every frozen baseline cell has a valid terminal evidence state;
2. every admitted supplemental/gap-closure cell is closed;
3. every frozen behavioral scenario is represented for every required system according to the scenario manifest;
4. every frozen perturbation requirement is represented by its declared matched cells;
5. no escalation is pending and every escalation chain verifies;
6. all required native artifact manifests verify;
7. all 13 mandatory evidence channels satisfy their per-system coverage contract;
8. all system-level completion reports are complete;
9. the cross-system manifest verifies;
10. future-query/unknown-question coverage gates required by the parent harvest contract pass.

Scheduler exhaustion, backend exhaustion, process exit, budget exhaustion, or elapsed time can never be translated into `COMPLETED`. They produce an explicit incomplete/blocker state.
## Scheduling policy

The first implementation is deterministic and sequential: one mutable execution cell at a time. This avoids cross-cell filesystem races, mixed native streams, resource contention, and ambiguous failure attribution.

Ordering is frozen into stable matched blocks so comparable systems/scenarios do not drift arbitrarily across the campaign. The scheduler records block ID, ordinal, selection reason, and all skipped/not-yet-eligible cells.

A blocked cell does not abort unrelated eligible cells. The scheduler may advance to other work while preserving the blocker, but it cannot close the campaign until the blocked cell is reconciled.

Future parallel execution may be added only behind resource/workspace leases that preserve the same logical schedule and evidence semantics.
## Required orchestration records

At minimum the journal must preserve machine-queryable records for:

- schedule compiled/frozen and schedule hash;
- global/system/cell preflight reports;
- cell eligibility and scheduler selection;
- before/after snapshots;
- backend launch/resume identity;
- every raw backend observation before interpretation;
- verifier inputs/results;
- stall detector inputs/verdicts;
- failure-boundary/capsule persistence;
- escalation-router candidates/selection;
- infrastructure interruption/reconciliation;
- artifact-manifest evaluation;
- discovered gaps and supplemental-cell admission;
- cell/system/campaign completion evaluations.

Each record carries campaign, cell, execution, parent-event, wall-clock, monotonic-order, source/version and content-hash lineage where applicable.
## TDD acceptance matrix

The fake-backend implementation must prove at least these cases before any live backend exists:

- schedule rejects missing/duplicate/unknown cells and uncovered frozen requirements;
- no execution occurs before global and cell preflight are GREEN;
- success path records raw evidence before verification and completes only after manifests;
- incorrect result persists a verified capsule before escalation continuation;
- stall persists detector evidence and capsule before escalation;
- recursive escalation creates parent-linked child capsules;
- infrastructure interruption resumes the same logical execution ID/escalation level;
- crash/replay does not duplicate a launch, capsule, artifact finalization or advancement;
- malformed/unknown native records remain lossless raw evidence;
- unexpected artifacts become discoveries rather than being discarded;
- discovered high-value gaps append mandatory supplemental cells;
- blocked cells do not globally abort eligible work;
- scheduler exhaustion with open work cannot report completion;
- all 11 adapters can run synthetic matched cells through the same orchestrator semantics;
- constructing/testing the runner launches zero real target agents, providers or network calls.
## Non-goals for this implementation phase

This phase does **not**:

- launch Codex, Claude Code, Prime Agent, Pi, oh-my-cli, SWE-agent, mini-SWE-agent, Aider, AegisEvo, OpenHands or Kimi CLI;
- add production subprocess/network/API execution backends;
- consume paid model calls;
- define the final live scenario fixture corpus;
- choose production escalation-model credentials/providers;
- alter the existing INVERTED causal system-testing template;
- repair unrelated capability-ratchet regressions on the shared branch.

Those become separate gated implementation targets after the fake-backed orchestration engine proves the campaign cannot lose evidence, skip work, corrupt resume state or bypass escalation.
## Raw-firehose invariant

For every observable target/backend stream enabled by the adapter, the backend must forward the complete stream to the recorder without semantic filtering. This includes stdout, stderr, structured event streams, partial streamed model output, tool requests/results, lifecycle events, diagnostics and target-native artifacts.

Filtering, parsing, deduplication, truncation, classification or normalization may create derived views only after the exact source record is preserved. If the target itself truncates or withholds a value, that limitation is captured as provenance; the harness must not pretend the omitted datum was observed.

The economic rule is explicit: storage volume is not the optimization target. Future irrecoverability is.