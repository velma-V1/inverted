# Harvest D D2 Closure — Model Capability Frontier

Status: **FROZEN FOR D3 ENTRY**

D2 admissible-call use: **56 / 70**. The remaining 14 calls are intentionally unspent because the adaptive frontier reached diminishing information value.

## Measurement validity

The original v1 18-call SMALL_A seed run is retained as harness-diagnostic evidence only. It is not admissible for capability-boundary claims because exact JSON equality collapsed format/schema/semantic failure modes.

All capability claims below use `HARVEST-D-LAYERED-SCORING-v2` with frozen generation settings:

- temperature: 0.0
- seed: 20260902
- context: 4096
- retries: 0

## Observed frontier

### Full 18-case development seed

- `qwen2.5:1.5b-instruct-q8_0`: 2/18 semantic successes; 7/18 disposition correct; 7/18 answer correct.
- `qwen3.5:9b-q8_0`: 10/18 semantic successes; 10/18 disposition correct; 11/18 answer correct.

Transition classes:

- BOTH: 2
- QWEN_GAIN: 8
- NEITHER: 8

### Adaptive localization of QWEN_GAIN cases

- `ministral-3:3b-instruct-2512-q8_0`: solved 5/8 QWEN_GAIN cases.
- Residual 3B→9B set: F1-002, F1-004, F7-002.
- `phi4-mini:3.8b`: solved 2/3 residual cases.
- Remaining residual: F7-002, where 3.8B produced the correct answer but wrong disposition.
- `qwen3:8b`: solved F7-002.

Interpretation: most of the raw 1.5B→9B gap collapses by roughly the 3–4B range, but model-family effects remain confounded. F7-002 is not intrinsically 9B-only.

### NEITHER residual ceiling

On the 8 cases missed by both 1.5B and 9B, `qwen3:14b` recovered only 1/8 (F3-004).

Persistent 14B residual classification:

- 5 answer-right / disposition-wrong
- 1 both-wrong
- 1 disposition-right / answer-wrong
- 1 recovered

The five answer-right / disposition-wrong cases are:

- F3-002
- F6-004
- F8-002
- F8-004
- F9-004

## D2 conclusion

The residual frontier is not well explained by parameter count alone. Increasing from 9B to 14B repaired only one of eight hard residuals, while five of the seven persistent failures retained the correct semantic answer but selected the wrong system disposition.

This is sufficient evidence to stop D2 early and hand the persistent residuals to D3 as architecture-substitution targets. The highest-information first D3 mechanism is a deterministic post-model disposition compiler because it directly attacks the dominant observed failure mode without changing model reasoning.

## Claims not authorized

D2 does **not** establish a universal parameter threshold, does not prove 3.8B is equivalent to 9B, and does not certify any model family outside this development pool. Fresh-family generalization remains required later in Harvest D.
