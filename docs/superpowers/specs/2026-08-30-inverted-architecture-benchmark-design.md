# Inverted AI Architecture Benchmark — Design Specification

## Purpose

Determine, in one preregistered benchmark campaign, whether an architecture in which a non-model system generates or executes candidate outcomes and an AI model primarily audits those outcomes is materially more reliable than a conventional architecture in which the AI model directly chooses the actions.

The benchmark must be falsifiable. It returns exactly one operational verdict for the tested hypothesis: `SUPPORTED`, `REFUTED`, or `INCONCLUSIVE`. It does not claim universal mathematical proof across all domains.

## Primary hypothesis

Given identical natural-language goals, comparable evidence, the same model, and controlled resource budgets, a non-AI executor plus AI auditor will achieve a higher rate of correct final states and/or materially lower catastrophic false acceptance than direct AI execution, across multiple task families and increasing task complexity.

## Experimental arms

Every task/model/system-quality/seed condition is evaluated with six arms.

1. **A — AI Direct**: model chooses actions; no post-hoc semantic auditor.
2. **B — AI Direct + Deterministic Checks**: strongest conventional baseline; model chooses actions and deterministic invariants reject mechanically invalid states.
3. **C — System Alone**: deterministic candidate executor operates without an AI auditor.
4. **D — System + AI Auditor**: proposed inverted architecture. The non-AI system proposes/executes candidate outcomes; the model audits and may accept or reject candidates.
5. **E — System + Random Auditor**: control for improvements caused merely by rejection/retry opportunities.
6. **F — System + Oracle Auditor**: upper bound showing the maximum attainable performance with perfect auditing.

## Task families

The benchmark contains three independently generated families with machine-checkable hidden ground truth.

### State mutation

A synthetic computer-like state contains files, permissions, services, settings, and database records. Goals require one or more state transitions while preserving explicit and implicit invariants.

### Policy/procedure

Tasks are successful only when both the final state and required/forbidden procedure constraints are satisfied. This prevents an auditor from succeeding solely by looking at destination state.

### Reconciliation

Several structured data sources contain missing, contradictory, stale, or corrupted fields. The goal is a consistent resolved state subject to source-priority and integrity constraints.

## Complexity levels

Four preregistered levels are generated independently for each family.

- **L1:** 1–2 requirements, minimal distractors.
- **L2:** 3–5 requirements with at least one preservation constraint.
- **L3:** 6–9 requirements plus side effects and plausible distractors.
- **L4:** 10–15 requirements with adversarially plausible faults, misleading evidence, and non-local constraints.

Generation is seeded and deterministic. Held-out seeds are never embedded in prompts or examples.

## Executor quality sweep

The non-AI executor is evaluated at target candidate-quality levels of 0.20, 0.40, 0.60, 0.80, and 0.95. Quality is controlled by seeded fault injection into otherwise legal candidate executions. Actual realized quality is measured by the hidden oracle rather than assumed from the configured target.

Fault categories include:

- omitted requirement
- wrong target/value
- ordering/procedure violation
- preservation violation
- unintended side effect
- stale-source selection
- contradiction left unresolved
- permission/policy violation
- deceptive but superficially successful outcome
- compound fault

## Model requirements

The decisive campaign supports at least three model configurations spanning more than one model family and, where practical, more than one capacity tier. The exact same model configuration is used when comparing its executor and auditor roles.

Model adapters must support:

- Ollama/local HTTP APIs
- OpenAI-compatible chat-completions endpoints, including local servers and OpenRouter-style endpoints
- a deterministic mock adapter for CI and benchmark self-tests

Model/provider-specific telemetry is captured when exposed and represented as unavailable rather than fabricated when not exposed.

## Hidden oracle

Ground truth is deterministic program logic and is never supplied to model prompts. The oracle scores:

- final-state correctness
- individual requirement satisfaction
- preservation constraints
- procedure constraints
- critical/catastrophic violations
- injected-fault identity
- whether an auditor acceptance is a true positive or false positive

The oracle is the sole authority for benchmark correctness. No LLM judge defines the benchmark labels.

## Fairness and anti-confound controls

- Same task instances across comparable arms.
- Same model/version/configuration for executor-versus-auditor comparisons.
- Seeded randomized candidate ordering.
- Candidate formatting normalized so correctness is not signaled stylistically.
- Hidden oracle inaccessible to models.
- Adversarially plausible incorrect candidates.
- Multiple independent seeds and epochs.
- Equal-budget analysis in addition to unrestricted architectural analysis.
- Parser failures, retries, timeouts, and malformed tool/model outputs count as observed failures rather than being silently dropped.
- No post-hoc changes to primary verdict thresholds after results are observed.

## Telemetry and evidence contract

Every model call and system transition receives stable run, trial, candidate, and call identifiers. Raw event data is append-only JSONL so every aggregate can be independently recomputed.

### Per model call

Capture every field available from the serving backend, including:

- run/trial/candidate/call IDs
- model/provider/base URL label
- role (`executor`, `auditor`, other control role)
- request start/end timestamps
- wall latency
- time to first token when streaming/backend telemetry exposes it
- prompt/input token count
- completion/output token count
- total tokens
- reasoning tokens, cached tokens, prompt-cache hits/writes, or provider-specific token classes when exposed
- generated tokens per second
- end-to-end tokens per second
- provider-reported evaluation/load/prompt-evaluation durations where exposed
- HTTP/status/error class
- timeout flag
- retry number and retry reason
- finish/stop reason
- response parse success/failure and parse error
- request parameters affecting inference (temperature, top-p, max tokens, seed where supported)
- cost estimate only when a configured/provider price is known; unknown remains null
- raw provider usage metadata in a namespaced field

