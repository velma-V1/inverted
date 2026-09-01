# Idea 001 — Minimal Relational Brain

**Build order:** 1 of 6  
**Status:** Ready for detailed test design

## Hypothesis

A fixed Qwen3.5-9B can improve task performance if a tiny external relational substrate tracks states, relationships, transitions, and verified outcomes, then feeds only the highest-utility connected information back into the model.

## Design principle

Keep the substrate minimal enough that any gain can be attributed to relational state rather than a large memory stack.

```text
NODE + EDGE + STATE + TRANSITION + OUTCOME
```

## Data model

Use SQLite.

```text
NODE
- id
- kind
- content
- scope
- created_at
- source_evidence

EDGE
- src
- dst
- relation
- successes
- failures
- last_tested
- scope
- evidence_ids

TRANSITION
- from_state
- action
- to_state
- successes
- failures
- evidence_ids

ACTIVE_STATE
- task_id
- node_id
- activation
- updated_at
```

Do not store one arbitrary scalar weight. Store success/failure evidence counts and derive utility from them with a conservative Bayesian prior so one lucky success cannot create a permanently dominant path.

## Runtime

```text
task
  ↓
seed 3–8 relevant nodes
  ↓
spread activation across bounded edges
  ↓
rank by relevance × evidence-backed utility × recency
  ↓
return smallest useful connected packet to Qwen
  ↓
Qwen acts
  ↓
verifier scores outcome
  ↓
credit/blame only the path actually used
```

## Credit assignment

- Directly verified edge: full evidence update.
- Edge merely traversed as part of a successful path: partial evidence only.
- Edge present but unused: no update.
- Contradicted edge: failure evidence.
- High-value edges can later be ablated in controlled tests to estimate causal contribution.

Weak edges become dormant rather than deleted.

## Guardrails

- Every durable edge must point to evidence.
- Fan-out and traversal depth are hard-capped.
- No model-generated edge becomes trusted from a single episode.
- Qwen cannot directly overwrite historical evidence.
- Raw episodes remain available for audit.

## First experiment

Compare:

1. Qwen alone.
2. Qwen + relational brain.

Use repeated task families where useful transitions recur in altered forms. Include held-out transfer cases that require reusing a learned relationship without repeating the original wording.

## Primary metrics

- Success rate
- Repeated-failure rate
- Transfer to unseen related cases
- Wrong-path activation rate
- Tokens added per task
- Latency overhead
- Performance after removing high-utility edges

## Success gate

Proceed only if relational memory improves held-out task success with low wrong-path activation and the gain survives edge-ablation checks.

## Research basis

Relevant foundations include spreading-activation semantic memory, successor representations, reinforcement-weighted graph memory, and recent trainable graph-memory agent systems. The experiment deliberately strips these ideas to the smallest falsifiable substrate.
