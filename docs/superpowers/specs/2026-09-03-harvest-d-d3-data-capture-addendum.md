# Harvest D D3 — Maximum-Value Data Capture Addendum

## Status

APPROVED DESIGN REVIEW ADDENDUM. NORMATIVE FOR D3 IMPLEMENTATION.

This addendum strengthens `2026-09-03-harvest-d-d3-automated-information-control-tomography.md`.

Principle:

> Model inference is expensive and often impossible to reproduce exactly; storage and deterministic post-hoc analysis are cheap. Every admissible D3 physical model call must therefore preserve the maximum practically useful observable evidence so later hypotheses can be tested from stored data without rerunning the model.

This addendum does not authorize hidden/private chain-of-thought collection, credential capture, broad environment dumps, authority expansion, or oracle leakage. It maximizes usable experimental evidence.

## 1. Three-layer evidence rule

Every expensive observation must be preserved in three linked forms:

1. **RAW / IMMUTABLE** — exact observable request, exact raw model/runtime response, exact model-visible information packet, system-known state/evidence snapshot, and raw event payloads.
2. **NORMALIZED / QUERYABLE** — typed fields for cross-case analysis without reparsing raw blobs.
3. **DERIVED / RECOMPUTABLE** — scores, labels, intervals, classifications, causal claims, and summaries, each linked to the raw and normalized sources that produced it.

Hashes are integrity/linkage aids. A hash must never replace the underlying payload when the payload is safe and useful to retain.

## 2. Required per-call capture

For every physical model call, preserve at minimum:

### Identity and lineage

- run_id;
- experiment_id;
- phase;
- block_id;
- case_id;
- case-family and difficulty;
- arm_id;
- parent/preceding event IDs;
- physical_model_call_id;
- attempt index, which must normally be zero because D3 forbids blind retries;
- scheduler decision ID that caused the call;
- source case-bank path/hash;
- mutation/perturbation lineage when applicable;
- target/sham/control membership;
- fresh/development/neighbor/sealed status.

### Exact model input

- complete system message;
- complete user/task message;
- complete tool/evidence messages supplied to the model;
- exact ordered message array sent to the runtime;
- exact information packet before rendering;
- exact rendered information packet;
- information field IDs present/absent;
- information quality labels;
- trust/source labels;
- representation, ordering, placement, timing, and amount condition;
- schema/tool definitions visible to the model;
- prompt/template version;
- prompt construction code/config version;
- prompt hash and byte count;
- token count where available;
- whether any context truncation occurred and what was removed.

### Exact model output

- complete response text exactly as returned;
- full raw runtime/API response payload;
- parsed structured response if parsing succeeds;
- parse errors if parsing fails;
- all explicitly emitted candidate actions/alternatives;
- explicitly emitted confidence/uncertainty fields;
- explicitly emitted evidence requests;
- explicitly emitted referenced state/evidence/authority fields;
- explicitly emitted concise rationale/reason codes;
- stop/finish reason when available;
- truncation indicator;
- malformed/empty/partial-output indicator.

The raw runtime payload must be retained even when normalized fields are extracted from it.

## 3. Observable decision trace instead of hidden chain-of-thought

D3 must not rely on private chain-of-thought. Where decision-process information would improve later analysis, the model-facing contract should request a compact structured decision trace that is safe to store and compare.

When applicable, capture:

- selected disposition/action;
- candidate actions considered;
- rejected alternatives with short reason codes;
- evidence/state/authority fields referenced;
- missing information identified;
- uncertainty category or confidence band;
- recovery candidates considered;
- selected recovery and reason code;
- expected postcondition;
- predicted risk/consequence class;
- whether escalation/evidence acquisition was considered;
- novelty/unknown-signature flag.

This trace is an observable model output and may be scored, but it is never treated as ground truth.

## 4. Runtime and model provenance

Capture enough runtime metadata to distinguish model behavior from harness/runtime changes:

- requested model ID;
- returned model ID;
- model digest/hash when available;
- model family/version;
- parameter size when known;
- quantization when known;
- local artifact size when available;
- chat template/version when available;
- Ollama/runtime version;
- endpoint/runtime identity;
- generation options in full;
- temperature;
- seed;
- context-window setting;
- max-output setting when applicable;
- stop sequences if any;
- tool schema version;
- tokenizer/runtime-reported prompt/eval token counts;
- runtime-reported load duration, prompt-eval duration, eval duration, total duration, and throughput values when available;
- wall-clock latency independently measured by the harness.

If the runtime exposes additional stable, non-sensitive timing or inference counters, retain the raw values rather than discarding them.

## 5. Hardware and execution-environment metadata

Record a safe allowlisted environment snapshot at run start and relevant changes during the campaign:

