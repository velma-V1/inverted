# Inverted Brain vNext Harvest Compiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** Evolve the isolated Inverted Brain branch from a Claude/Codex-only Brain-rule harvester into a typed architecture-harvest pipeline that can learn from systems, books, skills, tools, and hands without contaminating the original Inverted experiment.

**Architecture:** Preserve the existing causal replay and fresh-transfer machinery. Add a typed learning compiler that routes validated findings to Brain, System, Skill, Tool/Hand, Memory, or Negative Evidence; add a harvest-source catalog and vNext architecture specification; keep actual integration of third-party runtimes out of this change.

**Tech Stack:** Python 3.11+, dataclasses, pytest, YAML/Markdown configuration, existing Inverted-Brain evidence/registry code.

**Spec:** `docs/inverted-brain/2026-09-06-inverted-brain-vnext-harvest-compiler-design.md`

## Global Constraints
- Do not modify `src/inverted/`, original benchmark configs, or historical evidence.
- Existing Frontier Mechanism Harvest evidence/spec remains historical and is not rewritten to match later discoveries.
- Qwen3.5-9B remains the fixed substrate for architecture comparisons unless a later experiment preregisters otherwise.
- A source can generate hypotheses; only causal/transfer evidence can authorize promotion into Brain/System behavior.
- Full teacher trajectories, leaked prompts, or book text are never installed as Brain laws.
- Every learned artifact keeps provenance, scope, boundary conditions, counterevidence, and verification requirements.
- Skills/tools/hands are future capability layers; this change defines their contracts and routing, not unrestricted execution.

---

### Task 1: Restore Clean Test Isolation

**Files:** rename colliding Brain test filename; remove accidental test package marker.

- [x] Rename `tests/inverted_brain/test_cli.py` to `test_brain_cli.py`.
- [x] Remove `tests/inverted_brain/__init__.py` so it cannot shadow `src/inverted_brain`.
- [x] Run complete repository suite and require 156/156 green.
### Task 2: Typed Learning Artifact Contracts

**Files:**
- Modify: `src/inverted_brain/contracts.py`
- Create: `tests/inverted_brain/test_learning_compiler.py`

**Interfaces:**
- `LearningDestination`: BRAIN, SYSTEM, SKILL, TOOL_HAND, MEMORY, NEGATIVE_EVIDENCE.
- `LearnedArtifact`: immutable typed output with provenance, scope, boundaries, failure modes, verification obligations, and cost.

- [x] Write failing tests for destination values, serialization-safe fields, and mandatory provenance/evidence.
- [x] Run the focused tests and require RED because the new contracts do not exist.
- [x] Add only the minimal dataclass/type definitions needed by those tests.
- [x] Re-run and require GREEN.

### Task 3: Deterministic Learning Compiler

**Files:**
- Create: `src/inverted_brain/learning_compiler.py`
- Extend: `tests/inverted_brain/test_learning_compiler.py`

**Interfaces:**
- `compile_finding(candidate, finding_kind, provenance, boundary_conditions, failure_modes, verification) -> LearnedArtifact`
- Accepted kinds map deterministically: reasoning policy -> Brain; invariant/governance -> System; repeatable procedure -> Skill; executable capability -> Tool/Hand; durable fact -> Memory; rejected/failed mechanism -> Negative Evidence.

- [x] Write failing tests for all six routes and for rejection of unsupported or evidence-free findings.
- [x] Require RED.
- [x] Implement the minimal mapping and validation.
- [x] Require GREEN and ensure rejected mechanisms can be preserved as Negative Evidence rather than discarded.
### Task 4: Harvest Source Catalog and vNext Architecture

**Files:**
- Create: `configs/inverted_brain/harvest_sources.yaml`
- Create: `docs/inverted-brain/2026-09-06-inverted-brain-vnext-harvest-compiler-design.md`
- Create: `docs/inverted-brain/README.md`

- [x] Record source roles and harvest targets for Codex, Claude Code/Agent SDK, Prime Agent, Pi, oh-my-cli, SWE-agent, AegisEvo, Aider, book-to-skill, Taste Skill, Comet MCP, media-inference-worker, Hyperspace AGI, Prime Verifiers/prime-rl, and Weinberg's *The Psychology of Computer Programming*.
- [x] Mark unauthenticated prompt dumps as hypothesis sources only, never authority.
- [x] Specify Brain/System/Skill/Tool-Hand/Memory boundaries, production-vs-learning split, provenance model, anti-lock-in meta-reasoning requirement, and future fine-tuning path.
- [x] State that system ranking is secondary to mechanism decomposition, causal testing, interaction/order testing, and complexity rent.

### Task 5: Regression and Instrument Verification

**Files:** existing test suite and instrument only.

- [x] Run `pytest tests/inverted_brain -q`: 57/57 green.
- [x] Run full repository `pytest -q`: 171/171 green.
- [x] Run the non-scientific instrument smoke; audit PASS, zero manifest mismatches, explicitly NOT BRAIN EVIDENCE.
- [x] Verify branch diff contains no edits under `src/inverted/` or original benchmark/evidence paths.
- Remote publication is intentionally deferred; publish only on explicit operator instruction.

## Acceptance
- Existing causal harvest remains usable and historically traceable.
- New findings cannot be retained without an explicit destination and evidence provenance.
- Rejected mechanisms become negative evidence rather than disappearing.
- The architecture has explicit interfaces for future skills, tools, hands, distributed workers, and eventual Qwen weight tuning.
- No live scientific campaign is started by this update.