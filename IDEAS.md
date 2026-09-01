# Qwen Experimental Ideas

This is the architecture index for experimental Qwen cognition, memory, mentoring, and model-modification work that may follow the real Inverted benchmark.

These experiments are deliberately isolated from the preregistered Inverted benchmark. They do **not** change its design, arms, or evidence contract.

## Build order

The IDs encode intended build/test order: **001 is first; 006 is last.** Each later architecture is justified only by evidence from earlier, cheaper experiments.

| Build | Architecture | Status | File |
|---:|---|---|---|
| **001** | Minimal Relational Brain | Ready for detailed test design | [ideas/001-minimal-relational-brain.md](ideas/001-minimal-relational-brain.md) |
| **002** | Portable Cognitive Workspace | Ready for detailed test design | [ideas/002-portable-cognitive-workspace.md](ideas/002-portable-cognitive-workspace.md) |
| **003** | Graph Memory Brain | Ready for detailed test design | [ideas/003-graph-memory-brain.md](ideas/003-graph-memory-brain.md) |
| **004** | Hybrid Portable Brain | Depends on 001–003 evidence | [ideas/004-hybrid-portable-brain.md](ideas/004-hybrid-portable-brain.md) |
| **005** | Live Codex Intervention | Controlled side experiment after memory/state work | [ideas/005-live-codex-intervention.md](ideas/005-live-codex-intervention.md) |
| **006** | Qwen Model Surgery | Last-resort invasive experiment | [ideas/006-qwen-model-surgery.md](ideas/006-qwen-model-surgery.md) |

## Escalation logic

```text
001 Minimal Relational Brain
        ↓
002 Portable Cognitive Workspace
        ↓
003 Graph Memory Brain
        ↓
004 Hybrid Portable Brain
        ↓
005 Live Codex Intervention
        ↓
006 Qwen Model Surgery
```

The sequence deliberately moves from cheap, reversible external structure toward expensive, invasive intervention.

## Shared experimental rule

Use one common cognitive-test harness wherever possible. Keep the same Qwen model, prompts, seeds, task distributions, verifier, telemetry, token budgets, and scoring. Swap only the cognitive backend/intervention being tested so gains can be causally attributed.

Every architecture file should ultimately progress through:

1. hypothesis,
2. evidence basis,
3. exact architecture,
4. matched controls,
5. test protocol,
6. success/failure gates,
7. regression analysis,
8. implementation,
9. measured results,
10. final disposition: keep, simplify, combine, or reject.

## Non-contamination rule

Do not modify the active preregistered Inverted decisive campaign to test these ideas. Run them only as separate follow-on experiments after the real benchmark completes.
