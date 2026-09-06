# INVERTED Operating-Surface Evidence Frontier

**Status:** CURRENT PROJECT EVIDENCE STATE — 2026-09-05  
**Purpose:** Start future model-uplift experiments from the strongest defensible position supported by existing evidence.

This registry synthesizes Test 1, contaminated-but-diagnostic Test 2, valid Test 3 S2, Harvest A/B/C, Harvest D D2/D3/D4/R1, and HD-NEXT-1. The 2026-09-05 raw-ZIP audit additionally opened and cross-compared the preserved raw archives rather than relying on their summary reports.

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
   - Raw Harvest C makes the model-specific reversal explicit: Qwen DIRECT 51% -> CHECKED 94% while INVERTED reached 55%; Ministral DIRECT 8% -> CHECKED 16% but INVERTED 52%; Devstral DIRECT 33% -> CHECKED 81% / INVERTED 68%.

2. **Task/failure region changes the useful support. — ESTABLISHED**
   - HD-NEXT-1 Small-A promoted support scored 0/4 on `GLOBAL_INTERACTION` and 0/4 on `TRANSACTION`, while its raw baseline scored 4/4 and 3/4 respectively.
   - The same promoted support scored 3/3 on `EVIDENCE` and 2/3 on `AUTHORITY`.
   - Test 3 retains recurring policy/order and preservation-specific failure regions even when aggregate success is high.
   - Raw Harvest B shows regime-level sign reversal: for insufficient-only, no-valid-action, plausible-unsupported, and source-ambiguity cases, DIRECT was 0% while CHECKED and INVERTED were 100% across all three tested models; on adversarial cases DIRECT and CHECKED were 100% while INVERTED was 0% across all three models.

3. **More support is not monotonically better. — ESTABLISHED**
   - HD-NEXT-1 development and fresh results contain component removals and alternate support bundles that equal or outperform the promoted bundle.
   - Harvest B shows unnecessary evidence load exists even when evidence quality is useful.
   - Context/support must therefore be treated as a dose-response problem, not an inclusion checklist.
   - D3 answer-level matched diagnostics sharpen this: Qwen RAW beat the full I1-I10 packet on 2/8 matched cases (both GLOBAL_INTERACTION), and removing I5 or I8 rescued 3/8 matched Qwen cases; for Small-A, removing I1 harmed a GLOBAL_INTERACTION case. These are priors only because D3's disposition scorer was invalid.
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
   - Test 1 adds a second efficiency boundary: a checked/direct intervention improved Qwen by +20.0pp and policy tasks by +23.89pp while adding 0pp on saturated state/reconciliation tasks; a third checked retry recovered only 1/37 = 2.70%, making repeated retries a sharply diminishing-return region.

9. **Ceiling-saturated benchmarks cannot measure uplift well. — ESTABLISHED**
   - Test 1 had Qwen direct at 100%, Gemma direct/system-assisted at 100%, and Devstral direct/system-assisted at 100% in major arms.
   - Future model-uplift tests must deliberately operate in non-saturated regions where improvement and degradation are observable.

## Evidence that is useful but cannot be promoted

- **Test 2 matrices and role champions — DIAGNOSTIC_ONLY.** Its own verdict records `non_unique_physical_model_call_identity`, so model/representation/order/synergy tables are priors only.
- **D3 combined semantic verdicts — MEASUREMENT_RISK.** All 632 calls failed the bundled semantic contract because disposition ownership was scored against the model; answer-level/context observations remain diagnostic, but the run cannot certify recipe performance. The raw ZIP also shows its reproducibility calibration was NOT_RUN; D3.3 was 111/120 STATE-family calls; and several intended dedicated outputs are empty even though some equivalent metadata exists elsewhere. D3 therefore supplies targeted priors, not fine-grained operating-surface estimates.
- **Harvest A/B/C targeted repairs — system-responsibility evidence, not model-uplift proof.** They show deterministic recovery/correction can remove injected failures, but the correction often supplies the correct system action directly.
- **HD-NEXT-1 T2 factor marginals — DIAGNOSTIC_ONLY.** They come from a covering design with unequal/confounded factor exposure; use them to choose local neighborhoods, not as causal main effects.
## Dimension frontier

