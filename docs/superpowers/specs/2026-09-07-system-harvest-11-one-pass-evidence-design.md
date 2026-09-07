# SYSTEM_HARVEST_11 - One-Pass Evidence / Escalation Harvest Design

## Status

Owner-approved architectural direction. This is a new harvest program and does not replace or modify the INVERTED-vs-Brain causal testing template.

## Mission

Harvest eleven external/dev-agent systems at maximum practical evidence depth so future INVERTED work can copy, reimplement, modify, combine, reject, or newly reinterpret mechanisms without depending on a second acquisition opportunity.

The primary acceptance test is future-query survivability: 6–12 months later, a frontier model must be able to investigate a newly discovered architecture problem from the preserved evidence even if that question was not known when the harvest ran.

## Frozen system set

1. Codex
2. Claude Code / Agent SDK
3. Prime Agent
4. Pi
5. oh-my-cli
6. SWE-agent
7. mini-SWE-agent
8. Aider
9. AegisEvo
10. OpenHands
11. Kimi CLI

## Governing economic law

Data collection is cheap. Retesting is not.

For this campaign, omission cost is measured by future irrecoverability, not storage volume. Safe observable evidence may not be discarded merely because today's analysis does not yet need it.
## One-pass evidence standard

"Never rerun" is an importance signal for evidence collection, not an execution prohibition. The harness must behave as if this may be the only affordable or available acquisition opportunity, so omission cost is treated as future irrecoverability. Future replay, validation, or fresh testing remains allowed when scientifically justified.

- Every safely observable model/system product is preserved before summarization or normalization.
- Missing evidence that should have been observable prevents harvest completion until captured or explicitly classified.
- `INACCESSIBLE` is valid only when the source truly cannot expose the datum and the reason is recorded with supporting evidence.
- Crash recovery resumes the same durable campaign journal when possible, but this is an integrity property rather than a ban on future campaigns.
- The data model must support new 6-12 month questions that were not known at acquisition time.

## Failure-boundary escalation law

A wrong answer, stall, stuck state, or equivalent semantic failure is a high-value capability-boundary event. It does not become a terminal retry-failure record. Before any recovery mutation occurs, the harness freezes a complete escalation capsule representing the reconstructable execution state at the failure boundary.

The capsule must preserve, through raw payloads or content-addressed references, the original task contract and instructions, all active ingredients/support layers, exact model-visible context, system-visible state, model/runtime identity and inference parameters, tool registry and complete tool/model trajectory, filesystem/git/process/environment state, memory and plan state, verifier state, pre-failure state, failing action, raw failure result, post-failure state, pending work, telemetry, provenance, and event lineage.

The escalation model receives that capsule and continues from the captured failure boundary. It must not be reduced to a fresh summary prompt or a clean restart. Restart is allowed only when the captured evidence demonstrates that continuation is impossible or unsafe, and that decision itself is preserved as evidence.

Escalation is recursive. If an escalation model also fails or stalls, its new failure boundary creates a child capsule linked to the prior capsule and the next stronger escalation level inherits the complete chain. Infrastructure interruption is different: it resumes the same execution identity and does not create a semantic escalation unless the recovered system actually reaches a semantic failure boundary.

Native retries performed internally by the system under test remain part of that system's observed behavior and are captured exactly; the harness does not silently reinterpret them as escalation events.

## Completion state machine

Allowed campaign states are:

`PLANNED -> ACQUIRING -> RUNNING -> GAP_CLOSURE -> COVERAGE_AUDIT -> COMPLETED`

Exceptional durable states are `PAUSED_ENVIRONMENT` and `INCOMPLETE`; neither may be presented as completed.
## Exhaustive observable capture contract

For every model/system action, capture every safely observable product before normalization or summarization. This includes, when exposed:

- exact model request payloads, messages, tool schemas, inference parameters, and context snapshots;
- streaming deltas/chunks, final response payloads, reasoning/thinking fields exposed by the runtime, tool-call proposals, structured outputs, parser products, usage/token counters, cache metadata, and provider/runtime telemetry;
- system prompts/instructions that are observable, generated plans, candidate sets, rejected candidates, routing choices, confidence/uncertainty fields, policy decisions, memory reads/writes, summaries, checkpoints, and internal event logs;
- every tool request, arguments, stdout, stderr, exit status, raw result, parsed result, timeout/cancel event, retry, fallback, and non-selection when eligibility is observable;
- filesystem reads/writes, before/after hashes, diffs, patches, created/deleted files, git state, process state, environment changes, network events exposed by the harness, and verifier/test outputs;
- timestamps, ordering, execution position, parent/child event IDs, state IDs, task/example/attempt IDs, model/runtime identity, configuration hashes, source commit/version, and provenance;
- all errors, warnings, stalls, partial outputs, malformed outputs, abandoned paths, no-progress events, recovery actions, and termination reasons.

The contract covers observable outputs, not inaccessible hidden chain-of-thought or provider-internal state. Raw credentials and secrets are not persisted in plaintext; they are replaced by stable redaction tokens while preserving type, position, lineage, and cryptographic fingerprint where safe.

No normalized field may exist without lineage to the raw event(s) that support it.

## Four-tier evidence store

`01_RAW/` contains immutable exact acquired evidence.

`02_NORMALIZED/` contains common schemas across all eleven systems.

`03_RELATIONSHIPS/` contains state/action/mechanism/provenance/context/failure graphs and stable IDs linking the evidence.

`04_DERIVED/` contains current conclusions, rankings, transfer ideas, causal hypotheses, and implementation recommendations. Derived evidence is regenerable; raw evidence is not.
## Mandatory coverage domains

Each system must produce a coverage ledger across all applicable domains below. The domain list is a floor, not a ceiling; newly discovered mechanisms automatically create new ledger items.

1. **Identity and source snapshot** — exact code/version, tree, hashes, dependencies, configs, feature flags, tests, examples, docs, licenses, release history.
2. **Repository archaeology** — removed/reverted mechanisms, major fixes, architectural migrations, TODO/FIXME/HACK evidence, issue/PR lessons where available.
3. **Architecture and responsibility** — modules, processes, agents, control flow, data flow, state, persistence, verification, recovery, authority, dependency graphs.
4. **Control loop** — ingestion, interpretation, planning, action selection, execution, observation, evaluation, replanning, retry, recovery, completion and stop conditions.
5. **Context engineering** — every context source, selector, ordering, placement, token budget, truncation, compression, deduplication, refresh, eviction, caching, stale-context handling.
6. **Memory/state** — working, task, project, failure, evidence, checkpoint and cross-session state; schemas, read/write triggers, invalidation and reconciliation.
7. **Planning/decomposition** — plan representation, dependency handling, mutation, checkpoints, replanning, stale-plan behavior and completion criteria.
8. **Tools/search/edit/terminal** — full schemas, eligibility, selection, argument generation, parsing, file-edit strategy, shell lifecycle, search/ranking and failure handling.
9. **Verification** — syntax, tests, lint, compile/type checks, diff review, invariants, postconditions, semantic verification, world-state verification and blind spots.
10. **Failure/recovery** — detection, first divergence, diagnosis, retry, rollback/compensation, alternative path, escalation, safe stop, recovery verification.
11. **Checkpoint/resume** — interruption behavior, serialization, restart, state reconstruction, unfinished work, duplicate prevention and replay safety.
12. **Agents/concurrency/scheduling** — delegation, worker context, queues, parent-child communication, parallelism, locks, race protection, conflict resolution and aggregation.
13. **Model interface/routing** — provider/model, inference parameters, reasoning modes, fallbacks, escalation, routing features, thresholds and cost/capability tradeoffs.
14. **Authority/security/isolation** — permissions, approval gates, destructive-action fencing, sandboxing, network/filesystem scope, secrets, injection and untrusted-input handling.
15. **Observability/runtime economics** — logs, traces, metrics, tokens, latency, cache, CPU/RAM/GPU/VRAM/disk/network where measurable, retries and operator interventions.
16. **Configuration/extensibility** — every exposed/hidden knob found, plugin/tool/MCP/skill hooks, adapters, middleware, commands and extension interfaces.
17. **Engineering substrate** — schemas, event systems, serialization, test harnesses, replay, mocks/fixtures, deterministic IDs, error taxonomies and provenance machinery.
18. **Unique and anti-feature discovery** — capabilities outside the current taxonomy plus complexity traps, brittle abstractions, hidden coupling, waste and unsafe patterns.
## Dynamic behavioral battery

