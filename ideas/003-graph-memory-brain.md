# Idea 003 — Graph Memory Brain

**Build order:** 3 of 6  
**Status:** Ready for detailed test design

## Hypothesis

Explicit relational retrieval will help Qwen reuse multi-hop knowledge, failure patterns, and dependencies that flat files or semantic retrieval alone do not surface reliably.

## Architecture

Use SQLite first. Do not introduce a graph server until scale proves it necessary.

```text
NODE
- id
- type
- title
- payload_ref
- confidence
- source_evidence
- valid_from
- valid_to

EDGE
- src
- dst
- relation
- confidence
- evidence_count
- evidence_ids
- valid_from
- valid_to
```

Recommended node types:

```text
TASK
FAILURE
SOLUTION
SKILL
FACT
TOOL
CONSTRAINT
PATTERN
OUTCOME
```

Recommended relations:

```text
CAUSES
FIXED_BY
FAILED_WITH
REQUIRES
CONFLICTS_WITH
APPLIES_TO
SUPERSEDES
SIMILAR_TO
VALIDATED_BY
```

## Source of truth

The graph is not allowed to become an unauditable memory blob. Every node/edge must reference source evidence or a source file. Temporal replacement is represented with validity intervals rather than destructive overwrite.

## Retrieval

```text
query/task state
  ↓
seed nodes via lexical + semantic match
  ↓
expand at most 1–2 hops
  ↓
filter invalid/stale/weak edges
  ↓
rank paths by relevance + evidence + specificity
  ↓
deduplicate
  ↓
return 5–15 highest-value facts/relationships
```

Hard-cap traversal depth and fan-out to prevent graph-noise amplification.

## Write path

```text
raw episode/evidence
  ↓
candidate entities + relations
  ↓
validation against source
  ↓
duplicate/conflict check
  ↓
write provisional node/edge
  ↓
repeated evidence or explicit verification
  ↓
promote confidence
```

## Guardrails

- No provenance-free durable edge.
- No silent overwrite; use `SUPERSEDES` + temporal validity.
- Conflicting claims coexist with confidence/evidence until resolved.
- Retrieval logs exactly which graph paths influenced Qwen.
- Graph can be rebuilt from canonical evidence/files.
- Periodic orphan, contradiction, and high-fan-out audits.

## First experiment

Compare:

1. Qwen baseline.
2. Qwen + flat retrieved memory with the same information budget.
3. Qwen + graph retrieval.

Tasks must require relationships, not merely recall: dependency chains, recurring failure mechanisms, superseded facts, multi-step tool requirements, and cross-task transfer.

## Primary metrics

- Held-out task success
- Multi-hop retrieval accuracy
- Wrong-edge retrieval rate
- Contradiction handling
- Token/latency overhead
- Performance at increasing graph size

## Success gate

Graph retrieval must beat a flat-memory control containing the same underlying information. If it only wins by providing more context, the graph hypothesis is not supported.

## Research basis

The design follows temporal knowledge-graph memory, dynamic linked-memory systems, and graph-RAG findings while deliberately avoiding heavyweight graph infrastructure until the relational advantage is proven.