| Dimension | Current state | Most advanced defensible starting point |
|---|---|---|
| Ingredient/content identity | BROAD UNIVERSE UNDERRESOLVED | I1-I10 and prior A-series mechanisms are seed priors, not a closed vocabulary. Do not rerun the same old formulations broadly, but do expand the semantic ingredient universe with sparse matched discovery across models/regions before local optimization. Weak standalone performance is insufficient for retirement because enabling, recurrent, recovery, and state-triggered value may exist. |
| Evidence quality/source/trust | ESTABLISHED importance; UNDERRESOLVED delivery | Preserve provenance, freshness, contradiction, sufficiency, and authority class. Optimize how each model receives them rather than whether they matter. |
| Amount/dose | UNMAPPED TO REQUIRED RESOLUTION / MEASUREMENT_RISK | Do not credit D3 as a dose experiment: on five matched D3.3 model/case cells, MINIMUM, COMPRESSED, MODERATE, FULL, and OVERLOADED rendered to byte-identical information packets. HD-NEXT-1 has only coarse amount categories. True per-ingredient and total-support dose curves remain open. |
| Order/sequence | STRONG_DIAGNOSTIC_SIGNAL / UNDERRESOLVED | D3 gives useful one-pass ordering priors, but recurrence and stateful sequencing are essentially unmapped. Future work must allow reusable operators such as `A -> B -> A`, distinguish exact-repeat versus refreshed-repeat effects, and compare static packet order with progressive delivery after intermediate model/state transitions. |
| Timing | STRONG_SIGNAL / UNDERRESOLVED | D3 used genuinely different message geometry: on four matched Qwen STATE cases, JUST_IN_TIME rescued 3/4 and PRE_DECISION 1/4 versus UPFRONT, while PROGRESSIVE rescued 0/4. HD-NEXT-1 also favored pre-decision/JIT directionally. D3's scorer/noise limitations and state-heavy coverage prevent promotion. |
| Placement | MOSTLY UNMAPPED / UNDERRESOLVED | D3's 476 non-RAW information packets were all recorded as TASK_CONTEXT; its timing variants sometimes redistributed content between system/user messages, so timing and placement can be entangled. HD-NEXT-1 includes task/system/mixed levels but with shallow/confounded exposure. Dedicated placement remains open. |
| Representation | STRONG_DIAGNOSTIC_SIGNAL / UNDERRESOLVED | D3 matched Qwen STATE cases: ADMISSIBLE_ACTION_MATRIX rescued 2/4 relative to TYPED_FIELDS; compressed summary, decision table, decomposition, explicit alternatives, minimal ledger, and raw prose each rescued 1/4; priority block and strict JSON rescued 0/4. Test 2 also shows model×representation differences but is contaminated. Robust model×task confirmation remains open. |
| Context length / useful-token ratio / position | UNMAPPED TO SUFFICIENT DEPTH | D3 did create overload, redundant-history, and token-matched-irrelevant controls, but they were not matched against a same-case TARGET baseline in D3.7 and its main amount labels were often literal no-ops. Dense length, useful-token ratio, and critical-information-position curves remain open. |
| Pairwise/higher-order interactions | ESTABLISHED importance; UNDERRESOLVED map | Pairwise coverage exists, but enabling, suppression, replacement, recurrence, and higher-order path structure are not mapped to required depth. High-order search should deepen from observed edges while preserving protected exploration of weak/reversed/repeated combinations. |
| Task/failure family | ESTABLISHED conditionality | `GLOBAL_INTERACTION`, `TRANSACTION`, `VERIFIER_ORACLE`, policy ordering, preservation, and structural dependency regions are high-information non-saturated targets. |
| Structural complexity | STRONG_SIGNAL | Existing data shows model/role behavior changes with complexity, but some older matrices are contaminated. Use objective descriptors such as dependency depth, requirement count, action-space size, irreversibility, and interaction layers rather than one coarse difficulty label. |
| Model-specific data needs | ESTABLISHED | Optimize Small-A and Qwen independently against their own raw baselines. Additional models are transition/diagnostic probes, not templates that define another model's recipe. |
| Model state / failure state / routing state | STRONG_SIGNAL | Rich public evidence-state routing is the strongest clean signal. The next surface map should condition support on observable state rather than only static task labels. |
| Deterministic assistance A1–A11 | CONDITIONAL / UNDERRESOLVED for cognition | System-level replay is cheap and useful; whether exposing/using each assistance mechanism improves each model's cognition must be measured separately. |
| Recovery pipeline | ESTABLISHED importance; CONDITIONAL model behavior | Deterministic recovery can be extremely effective, while repeated model repair can damage preservation or leave policy-order requirements unsolved. Detection, diagnosis, candidate generation, selection, execution, and verification must remain separate. |
| Negative transfer | ESTABLISHED existence; boundary UNDERRESOLVED | Extra support, I9, overload, and alternate bundles change sign across development/fresh/family regimes. Observable switch conditions are not yet mapped tightly. |
| Latency/tokens/compute | ESTABLISHED necessity | Local dumps now provide direct hardware priors: HD-NEXT-1 Small-A ~0.09s/call, Qwen ~33.97s/call; Qwen D3 long-output stress ~77.22s/call; Devstral 24B warm median <9s but cold/model-swap behavior can add ~30s load time. Use `docs/LOCAL_RUNTIME_EVIDENCE.md`; runtime may shape scheduling but not delete valuable scientific coverage. |
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