Every compatible system receives a common core battery plus system-specific probes. The core battery must include happy paths and adversarial/compound conditions: trivial edit, multi-file feature, unfamiliar repository, debugging, dependency reasoning, ambiguity, conflicting requirements, incomplete evidence, failing/flaky tests, wrong initial assumption, missing dependency, command/tool failure, timeout, malformed tool result, interrupted execution, partial mutation, stale git/state, merge conflict, context pressure, huge output, misleading evidence, permission boundary, irreversible-action boundary, recovery opportunity, repeated-failure trap, replanning, parallelizable work, long-running work and resume-after-interruption.

Rare compound cases are mandatory. The campaign must include high-value edge cases analogous to the project's “purple unicorn riding an orange whale” standard rather than testing only common paths.

## Perturbation and boundary battery

Where semantically valid, deliberately vary or break:

- context amount/order/freshness;
- memory and planning availability;
- verifier availability;
- tool availability and malformed results;
- network availability;
- model/provider choice;
- token/call/resource pressure;
- repository size and dependency complexity;
- interruption timing;
- conflicting state;
- retry/recovery opportunity.

Selected identical cases are repeated for stochasticity/path-variance measurement. Hidden thresholds discovered during observation receive targeted boundary probes.

## Decision/counterfactual capture

For every meaningful decision where observable, preserve the chosen option, all eligible alternatives, selection/rejection reason, pre-decision state, post-decision state, active mechanisms, context lineage, cost and verification result.

This makes future shadow analysis possible even when the future question was not anticipated during acquisition.
## Mechanism extraction contract

Every separable mechanism receives a stable `mechanism_id` and records:

- problem solved and trigger;
- exact inputs/outputs/state/dependencies;
- responsibility owner and authority boundary;
- algorithm/implementation location;
- context/tool/model requirements;
- activation frequency and non-events;
- observed successes and failures;
- first meaningful divergence where known;
- failure boundary and negative-transfer region;
- complexity/resource rent;
- minimal extraction unit;
- reimplementation recipe and pseudocode;
- overlap/conflict/synergy hypotheses with INVERTED;
- evidence lineage and confidence.

Transfer dispositions are:

`COPY_DIRECTLY`, `REIMPLEMENT`, `MODIFY`, `SIMPLIFY`, `COMBINE`, `REPLACE_EXISTING`, `USE_AS_CONTROL`, `USE_AS_VERIFIER`, `USE_AS_RECOVERY`, `USE_AS_ROUTER`, `USE_AS_MEMORY`, `USE_AS_CONTEXT_OPERATOR`, `USE_AS_TOOL_PATTERN`, `USE_AS_TEST_PATTERN`, `DO_NOT_COPY`, `NEEDS_CAUSAL_TEST`, `UNRESOLVED`.

The purpose is not to rank eleven products. It is to build a cross-system mechanism graph that exposes convergent solutions, unique mechanisms, competing implementations, common failures, removable complexity and high-value composition candidates.

## Coverage ledger

Every required item is explicitly one of:

`PENDING`, `CAPTURED`, `CAPTURED_PARTIAL`, `INACCESSIBLE`, `NOT_APPLICABLE`, `CONTRADICTED`, `NEEDS_RUNTIME_PROBE`, `NEEDS_STATIC_PROBE`, `NEEDS_GAP_CLOSURE`.

