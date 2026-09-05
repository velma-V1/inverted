# INVERTED Operating-Surface Evidence Frontier

**Status:** CURRENT PROJECT EVIDENCE STATE — 2026-09-05  
**Purpose:** Start future model-uplift experiments from the strongest defensible position supported by existing evidence.

This registry synthesizes Test 1, contaminated-but-diagnostic Test 2, valid Test 3 S2, Harvest A/B/C, Harvest D D2/D3/D4/R1, and HD-NEXT-1.

## Evidence classes

- **ESTABLISHED** — sufficiently strong to constrain future design; do not broadly retest.
- **STRONG_SIGNAL** — replicated or clean directional evidence, but not enough for a general promotion claim.
- **CONDITIONAL** — effect clearly depends on model/task/state or has a known boundary.
- **DIAGNOSTIC_ONLY** — useful for hypothesis targeting, not confirmatory claims.
- **UNDERRESOLVED** — tested, but resolution/power/matching is inadequate for the project objective.
- **UNMAPPED** — materially important region not directly measured.
- **MEASUREMENT_RISK** — old result is confounded by scoring, identity, saturation, or protocol limitations.

Historical frozen runs remain historical truth for the protocols they actually executed; this registry does not rewrite them.
## Highest-confidence project findings

1. **Models have materially different response surfaces. — ESTABLISHED**
   - D2 showed the 1.5B→9B gap is not a simple parameter-size threshold: 3B/3.8B/8B models solved different residuals, while 14B recovered only 1/8 of the 1.5B+9B shared failures.
   - HD-NEXT-1 fresh evidence showed the same support treatment behaving very differently on Small-A and Qwen.
   - Test 3 S2 showed different interventions/models win different failure states.

2. **Task/failure region changes the useful support. — ESTABLISHED**
   - HD-NEXT-1 Small-A promoted support scored 0/4 on `GLOBAL_INTERACTION` and 0/4 on `TRANSACTION`, while its raw baseline scored 4/4 and 3/4 respectively.
   - The same promoted support scored 3/3 on `EVIDENCE` and 2/3 on `AUTHORITY`.
   - Test 3 retains recurring policy/order and preservation-specific failure regions even when aggregate success is high.

3. **More support is not monotonically better. — ESTABLISHED**
   - HD-NEXT-1 development and fresh results contain component removals and alternate support bundles that equal or outperform the promoted bundle.
   - Harvest B shows unnecessary evidence load exists even when evidence quality is useful.
   - Context/support must therefore be treated as a dose-response problem, not an inclusion checklist.
4. **Evidence quality/trust/freshness is a first-class ingredient. — ESTABLISHED at system level; model recipe UNDERRESOLVED**
   - Harvest B measured provenance conflict, stale evidence, majority-wrong evidence, forged authority, source ambiguity, and insufficient evidence.
   - Targeted deterministic correction generalized without regression in that campaign.
   - What remains unresolved is exactly how each model should receive that evidence: amount, form, order, timing, and placement.

5. **State, dependency, authority, consequence, and recovery information are high-value regions. — ESTABLISHED as responsibility/failure domains**
   - Harvest A exposed state/dependency/preservation/recovery failures.
   - Harvest C exposed authority/scope/chained-risk/irreversibility failures.
   - These domains should seed operating-surface experiments; future work should not spend calls rediscovering that they matter.

6. **Rich observable state can improve routing. — STRONG_SIGNAL**
   - Valid Test 3 S2: rich-evidence-state routing reached 71/72 = 98.61%, versus 69/72 for fixed and family-only routing.
   - It also preserved zero catastrophes, but the frozen promotion threshold was not met, so the result remains a strong signal rather than a promoted router.

7. **Runtime stochasticity is nonzero even at temperature 0. — ESTABLISHED**
   - R1 reproducibility calibration found 1 unstable cell out of 6 repeated model/case cells.
   - Fine-grained recipe claims must therefore estimate a noise floor with repeated matched cells before interpreting small deltas.
8. **The performance frontier is multi-objective. — ESTABLISHED operational requirement**
   - D4 Qwen policy evidence showed DEFAULT at 14/24 versus THINK_OFF at 10/24, but THINK_OFF eliminated six context-exhaustions and reduced median latency from roughly 77.7 seconds to roughly 0.4 seconds.
   - Test 3 S2 likewise produced accuracy/latency/token tradeoffs between router arms.
   - Future analysis must preserve Pareto-optimal points rather than collapse all metrics into one winner.

9. **Ceiling-saturated benchmarks cannot measure uplift well. — ESTABLISHED**
   - Test 1 had Qwen direct at 100%, Gemma direct/system-assisted at 100%, and Devstral direct/system-assisted at 100% in major arms.
   - Future model-uplift tests must deliberately operate in non-saturated regions where improvement and degradation are observable.

## Evidence that is useful but cannot be promoted

- **Test 2 matrices and role champions — DIAGNOSTIC_ONLY.** Its own verdict records `non_unique_physical_model_call_identity`, so model/representation/order/synergy tables are priors only.
- **D3 combined semantic verdicts — MEASUREMENT_RISK.** All 632 calls failed the bundled semantic contract because disposition ownership was scored against the model; answer-level/context observations remain diagnostic, but the run cannot certify recipe performance.
- **Harvest A/B/C targeted repairs — system-responsibility evidence, not model-uplift proof.** They show deterministic recovery/correction can remove injected failures, but the correction often supplies the correct system action directly.
- **HD-NEXT-1 T2 factor marginals — DIAGNOSTIC_ONLY.** They come from a covering design with unequal/confounded factor exposure; use them to choose local neighborhoods, not as causal main effects.
## Dimension frontier