- OS/version/build;
- Python version;
- INVERTED package/repo commit;
- git branch and dirty/clean state;
- CPU model and logical/physical core counts where available;
- installed RAM;
- GPU model(s), VRAM, driver/runtime versions where available;
- observed model processor allocation (CPU/GPU split where runtime exposes it);
- CPU-sentinel residency evidence when applicable;
- process/runtime identity;
- relevant local model-cache/artifact identity;
- available disk space for evidence directory;
- system clock/timezone;
- experiment process start/stop timestamps.

Do not dump arbitrary environment variables, secrets, usernames, tokens, filesystem contents, or unrelated process data.

## 6. Resource/performance telemetry

Where collection is practical and does not materially perturb the experiment, record at call/block granularity:

- wall latency;
- prompt/eval tokens;
- tokens per second;
- CPU utilization summary;
- system RAM utilization;
- GPU utilization;
- GPU VRAM utilization;
- model load/unload events;
- queue/wait time if observable;
- runtime error/timeout durations;
- local energy/power proxy only when safely and consistently available.

Performance telemetry is diagnostic; it may not override correctness or hard-invariant results.

## 7. Full system-known state snapshots

For each decision boundary, preserve the actual safe payloads, not only hashes, for:

- canonical state and version;
- current objective/subgoal;
- scope;
- authority/lease state including consumption status;
- evidence set and provenance;
- required-but-missing evidence;
- global invariants;
- postconditions;
- dependency/topology state;
- transaction/effect status;
- recovery state;
- admissible-action set;
- active deterministic guards/rules;
- router-visible features;
- promoted knowledge/guard versions active at the time.

Also record a separate **model-visible projection** of these fields so later analysis can distinguish system knowledge from model knowledge.

## 8. Assistance/intervention telemetry

For every deterministic or model-based assistance mechanism, record:

- mechanism ID and version;
- OFF/TARGET/SHAM status;
- trigger condition and trigger values;
- exact inputs;
- exact output;
- reason code;
- action/disposition before intervention;
- action/disposition after intervention;
- whether the intervention changed the trajectory;
- whether it prevented, introduced, migrated, or merely detected a failure;
- latency and token cost if any;
- dependency on other active mechanisms;
- whether the mechanism had access to model-visible, system-only, or mixed information.

For zero-call counterfactual replay, preserve the replay specification and verify that only the intended intervention variable changed.

## 9. Scheduler and adaptive-experiment telemetry

Because D3 is adaptive, the scheduler itself is part of the causal system and must be recorded.

For every scheduling decision, retain:

- unresolved hypotheses considered;
- candidate next experiments;
- eligibility/preregistration status of each candidate;
- evidence counts available to each candidate;
- current sequential decision state;
- estimated information value/priority features used by the scheduler;
- reason the selected experiment outranked alternatives;
- calls remaining globally and by protected reserve;
- calls reallocated from killed/futile mechanisms;
- stopping reason for any experiment arm;
- promotion/defer/reject state changes.

Do not store hidden chain-of-thought from any model used by the scheduler. Store deterministic scores, structured reason codes, and observable scheduler inputs/outputs.

## 10. Failure and edge-case capture

Every edge case must be stored, including cases normally discarded by benchmark harnesses:

- malformed output;
- empty output;
- partial/truncated output;
- schema mismatch;
- parser disagreement;
- timeout;
- connection refusal/reset;
- runtime crash;
- model unavailable/load failure;
- provenance mismatch;
- context overflow/truncation;
- unexpected token counts;
- duplicate-call prevention event;
- journal recovery/resume event;
- stale state detection;
- authority mismatch;
- unknown effect;
- verifier disagreement;
- target/sham inconsistency;
- oracle/instrumentation ambiguity;
- contamination/leakage suspicion;
- sealed-bank access attempt;
- scheduler dead-end;
- hard-stop event.

An invalid trial is still evidence. Mark it invalid/inadmissible with a precise reason; do not silently delete it.

## 11. Error and exception evidence

For harness/runtime exceptions, preserve:

- exception class;
- safe error message;
- component/stage;
- case/call/event IDs;
- call state at failure;
- whether request transmission began/completed if knowable;
- whether response bytes were received;
- whether any external/simulated effect may have occurred;
- recovery/resume decision;
- stack trace for harness code where safe;
- raw HTTP/runtime status and response body where safe;
- resulting admissibility classification.

Unknown transmission/effect state must remain UNKNOWN rather than being inferred as failure/no-effect.

## 12. Scoring and oracle provenance

Every derived score must preserve:

- scorer version/hash;
- normalization rules used;
- parser version;
- exact expected semantic oracle/reference object;
- oracle version/hash;
- score before normalization where meaningful;
- normalized score;
- disposition correctness;
- answer correctness;
- semantic correctness;
- contract/format/schema correctness;
- verifier outputs;
- disagreement among independent verifiers/oracles;
- adjudication event if used;
- timestamp/order showing the hidden oracle was revealed only after the model decision when required.

Re-scoring stored raw responses with a later scorer must create a new derived layer and never overwrite original scores.

## 13. Case-generation and perturbation provenance

