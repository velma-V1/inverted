# Idea 004 — Compressed Recurring-Failure Capsules

**Status:** Seed

## Core hypothesis

When Codex finds enough failures with the same underlying mechanism, it can compress the useful causal pattern into a small reusable correction that helps Qwen avoid the entire failure class.

## Proposed workflow

1. Preserve all raw failure episodes.
2. Cluster failures by mechanism, not superficial prompt similarity.
3. Require a minimum repeated count before creating a capsule.
4. Build a compact failure capsule containing trigger signature, observed failure, likely cause, successful correction, and confidence.
5. Test the capsule against held-out failures plus unrelated controls.
6. Progressively compress the capsule to find the minimum useful correction signal.

## Starting threshold

Begin with at least 5 reproducible failures in one cluster and at least 3 held-out cases not used to construct the capsule.

## Candidate measurements

- Target failure reduction
- Generalization to unseen variants
- Regression on unrelated tasks
- Added prompt tokens
- Added latency
- Minimum capsule size that preserves the gain

## Important constraint

A capsule is never treated as ground truth merely because Codex created it. It must outperform baseline on held-out cases before it can be reused.
