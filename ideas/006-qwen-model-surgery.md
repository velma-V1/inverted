# Idea 006 — Qwen Model Surgery

**Build order:** 6 of 6  
**Status:** Deferred until recurring failures survive external cognitive fixes

## Hypothesis

If a reproducible Qwen failure can be localized to a repeatable internal mechanism, the smallest causal intervention at that mechanism can reduce the failure class without unacceptable collateral regression.

## Scope

This is a laboratory path, not a production runtime feature. Use an instrumentable Hugging Face checkpoint for internal work; retain Q4/Q8 deployment models as controls.

## Architecture

```text
CLEAN RUN                 FAILURE RUN
    │                         │
    └────────────┬────────────┘
                 ▼
         synchronized telemetry
                 ▼
         candidate divergence
                 ▼
          causal patch sweep
                 ▼
      reproducible mechanism?
          │             │
         NO            YES
          │             ▼
       reject      minimal intervention
                        ▼
                  held-out related suite
                        ▼
                  broad regression suite
```

## Instrumentation targets

Start with per-layer/token summaries and escalate only around interesting windows. For Qwen3.5, candidate targets include residual streams, attention outputs, and Gated DeltaNet signals such as q/k/v, beta, log-decay, recurrence output, and block outputs where the tooling exposes them.

## Causal localization

Use paired prompts that differ by exactly one controlled variable. When possible, patch an activation/state from a successful run into the corresponding location in a failing run.

A location becomes interesting only when the same intervention repeatedly converts failure to success on related held-out cases.

## Intervention ladder

Always choose the least invasive method that works:

```text
1. activation/state patch
2. inference-time steering/gating
3. learned small gate/adapter
4. LoRA
5. targeted parameter edit
6. structural/topology modification
```

Do not jump directly to weight edits.

## Regression firewall

Every candidate intervention must be evaluated against:

- target failure suite
- unseen related cases
- general reasoning
- instruction following
- coding
- tool use
- long context
- structured output
- safety/alignment behavior

A local repair that materially damages broad capability is rejected.

## Evidence requirements

- Exact model hash and runtime recorded.
- Deterministic paired controls where possible.
- Full intervention provenance.
- Repeated causal effect, not correlation only.
- Untouched baseline model preserved.
- Modified checkpoint isolated and versioned.

## First experiment

Select one failure class that:

1. occurs reproducibly,
2. survives Ideas 001–005 or is clearly model-internal,
3. has clean success/failure controls,
4. matters enough to justify invasive work.

Perform activation patching/localization first. Stop if no reproducible causal locus emerges.

## Primary metrics

- Target repair rate
- Held-out generalization
- Broad regression
- Intervention magnitude
- Quantized deployment retention
- Reproducibility across seeds/prompts

## Success gate

A surgery is retained only if it produces a repeatable causal improvement on held-out cases with negligible unacceptable regression and survives re-quantization/deployment comparison.

## Research basis

The design follows causal tracing/model editing, activation engineering, and mechanistic-interpretability intervention methods. It is intentionally last because external state, memory, retrieval, and mentoring are cheaper, safer, and easier to reverse.
