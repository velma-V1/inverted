# TEST 3 — S2 Complete Forensic Evidence Hardening

Date: 2026-09-01
Branch: `build/test3-s2-adaptive-routing`
Status: approved design, implementation pending

## Objective

Harden S2 so every scientifically valuable observation generated before, during, or after the campaign is durably retained, including partial runs and measurement-system failures. The S2 intervention protocol, arm definitions, frozen thresholds, Holdout-B cases, model selection, and 720-inference schedule remain unchanged.

The test must never rely on RAM as the sole copy of evidence that would be useful to reconstruct, diagnose, audit, reproduce, or learn from an execution.

## Current verified gaps

1. Successful model adapters receive the complete Ollama provider response, but `BoundedCompletion` drops the full `CompletionResult.raw` payload. S2 therefore preserves response text and selected telemetry, not the complete provider result.
2. Candidate construction collapses distinct failures such as JSON parse failure, malformed action construction, action application failure, and repair-composition failure into `candidate=None` / `parse_or_execution` without preserving the exact stage and exception.
3. S2 accumulates model calls, routing decisions, routing snapshots, validator results, events, and trial results in memory until the entire 720-call runtime returns.
4. An exception during the runtime can therefore erase the complete accumulated prefix from the final evidence packet.
5. Pre-run provenance is performed before the runtime's protected evidence-finalization path. A provenance failure can consume external actions while leaving no complete abort record.
6. Provenance currently retains selected fields and hashes for some Ollama endpoints instead of retaining every returned payload needed for later forensic interpretation.
7. Router-observability collisions are not explicitly measured: different hidden fault truths can map to an identical router-visible state.

## Design principle

S2 becomes an event-sourced forensic experiment.

Every valuable event is appended to an on-disk journal as soon as the event exists. The existing in-memory runtime remains the convenient working representation, but it is no longer the authoritative persistence layer.

The journal is append-only, ordered, independently hashable, and sufficient to reconstruct the largest valid prefix of a failed run.

No private/hidden fixture truth is allowed to enter a model prompt or router decision. Private truth may only be joined after execution for forensic analysis.

## Evidence flow

```text
experiment event
    -> append forensic journal record
    -> flush durable record
    -> continue existing runtime mutation
    -> normal final analysis/artifact packet

abnormal abort
    -> append abort record if process remains alive
    -> finalize partial evidence packet from durable journal/prefix
    -> mark protocol invalid for primary claim
    -> retain consumed action accounting and all surviving evidence
```

## Required captured events

The journal must be able to represent, at minimum:

- run initialization;
- config snapshot and hashes;
- code/protocol identity;
- environment/runtime identity useful for reproduction;
- preflight provenance request start;
- raw preflight response or exact error;
- external-action budget reservation;
- trial start;
- candidate-before snapshot;
- deterministic validator state;
- full public failure state;
- exact router-visible projection;
- router action decision;
- exact model request messages and generated Ollama request payload;
- physical call start and physical call number;
- raw provider response or exact provider/transport failure;
- parsed response outcome;
- candidate/action construction result or failure;
- repair composition result or failure;
- proposed candidate snapshot;
- post-action validator result;
- active or shadow state transition;
- trial completion;
- post-run provenance request/response/error;
- analysis completion;
- final verdict;
- artifact finalization;
- abnormal abort with exception class, message, traceback, current trial/call identity, and exact partial counters.

## Raw model transaction retention

`BoundedCompletion` must retain the complete provider `raw` response produced by `CompletionResult` for successful calls. Failed calls must preserve the complete `ModelCallRecord` plus any response body/error information available from the adapter.

S2 must emit a dedicated raw transaction stream. The normal `model_calls.jsonl` remains useful as the normalized analysis surface, but raw provider evidence must not be replaced by normalized fields.

No inference is added for this capability.

## Failure-stage taxonomy

Do not collapse all candidate failures into `parse_or_execution`. Preserve an explicit stage and details, including at least:

- `model_transport_failure`
- `generation_censored`
- `empty_model_response`
- `response_json_parse_failure`
- `response_schema_or_action_decode_failure`
- `action_application_failure`
- `repair_patch_parse_failure`
- `repair_patch_composition_failure`
- `deterministic_validator_failure`
- `runtime_internal_exception`
- `provenance_failure`
- `artifact_finalization_failure`

Each record must carry the call/trial identity, exception class/message when applicable, and enough input context to reconstruct the failing transformation without contaminating router/model inputs.

## Append-only forensic journal

Add an S2-specific journal component with these properties:

- JSONL append-only format;
- monotonic sequence number;
- UTC timestamp;
- event type;
- run/trial/call identifiers where applicable;
- payload;
- hash chain (`previous_sha256`, `record_sha256`) or equivalent integrity mechanism;
- flush after each record;
- no destructive rewrite during the live run;
- journal writing failures become explicit instrumentation failures and block architecture claims.

The live journal is not included in router evidence and cannot affect arm behavior.

## Partial/abort evidence packet

A failed Tier-A execution must still produce an evidence directory whenever the process can execute cleanup.

The packet must identify itself as partial/aborted and must include:

- completed journal prefix;
- raw model transactions already observed;
- all completed normalized call rows;
- completed routing decisions/snapshots/validator rows/events;
- completed and partial trial state;
- action-budget snapshot;
- provenance completed before failure;
- abort state and traceback;
- integrity inventory for files successfully finalized;
- a verdict that explicitly withholds S2 primary/architecture claims.

If a hard process kill prevents cleanup, already-flushed journal records remain the recovery source.

## Provenance completeness

For S2 only, retain both normalized provenance fields and full JSON payloads returned by:

- `/api/version`
- `/api/tags`
- `/api/ps`
- each `/api/show` request

Requests must still be counted by the existing combined external-action budget. No new provenance endpoints are required.

Secrets or authorization headers must never be persisted. The current local Ollama flow has no API secret requirement.

## Router-observability collision analysis

Add a post-execution private analysis that groups cases by exact router-visible observation while joining the hidden fixture truth only on the analysis side.

For each arm/router observation level, capture:

- observation fingerprint;
- number of cases mapped to the observation;
- number of distinct hidden fault truths represented;
- hidden perturbation/fault labels represented;
- collision/ambiguity flag;
- action selected for the observation;
- observed outcomes;
- whether richer B3 evidence separates collisions present in B2;
- collision groups that remain indistinguishable even under B3.

Primary summaries must include:

- collision count;
- collision rate;
- ambiguous-case count/rate;
- largest collision-group size;
- B2-to-B3 collisions resolved;
- collisions remaining under B3.

This analysis is strictly post hoc. Hidden truth must never be passed to `public_router_state`, `select_action`, or model messages.

## New evidence artifacts

Add at minimum:

- `forensic_journal.jsonl`
- `raw_model_transactions.jsonl`
- `parse_and_composition_failures.jsonl`
- `external_action_ledger.jsonl`
- `environment_provenance.json`
- `abort_state.json`
- `router_observability_collisions.csv`
- `router_observability_summary.json`
- `journal_integrity.json`

The final `COMPLETE-EVIDENCE.txt` and `SHA256SUMS.csv` must incorporate the new artifacts. For abnormal runs, the completion marker must clearly state `PARTIAL/ABORTED EVIDENCE` rather than falsely claiming complete evidence.

## Budget and protocol invariants

Unchanged:

- 72 Holdout-B cases;
- 5 matched arms;
- 2 calls per arm/task;
- 360 trials;
- exactly 720 scheduled inference actions for a valid full run;
- at most 12 provenance API actions;
- 732 combined S2 external-action budget;
- repository absolute ceiling remains 1000;
- zero transport retries;
- no outcome-dependent early stopping;
- no hidden/private fixture fields in model prompts or router inputs.

Forensic persistence and analysis add zero model calls and zero new external API calls.

## Failure semantics

The evidence system must fail closed scientifically, not fail silent operationally.

- A journaling/integrity failure marks instrumentation invalid and blocks architecture claims.
- A model/transport failure is retained as experimental evidence and consumes its scheduled physical call slot under the existing caller semantics.
- An internal runtime exception aborts the remaining campaign but preserves the completed prefix and marks the run invalid for the primary claim.
- Provenance failure is retained with consumed action accounting and marks the run invalid/instrumentation-warning as appropriate.
- Artifact-finalization failure must not delete or truncate the journal already written.

## Tests required before Tier-A

Use test-first development. Each production behavior must first have a test that fails for the missing guarantee.

Required failure-injection/contract tests:

1. successful call retains complete raw provider payload;
2. response parse failure records exact stage and exception without losing raw response;
3. invalid action/application failure is distinguished from JSON parse failure;
4. repair composition failure is independently recorded;
5. journal records are flushed incrementally before runtime completion;
6. injected exception after N calls leaves N-call evidence prefix on disk;
7. exception between routing decision and model completion retains the decision/start state;
8. pre-run provenance failure writes action ledger + abort evidence;
9. post-run provenance failure preserves completed 720-call evidence and marks instrumentation warning/invalid claim correctly;
10. partial evidence packet cannot claim protocol validity or architecture promotion;
11. journal hash/integrity validation detects tampering/truncation where detectable;
12. router-observability collision detector identifies intentionally aliased hidden faults;
13. collision analysis cannot change routing/model inputs;
14. full mock S2 still consumes exactly 720 model-call slots and produces all required evidence artifacts;
15. existing S2 protocol, budget, B4 outcome independence, prompt privacy, stochastic-divergence, and workflow tests remain green.

## Acceptance criteria

Tier-A remains blocked until all of the following are true:

- every known scientifically valuable S2 event has a durable representation;
- complete raw Ollama response payloads survive successful calls;
- exact transformation failures are retained instead of collapsed;
- abnormal aborts preserve the largest available evidence prefix;
- consumed external actions remain accountable after failures;
- provenance failures are reconstructable;
- router-observability collisions are explicitly measured;
- private truth remains causally isolated from runtime routing and model prompts;
- no new model/API calls are introduced;
- all dedicated S2 and repository regression tests are green.

Only after these gates pass may S2 Tier-A be authorized.