Prompts and model responses are optionally persisted under an explicit `--capture-content` switch because they may contain sensitive data in future real-world extensions. Synthetic benchmark runs enable it by default.

### Per candidate/system action

Capture:

- pre-state hash and serialized state
- requested goal/requirements
- candidate generation seed
- configured and realized executor quality
- action sequence
- action count
- state diff
- injected fault IDs/categories
- deterministic check results
- auditor decision, confidence if requested, cited failed requirements, and rationale
- random/oracle-control decision where applicable
- post-state hash and serialized state

### Per trial

Capture:

- architecture arm
- task family and complexity
- model configuration
- seed/epoch
- number of model calls
- candidate attempts/rejections
- total input/output/reasoning/total tokens
- total model latency and end-to-end latency
- aggregate generation throughput
- oracle correctness
- requirement-level accuracy
- catastrophic failure indicator
- auditor TP/TN/FP/FN classification where applicable
- failure reason taxonomy
- terminal status

### Run-level environment/provenance

Capture:

- benchmark version and git commit when available
- Python/platform information
- wall-clock start/end/duration
- configuration file and normalized effective configuration
- random seeds
- model endpoint/model identifiers
- relevant dependency versions
- concurrency settings
- capture-content setting
- errors and interrupted/incomplete-run status

## Metrics

At minimum, calculate and print/persist:

- task success rate
- requirement-level accuracy
- catastrophic failure rate
- auditor precision, recall, specificity, F1, false-positive rate, false-negative rate
- model call count
- retry/timeout/parser-failure counts
- candidate attempts and rejection rate
- input/output/reasoning/total tokens
- tokens per successful task
- mean/median/p50/p90/p95/p99 call and trial latency
- TTFT statistics where available
- generation tokens/second and end-to-end tokens/second
- wall-clock runtime
- optional known cost and cost per successful task
- failure counts and rates by taxonomy
- metrics sliced by arm, model, family, complexity, target executor quality, realized executor quality bin, and seed/epoch
- D-minus-A and D-minus-B absolute/relative deltas
- bootstrap 95% confidence intervals for primary rate differences
- effect sizes where appropriate
- crossover estimate: system-quality region in which D begins consistently outperforming A/B

The final console report must be exhaustive but structured: executive verdict first, then primary comparisons, reliability/crossover, model efficiency, auditor confusion matrices, latency/throughput, token/cost accounting, failure taxonomy, per-slice results, provenance, and paths to raw artifacts. Machine-readable CSV/JSON summaries accompany the human-readable report.

## Primary verdict rule

The preregistered primary comparison is Arm D versus Arm A. Arm B is a required strong-baseline secondary gate.

### SUPPORTED

All of the following must hold in the decisive campaign:

1. D exceeds A in overall task success by at least 10 percentage points.
2. The bootstrap 95% confidence interval for D−A excludes 0.
3. D beats A in at least 2 of 3 task families.
4. D beats random-auditor Arm E, establishing that semantic auditing contributes beyond retry mechanics.
5. D does not materially increase catastrophic false acceptance relative to A; a +2 percentage-point or larger increase fails this condition.
6. The D advantage over A remains positive under equal-token-budget analysis.
7. The direction of the D−A advantage reproduces across a majority of tested model configurations and a majority of independent seeds.
8. D is not more than 10 percentage points worse than B overall. If B decisively dominates D, the inversion is not supported as the preferred architecture even if D beats A.

### REFUTED

Return `REFUTED` when statistical power is adequate and any of the following decisive conditions holds:

- D fails to exceed A overall and the 95% CI rules out a +5 percentage-point advantage; or
- D fails to outperform E, indicating no demonstrated semantic-auditor contribution; or
- D increases catastrophic false acceptance by at least 2 percentage points; or
- D's apparent advantage becomes non-positive under equal-token-budget analysis; or
- D's advantage is confined to a single task family or single model configuration and fails the reproducibility gate.

### INCONCLUSIVE

Any completed decisive campaign satisfying neither `SUPPORTED` nor `REFUTED` returns `INCONCLUSIVE`. Incomplete campaigns never produce a positive or negative scientific verdict.

## Statistical power and stopping

The decisive configuration defines a minimum trial count per primary slice before verdict evaluation. Results are always printed for smaller/smoke runs, but those runs are explicitly labeled `NON-DECISIVE` and cannot emit `SUPPORTED` or `REFUTED`.

Primary uncertainty is estimated with seeded stratified bootstrap resampling over trial instances. The report includes the number of observations in every slice so sparse results cannot masquerade as certainty.

## Outputs

Each run writes a unique directory containing:

- `events.jsonl` — append-only raw event stream
- `model_calls.jsonl` — one normalized row per model call
- `trials.csv` and `trials.jsonl` — one row per completed trial
- `failures.csv` — all failed trials with taxonomy and evidence references
- `summary.json` — machine-readable aggregate results and verdict
- `summary.csv` — major sliced metrics
- `report.txt` — the exact exhaustive console report
- `config.json` — normalized effective configuration
- `provenance.json` — environment/version information

## Implementation constraints

- Python 3.11+.
- Prefer standard library; `httpx`, `PyYAML`, and `pytest` are acceptable lightweight dependencies.
- No agent framework, database, vector store, MCP layer, or external eval framework is required.
- CI must run entirely offline using deterministic mock models.
- Real model runs must never silently substitute a mock model.
- All randomized behavior must be reproducible from recorded seeds.
- A smoke configuration proves harness integrity; only the decisive configuration can produce a scientific verdict.