| Dimension | Current state | Most advanced defensible starting point |
|---|---|---|
| Ingredient/content identity | CONDITIONAL / UNDERRESOLVED | I1–I10 and A1–A11 already define useful candidate families. Do not restart binary inclusion screening; deepen model×task conditional effects around historical high-value regions. |
| Evidence quality/source/trust | ESTABLISHED importance; UNDERRESOLVED delivery | Preserve provenance, freshness, contradiction, sufficiency, and authority class. Optimize how each model receives them rather than whether they matter. |
| Amount/dose | UNDERRESOLVED | Existing levels are only coarse categories. Overload can hurt, but no dense dose curve or model×family dose optimum exists. |
| Order/sequence | UNDERRESOLVED | Coarse orders exist; Test 2 ordering is contaminated and HD-NEXT-1 is shallow. Exact sequence and interaction with dose/timing remain open. |
| Timing | STRONG_SIGNAL / UNDERRESOLVED | Small-A screening strongly favored pre-decision/JIT over upfront, but matching is inadequate. Real progressive multi-step delivery was explicitly uncovered in HD-NEXT-1. |
| Placement | STRONG_SIGNAL / UNDERRESOLVED | Task/system/mixed differences exist, but placement is confounded with other factors and almost untested dynamically. |
| Representation | STRONG_SIGNAL / UNDERRESOLVED | Matrix/JSON/structured forms repeatedly look promising in some roles/models, but robust matched model×task confirmation is missing. |
| Context length / useful-token ratio / position | UNMAPPED to insufficient depth | Controls were designed in D3 but not resolved into promotable evidence. Dense length and critical-information-position curves remain open. |
| Pairwise/higher-order interactions | ESTABLISHED importance; UNDERRESOLVED map | Pairwise coverage exists, but HD-NEXT-1 showed sign changes after fresh transfer and across families. High-order interactions must be targeted from observed contradictions, not exhaustively enumerated. |
| Task/failure family | ESTABLISHED conditionality | `GLOBAL_INTERACTION`, `TRANSACTION`, `VERIFIER_ORACLE`, policy ordering, preservation, and structural dependency regions are high-information non-saturated targets. |
| Structural complexity | STRONG_SIGNAL | Existing data shows model/role behavior changes with complexity, but some older matrices are contaminated. Use objective descriptors such as dependency depth, requirement count, action-space size, irreversibility, and interaction layers rather than one coarse difficulty label. |
| Model-specific data needs | ESTABLISHED | Optimize Small-A and Qwen independently against their own raw baselines. Additional models are transition/diagnostic probes, not templates that define another model's recipe. |
| Model state / failure state / routing state | STRONG_SIGNAL | Rich public evidence-state routing is the strongest clean signal. The next surface map should condition support on observable state rather than only static task labels. |
| Deterministic assistance A1–A11 | CONDITIONAL / UNDERRESOLVED for cognition | System-level replay is cheap and useful; whether exposing/using each assistance mechanism improves each model's cognition must be measured separately. |
| Recovery pipeline | ESTABLISHED importance; CONDITIONAL model behavior | Deterministic recovery can be extremely effective, while repeated model repair can damage preservation or leave policy-order requirements unsolved. Detection, diagnosis, candidate generation, selection, execution, and verification must remain separate. |
| Negative transfer | ESTABLISHED existence; boundary UNDERRESOLVED | Extra support, I9, overload, and alternate bundles change sign across development/fresh/family regimes. Observable switch conditions are not yet mapped tightly. |
| Latency/tokens/compute | ESTABLISHED necessity | Qwen is orders of magnitude slower than Small-A in current local runs; support policies must report correctness gain together with inference time, tokens, memory/compute, and model calls. |
| Fresh/sealed transfer | UNDERRESOLVED | HD-NEXT-1 reached fresh evidence but stopped before sealed confirmation; many older signals are development-only or contaminated. Future promotion needs independent fresh and sealed confirmation after discovery. |
## Questions that should not consume broad new-call budgets

Do not rerun broad experiments merely to establish that:

- models differ by capability and failure region;
- evidence provenance/freshness/sufficiency matters;
- state, dependency, authority, consequence, verification, and recovery matter;
- more context/support can create negative transfer;
- richer observable state can matter for routing;
- latency/token burden can materially change the preferred operating point;
- temperature 0 does not guarantee perfectly stable outcomes;
- one universal recipe is unlikely to be optimal across models and task families.

New calls are justified only when they increase **resolution**: dose curves, conditional switch points, exact sequencing, timing/placement, representation, higher-order interactions, state-dependent policies, or fresh/sealed transfer.

## Highest-value unresolved frontier

The current frontier is no longer `which broad mechanism might help?`.

It is:

> **For each model and non-saturated operating region, what exact conditional combination of information, dose, sequence, timing, placement, representation, assistance, and state-triggering maximizes the defensible Pareto frontier—and where does that combination change or become harmful?**

That question must be answered with matched own-baseline controls, explicit noise-floor calibration, model×task/state interaction measurement, and fresh/sealed confirmation. Compression/minimum-equivalent support comes only after the performance frontier is mapped.
