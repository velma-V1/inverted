# Test-4 Additions — Uncommon Data Probes

Status: **design additions only**. No Test-4 executable/spec currently exists in this repository under `test4`, `Test 4`, `TEST-4`, or `test_4`, so these probes define the three additions to integrate when the Test-4 baseline is created. They do not authorize model calls by themselves.

Goal: collect uncommon evidence that directly improves routing, verification, recovery, memory, and benchmark design rather than adding more ordinary pass/fail tasks.

## T4-X1 — Causal Fragility / Invariance-Fracture Map

### Question

Which apparently irrelevant representation changes cause the system to choose a different action, model, verifier, or recovery path?

### Method

Create matched causal pairs from the same underlying task and change exactly one nuisance variable at a time while preserving the required end state. Candidate transforms:

- object/key ordering where order is semantically irrelevant
- equivalent tool-result field ordering
- equivalent requirement ordering
- benign whitespace/formatting
- irrelevant metadata insertion/removal
- equivalent state serialization
- equivalent naming/label normalization where identity is preserved

Every pair must record whether the transform is proven semantics-preserving. A known semantic-changing transform is included as a positive control; identity is the negative control.

### Collect

- first action divergence step
- router/model/verifier/recovery flip
- success/failure flip
- catastrophic-outcome flip
- divergence persistence length
- final-state equivalence
- token/call/latency delta
- cache behavior delta
- confidence/calibration delta where available
- smallest perturbation that causes a decision flip
- feature/dependency lineage associated with the flip
- repeated-run stability of the flip
- transform class and intensity

### Improvement signal

Produces a fragility map showing where the controller relies on non-causal representation details. This is directly actionable for normalization, routing features, verifier placement, and adversarial benchmark generation.

---

## T4-X2 — Intervention Debt / Delayed-Credit Probe

### Question

Which actions look good immediately but create downstream repair debt, and which actions look neutral or costly immediately but prevent later failure?

### Method

For a matched trajectory, introduce or replay one permitted intervention at step `t` and score its effect at multiple future horizons rather than only at the next step or final outcome.

Each counterfactual remains classified as `CAUSAL_REPLAY`, `REQUIRES_NEW_INFERENCE`, or `INVALID_COUNTERFACTUAL`. No unobserved downstream model output may be treated as causal replay.

### Collect

- immediate outcome delta
- effect vector at `t+1`, `t+2`, …, terminal state
- first beneficial horizon
- first harmful horizon
- recovery/rework actions caused or avoided
- verifier debt: extra validation created or prevented
- routing debt: extra model switches created or prevented
- memory debt: stale/incorrect experience propagated or prevented
- failure propagation chain
- irreversible-branch indicator
- action reversal count
- downstream catastrophe delta
- cumulative calls/tokens/latency
- cost-to-benefit break-even horizon
- interaction effects with verifier, memory, routing, repair, and retry

### Improvement signal

Separates **locally attractive actions** from **globally useful actions**. This provides the evidence needed for horizon-aware routing, better recovery policies, and credit assignment across long agent trajectories.

---

## T4-X3 — Epistemic Conflict / Verifier-Arbitrage Probe

### Question

When validators disagree, which disagreement patterns predict real failure, corrupt success, unnecessary blocking, or the need for a different verifier?

### Method

Target cases where available evaluators disagree. Compare, when available:

- deterministic/schema validation
- execution/state validation
- semantic judging
- policy/procedure validation
- model self-confidence or self-check
- hidden-gold evaluation **for analysis only**

Hidden gold may never become a production routing feature or be visible before the evaluated decision.

### Collect

- full verifier-by-verifier conflict matrix
- verifier result, confidence, latency, and cost
- false-pass and false-block rates by failure class
- catastrophic false-pass rate
- disagreement topology and recurring verifier coalitions
- first verifier to detect the eventual failure
- verifier sensitivity to representation changes
- arbitration decision and arbitration regret
- dominant-verifier failure modes
- cases where majority vote is worse than a minority verifier
- cases where adding a verifier reduces accuracy
- procedure-valid but outcome-wrong cases
- outcome-correct but procedure-corrupt cases
- confidence-versus-correctness calibration

### Improvement signal

Finds when “more verification” is actively harmful and identifies which verifier should have authority for each failure class. This supports conditional verification instead of an expensive fixed verifier stack.

---

## Required shared controls

All three probes should include:

- identity/no-change control
- randomized irrelevant intervention control
- equal-call and equal-token comparisons where meaningful
- causal-twin grouping to prevent train/test leakage
- exact seed/config/model provenance
- raw event and decision traces
- temporal feature provenance
- integrity hashes
- retained instrumentation failures
- explicit missing-data fields rather than imputation

## Why these three

Together they expose three failure dimensions that ordinary benchmark accuracy largely misses:

1. **Fragility:** the system changes its mind for the wrong reason.
2. **Delayed consequence:** the system optimizes the next step instead of the trajectory.
3. **Epistemic conflict:** the system cannot tell which evaluator to trust.

Their outputs are intended to feed concrete changes to the controller, verifier policy, normalization layer, memory policy, recovery policy, and future benchmark task generation.
