# Hybrid Validation and Local Execution Design

## Goal

Use GitHub-hosted CI to exhaustively validate the inverted benchmark as a scientific instrument, then run only the irreducibly real-model portion on the local Windows/Ollama machine when Inverted itself is ready.

## Non-negotiable separation of evidence

GitHub synthetic/mock campaigns validate benchmark correctness, statistical behavior, determinism, failure handling, portability, and artifact integrity. They MUST NOT be reported as evidence that the inverted architecture outperforms direct AI execution. Only runs against real model endpoints may support/refute the architecture claim.

## Architecture

The system has two layers:

1. **Cloud instrument validation** — GitHub Actions runs unit/regression tests and deterministic known-answer stress campaigns. It uploads a validation evidence bundle containing pytest logs, generated benchmark artifacts, and machine-readable campaign summaries.
2. **Local real-model evidence collection** — the existing Inverted benchmark runs directly against Ollama with exact progress, durable checkpoints, safe resume after interruption, model-availability validation, and the normal ten evidence artifacts.

The two layers reuse the same task generator, arms, oracle, statistics, verdict, telemetry, and artifact writer. No parallel benchmark implementation is allowed.

## Experimental validity corrections

### Candidate pairing across models

Non-AI candidate generation MUST NOT depend on model identity. For a fixed task, epoch, seed, executor quality, arm-independent candidate attempt number, and run/campaign seed, all auditor models must receive the same candidate sequence. Model identity may remain in `trial_id` for uniqueness, but it cannot influence the RNG seed used by `C_SYSTEM`, `D_INVERTED`, `E_RANDOM_AUDITOR`, or `F_ORACLE_AUDITOR` candidate generation.

A regression test must prove that two different model identities receive byte-equivalent candidate action/state sequences for the same non-AI condition.

### Remove executor-quality duplication where quality is irrelevant

`A_DIRECT` and `B_DIRECT_CHECKED` do not consume the system executor quality parameter. They must run once per unique `(model, epoch, family, complexity, seed)` task rather than once at all five executor-quality levels.

`C_SYSTEM` is model-independent and must run once per unique `(epoch, family, complexity, quality, seed)` condition.

`E_RANDOM_AUDITOR` and `F_ORACLE_AUDITOR` are model-independent controls and must run once per unique `(epoch, family, complexity, quality, seed)` condition.

`D_INVERTED` remains model-dependent and spans all model x task x quality conditions.

Statistics must continue to use independent `task_id` clusters for primary confidence intervals and decisive power. Removal of duplicated rows must not change the definition of an independent task.

## Progress, checkpointing, and resume

The runner must expose exact progress based on a precomputed execution plan. Progress records include completed/total trial units, percentage, model, arm, family, complexity, quality, seed, and epoch.

After each completed trial unit, the runner appends a checkpoint record to durable JSONL. On restart with `--resume`, it reconstructs completed trial IDs/keys, skips them, and continues missing units only. A completed campaign must produce the same aggregate result as an uninterrupted campaign for deterministic/mock adapters.

A checkpoint is an execution-recovery artifact, not one of the final ten benchmark evidence files. Final artifacts remain the existing ten-file contract.

## GitHub validation matrix

GitHub Actions must run:

- Python 3.11, 3.12, and 3.14 where available.
- Ubuntu and Windows for the core unit/regression suite.
- Exact deterministic replay tests.
- Candidate-pairing invariance across model identities.
- Arm/model-order invariance.
- Clustered-bootstrap pseudoreplication attacks.
- Failure injection: malformed executor JSON, malformed auditor JSON, model errors, parser errors, token-budget exhaustion, and retry/rejection behavior.
- Artifact integrity and schema/row-count consistency.
- Known-answer campaigns whose expected verdict classes include `SUPPORTED`, `REFUTED`, `INCONCLUSIVE`, and `NON-DECISIVE`.
- Null-effect campaigns to detect false-positive support.
- Positive-effect recovery campaigns with controlled effect sizes.
- A large deterministic stress campaign across all task families, complexity levels, executor qualities, seeds, epochs, and six arms.

The stress campaign may use mock adapters only and must label its reports `INSTRUMENT VALIDATION — NOT ARCHITECTURE EVIDENCE`.

## GitHub evidence bundle

A dedicated workflow uploads one artifact bundle containing:

- pytest output/logs
- stress-run `summary.json`, `summary.csv`, `report.txt`, `config.json`, and `provenance.json`
- known-answer campaign summaries
- validation manifest with commit SHA, Python/OS matrix, test counts, campaign dimensions, expected/observed verdicts, and pass/fail state

Raw mock trial/model-call ledgers may be included when size remains practical; otherwise the final validation bundle must retain enough aggregate and manifest data to reproduce the run from the commit/config.

## Local real-model execution

Local execution must remain self-contained within Inverted and must:

1. verify the intended Inverted commit/config before inference;
2. verify Ollama is reachable and all configured models exist;
3. launch the real campaign with checkpoint/resume enabled;
4. stream exact progress and terminal output;
5. preserve interrupted runs for safe resume;
6. only report completion after exit code 0 and required final artifacts exist.

Primary model set for the first real campaign:

- `qwen3.5:9b-q8_0`
- `gemma3:12b`
- `devstral-small-2:24b`

## Success criteria

The implementation is ready for real inference only when:

- all new regression tests pass;
- GitHub core CI passes on its supported OS/Python matrix;
- cloud validation campaigns produce their expected verdicts and upload evidence;
- candidate-pairing invariance is proven by test;
- redundant model/quality-independent rows are absent from the execution plan;
- checkpoint/resume reproduces uninterrupted deterministic results;
- a smoke run shows exact progress and final ten artifacts;
- local real-model execution fails closed when Inverted prerequisites are missing.