Blank or silently skipped items are forbidden. `CAPTURED_PARTIAL` and `NEEDS_*` states prevent final completion until resolved to a permitted terminal state or proven inaccessible/not-applicable.
## Gap-closure loop

A system cannot close merely because the predefined checklist was executed.

`INITIAL HARVEST -> ANALYZE -> DETECT UNKNOWN/CONTRADICTION/SURPRISE -> TARGETED DEEP DIVE -> COVERAGE AUDIT -> GAP CLOSURE -> SECOND AUDIT -> FREEZE`

Any newly discovered high-value feature, hidden threshold, unexplained divergence, missing relationship or contradictory source/runtime observation automatically creates a new required ledger item inside the same campaign.

## Future-query survivability gate

Before a system freezes, analysts must ask questions that were not part of the original probe design. The stored evidence must support investigation of questions such as:

- which context characteristic predicts successful recovery;
- whether two apparently different retry mechanisms implement the same state machine;
- which verification step catches errors earliest per unit cost;
- whether a mechanism only becomes useful after another mechanism fails;
- whether one system's recovery policy can operate on another system's state representation;
- what mechanism predicts repeated unnecessary searches or edits;
- whether planning becomes harmful under specific context pressure;
- what would be required to recreate a newly noticed capability.

If an unknown question is unanswerable because observable evidence was discarded, coverage fails and the missing acquisition becomes mandatory before that system can freeze.

## Data-integrity rules

- Raw evidence is append-only and content-addressed.
- Each event receives a stable ID and parent/causal lineage where knowable.
- State snapshots/diffs are hashed.
- Manifest counts and hashes are verified before completion.
- Derived conclusions never overwrite raw records.
- Capture failures are first-class evidence and block completion until repaired or proven inaccessible.
- Every normalization transformation records source IDs and transform/version hashes.
## Completion gate

A system may be marked `HARVEST_COMPLETE` only when all of the following are true:

1. every required coverage item has a permitted terminal state;
2. no item remains `PENDING`, `CAPTURED_PARTIAL`, `NEEDS_RUNTIME_PROBE`, `NEEDS_STATIC_PROBE`, or `NEEDS_GAP_CLOSURE`;
3. every behavioral example has a verified terminal outcome; every semantic failure/stall on its path has a verified escalation capsule and lineage to the continuation that resolved it;
4. every expected raw evidence channel has a capture record or a proven `INACCESSIBLE` justification;
5. all raw/normalized/relationship manifests verify;
6. discovered mechanisms have evidence lineage and extraction records;
7. unresolved contradictions are explicitly preserved and classified;
8. future-query survivability probes demonstrate that new questions can be investigated from preserved evidence without depending on reacquisition;
9. the cross-system schema can ingest the system without lossy coercion;
10. no required data was summarized away before raw preservation.

The eleven-system campaign may be marked `COMPLETED` only when all eleven systems independently satisfy `HARVEST_COMPLETE` and the cross-system mechanism graph plus coverage manifest verify.

## Non-goals

This harvest does not decide the final INVERTED architecture, certify copied mechanisms, or replace later causal testing. It creates the richest practical evidence base from which those later decisions can be made without reharvesting the eleven systems.

## Acceptance criteria for the template/harness layer

The implementation is ready to run only when tests prove:

- the frozen eleven-system manifest is complete and immutable;
- wrong/stalled model execution requires a complete failure-boundary escalation capsule before recovery mutation;
- escalation continues from the captured boundary rather than restarting by default;
- recursive escalation preserves parent/child capsule lineage;
- semantic escalation and infrastructure resume are distinct;
- no single system/example semantic failure silently becomes terminal while a valid escalation path remains;
- completion is impossible with missing/partial/gap-closure items;
- every emitted event type can retain raw payload plus provenance/lineage;
- resumed execution preserves campaign/example/execution identity and escalation level;
- newly discovered coverage items can be appended without changing prior evidence;
- raw evidence manifests are content-addressed and verifiable;
- future-query coverage records are mandatory before freeze;
- template validation launches no real inference.
