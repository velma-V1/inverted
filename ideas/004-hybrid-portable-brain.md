# Idea 004 — Hybrid Portable Brain

**Build order:** 4 of 6  
**Status:** Depends on results from Ideas 001–003

## Hypothesis

The best external cognitive architecture will combine the strongest proven pieces of relational memory, portable task state, reusable procedural skills, and graph-based relationship retrieval while keeping one canonical evidence source.

## Core rule

The filesystem/evidence store is canonical. The graph is derived and rebuildable. No component may become an independent conflicting source of truth.

## Architecture

```text
PORTABLE_BRAIN/
├── manifest.yaml
├── working/
│   └── TASK_STATE.yaml
├── journal/
│   └── events.jsonl
├── episodes/
├── skills/
├── patterns/
├── edge-cases/
├── tools/
├── evidence/
│   └── immutable/
├── relational/
│   └── evidence-weighted.sqlite
├── graph/
│   └── derived.sqlite
└── indexes/
    ├── lexical.sqlite
    └── semantic.index
```

## Memory roles

```text
WORKING MEMORY
TASK_STATE
"What am I doing now?"

PROCEDURAL MEMORY
skills/ tools/
"How have I successfully done this?"

EPISODIC MEMORY
episodes/ journal/
"What actually happened?"

RELATIONAL MEMORY
relational/ + graph/
"What connects, causes, fixes, conflicts, or applies?"

EVIDENCE
evidence/
"Why should any of this be trusted?"
```

## Retrieval pipeline

```text
current task + task state
  ↓
lexical/semantic candidate retrieval
  ↓
relational utility lookup
  ↓
optional bounded graph expansion
  ↓
provenance + temporal validity filter
  ↓
rerank under strict context budget
  ↓
smallest sufficient context packet
```

## Consolidation

```text
raw experience
  ↓
candidate lesson/skill/relation
  ↓
verification
  ↓
held-out replay + counterexamples
  ↓
PASS
  ↓
promote canonical file/evidence
  ↓
rebuild/update relational + graph indexes
```

## Portability

The entire brain package is model-independent at the storage layer. A model adapter controls how much state/context a particular model receives. This permits tests such as:

```text
Qwen + mature brain
Gemma + same mature brain
fresh Qwen + same mature brain
```

## Guardrails

- Canonical evidence is immutable.
- Graph/index deletion must not destroy knowledge.
- Every retrieved item carries provenance and confidence.
- Component contribution is logged for ablation.
- No permanent promotion without held-out verification.
- Context compiler enforces a hard token budget.

## First experiment

Do not build this until Ideas 001–003 have isolated which primitives actually add value. Then compare:

1. Best single component.
2. Best two-component combination.
3. Full hybrid.

Use matched information budgets and component ablation.

## Primary metrics

- Task success
- Cross-task transfer
- Model-to-model transfer
- Context efficiency
- Retrieval precision
- Repeated failure reduction
- Component marginal contribution
- Regression rate

## Success gate

The hybrid must beat the best simpler architecture after controlling for token budget and stored information. If not, keep the simpler winner.

## Research basis

The design combines hierarchical memory, filesystem-backed agent memory, portable skill packages, graph memory, and evidence-gated consolidation. Its value is composition only if each component proves incremental benefit under ablation.