## Raw ZIP audit and equivalence findings — 2026-09-05

The preserved ZIP archives were opened and compared at raw-record level before further test design.

- **12 project-relevant ZIPs were inventoried.** `D3-COMPLETE-CAMPAIGN.zip` and the quarantined `harvest-d-d3-evidence.zip` are byte-identical copies (same SHA-256), so they are one empirical source, not two runs.
- **Test 1 raw equivalence verified.** The META packet's `ALL-6480-TRIALS.jsonl` and the COMPLETE packet's `derived/trials-complete.jsonl` contain exactly the same 6,480 parsed trial records in the same order. The 615 MB `Test1Evidence.zip` identifies the same run/checkpoint and its first embedded raw checkpoint record exactly matches the COMPLETE packet.
- **Test 2 forensic equivalence verified.** All eight core raw JSONL streams match the current repo semantically record-for-record: 452 model calls, 452 prompts, 452 responses, 400 trials, 482 events, 216 candidates, 72 repairs, and 208 validator results. The historical non-unique-call-identity contamination therefore remains the correct evidence disposition.
- **Test 3 S2 equivalence verified.** ZIP versus repo: 720 model calls, 720 raw transactions, 720 routing snapshots, 720 events, 732 external actions, and five parse/composition failures are semantically identical. The 6,530-row forensic journal differs only in regenerated hash-chain fields; removing `record_sha256`/`previous_sha256` leaves zero semantic differences.
- **Focused/zero-call D3 ZIPs add no inference observations.** They contain source/tests or zero-byte run-data streams. `INVERTED_entire_chat_condensed.zip` is design/history context, not empirical model evidence.
- **The S2/A/B/C full dump contains unique high-value raw slices not exposed by summary tables.** Those slices are incorporated into this frontier, especially the Harvest B regime sign reversals and Harvest C model-specific support reversals.

## Local runtime evidence â€” 2026-09-05

Raw dump telemetry was mined to estimate this machine's actual model-call behavior. The canonical planning record is `docs/LOCAL_RUNTIME_EVIDENCE.md`.

- HD-NEXT-1: 467 calls, ~31.7 minutes summed inference; Small-A 412 calls at ~0.09s average, Qwen 55 calls at ~33.97s average.
- D4/R1 independently place Qwen near ~33s/call in their calibration regimes; D3 is the long-output stress case at ~77.22s average across 383 Qwen calls.
- Devstral Small 2 24B has 904 measured Harvest A/B/C calls. Warm/resident median latency is 8.75s (609 calls; p90 10.84s), while Harvest C median load duration was ~30.57s and drove median total latency to 39.27s.
- Test 3 S2 completed 720 model calls in 1h 11m 49s wall-clock; Harvest A/B/C completed 912/900/900 calls in 1h 10m / 59m / 6h 03m respectively, showing scheduling/model residency can dominate raw call count.

Operational consequence: batch same-model work when scientifically safe, randomize treatments within model blocks, preserve warm/cold/load telemetry, and forecast both normal and stress regimes. **Do not narrow a valuable experiment merely to save wall-clock time.**

## Highest-value unresolved frontier

The current frontier is no longer `which broad mechanism might help?`.

It is:

> **For each model and non-saturated operating region, what exact conditional combination of information, dose, reusable sequence/recurrence, static or progressive layering, timing, placement, representation, assistance, and state-triggering maximizes the defensible Pareto frontier—and where does that combination change or become harmful?**

That question must be answered with matched own-baseline controls, explicit noise-floor calibration, model×task/state interaction measurement, and fresh/sealed confirmation. Compression/minimum-equivalent support comes only after the performance frontier is mapped.