For every case retain:

- original/base case;
- family/capability/difficulty;
- generation source;
- creation version/seed;
- perturbation IDs and parameters;
- localized/compound/structural mutation labels;
- intended causal variable;
- invariant-preserving transformations;
- known-confound annotations;
- contamination status;
- prior exposure status;
- neighbor/fresh/sealed lineage;
- semantic oracle derivation/provenance.

The exact final case payload used for each model call is immutable evidence.

## 14. Temporal and causal markers

Record timestamps and causal markers sufficient to measure:

- case start/end;
- information arrival time;
- model call start/end;
- first meaningful divergence;
- first failure detection;
- diagnosis time;
- intervention time;
- correction time;
- lock-in point;
- recovery start/end;
- verification time;
- final outcome time;
- detection and correction lag;
- time spent in each route/state when observable.

Use monotonic timing for durations and wall-clock timestamps for audit chronology.

## 15. Counterfactual and alternative-action evidence

Whenever the system generates or exposes multiple candidate actions/recoveries, retain the full candidate set and ranking/eligibility data, including candidates not selected.

When a deterministic shadow/counterfactual can be computed without a new model call, compute and store it where scientifically useful, including:

- OFF/TARGET/SHAM outcomes;
- alternate admissible dispositions;
- rule-disabled replay;
- verifier-only/block-only replay;
- alternate routing decision under the same observable state;
- information-field ablation results that do not require a new physical model call;
- deterministic post-hoc state/effect checks.

Counterfactual records must be explicitly marked as replay/shadow rather than physical execution.

## 16. Data integrity and schema evolution

Required protections:

- append-only raw event log;
- globally unique call/event IDs;
- per-artifact SHA-256;
- manifest with byte sizes and hashes;
- schema version on every record family;
- deterministic canonical serialization where practical;
- parent/child lineage links;
- no silent mutation of prior evidence;
- migration tools create new normalized/derived datasets while preserving original raw artifacts;
- integrity verification at checkpoint/resume and finalization.

## 17. Data completeness gate

A physical model call is not considered fully admissible until required capture artifacts have been durably written and validated.

If an essential raw artifact cannot be captured after the model call, record the call as `CAPTURE_INCOMPLETE` and exclude it from promotion claims while retaining every available byte/field.

If the capture subsystem itself becomes unreliable or repeatedly loses essential evidence, D3 must halt before spending further model calls. Cheap storage failure must never cause expensive inference to continue producing scientifically unusable data.

## 18. Queryability outputs

In addition to raw JSON/JSONL, D3 should emit normalized flat/index tables sufficient for fast later analysis, including indexes by:

- physical_model_call_id;
- case/family/difficulty;
- model/model digest;
- information condition;
- representation/order/timing;
- assistance mechanism;
- fault/recovery class;
- route;
- disposition;
- semantic success;
- failure class;
- intervention outcome;
- promotion state;
- event time/sequence.

The final evidence package should include a machine-readable schema/data dictionary describing every field and allowable enum/value.

## 19. Mandatory final data products

Add these to the existing D3 outputs:

- `d3_raw_model_requests.jsonl`;
- `d3_raw_model_responses.jsonl`;
- `d3_normalized_model_calls.jsonl`;
- `d3_information_packets.jsonl`;
- `d3_state_snapshots.jsonl`;
- `d3_evidence_snapshots.jsonl`;
- `d3_authority_snapshots.jsonl`;
- `d3_assistance_events.jsonl`;
- `d3_scheduler_events.jsonl`;
- `d3_recovery_trajectories.jsonl`;
- `d3_edge_cases.jsonl`;
- `d3_errors.jsonl`;
- `d3_counterfactuals.jsonl`;
- `d3_scores_raw.jsonl`;
- `d3_scores_normalized.jsonl`;
- `d3_runtime_telemetry.jsonl`;
- `d3_environment_provenance.json`;
- `d3_case_lineage.jsonl`;
- `d3_data_dictionary.json`;
- `d3_capture_completeness.json`;
- existing event log, call ledger, journal, resume state, hashes, and final report.

## 20. Final data-value test

Before D3 is declared complete, the stored evidence must support retrospective answers without additional model inference to questions such as:

- What exact information did the model see before every wrong disposition?
- Which information source/representation/order/timing changed the answer versus merely changed the disposition?
- What did the system know that the model did not?
- Which assistance mechanism first changed each trajectory?
- Which rejected candidate action would have been admissible?
- Which recovery path fixed the failure, migrated it, or worsened it?
- What runtime/model/hardware differences correlate with anomalous behavior?
- Which edge cases were excluded and why?
- Can the original scorer be reproduced exactly from raw artifacts?
- Can a new scorer or deterministic rule be replayed against the original raw model responses?
- Can every promoted architecture claim be traced to raw calls, exact inputs, system state, interventions, and verified outcomes?

If the answer is no because an observable field was not stored, the capture design is incomplete.
