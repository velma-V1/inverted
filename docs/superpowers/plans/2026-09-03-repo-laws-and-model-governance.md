# INVERTED Repository Laws and Model Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish one canonical repository-root law/rulebook that governs future AI work and make every existing AI entrypoint deterministically reference it.

**Architecture:** Keep governance centralized in `REPO_LAWS_AND_REGULATIONS.md`. Existing root/model-specific instruction files become thin loaders, while a small pytest contract prevents the pointers from silently drifting or disappearing. `MODEL_OPERATING_RULES.md` is retained only for backward compatibility.

**Tech Stack:** Markdown, Python stdlib `pathlib`, pytest, GitHub repository instruction surfaces.

**Spec:** `docs/superpowers/specs/2026-09-03-repo-laws-and-model-governance-design.md`

## Global Constraints

- One canonical source of truth: `REPO_LAWS_AND_REGULATIONS.md`.
- The laws must encode project loyalty, user-strength amplification, opposite-weakness compensation, research/data-specialist behavior, complexity rent, convergence, and shipping discipline.
- Include verbatim principles `My suggestion is a floor, not a ceiling` and `Data collection is cheap; retesting is not` with guardrails against scope inflation and indiscriminate collection.
- Preserve historical evidence and existing experiment-specific frozen constraints.
- Do not create a new runtime agent/orchestration framework.
- Keep model-specific entrypoints short; do not duplicate the law text.

---

### Task 1: Canonical repository law file

**Files:**
- Create: `REPO_LAWS_AND_REGULATIONS.md`

**Interfaces:**
- Consumes: current INVERTED objectives, evidence hierarchy, permanent operating rules, user-strength/weakness assessment.
- Produces: canonical governance path `REPO_LAWS_AND_REGULATIONS.md` referenced by every AI entrypoint.

- [ ] **Step 1: Write the canonical law document**

Include, in durable project-level form:

- authority and amendment rules;
- project loyalty and smallest-strongest-system objective;
- user suggestion floor law;
- cheap-data/retesting law;
- evidence hierarchy and claim discipline;
- no-self-certification and semantic-correctness rules;
- contradiction/failure/verified-state laws;
- automatic task-mode routing;
- research and data-collection operating protocol;
- architecture and complexity-rent admission gates;
- experiment and verification standards;
- user-strength multiplier and weakness-countermeasure map;
- convergence/stop/freeze/ship rules;
- communication and decision contract;
- explicit noncompliance/promotion rule.

- [ ] **Step 2: Self-review the law file**

Verify there is no internal contradiction between:

- suggestion-as-floor versus stopping rules;
- evidence capture versus privacy/sealed-test integrity;
- extreme research depth versus convergence;
- project loyalty versus the user's authority to explicitly redefine the project;
- smallest system versus sufficient redundancy for independent verification.

- [ ] **Step 3: Commit**

```bash
git add REPO_LAWS_AND_REGULATIONS.md
git commit -m "docs: establish canonical inverted repo laws"
```

---

### Task 2: Point all AI entry surfaces at the canonical law

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `.github/copilot-instructions.md`
- Modify: `MODEL_OPERATING_RULES.md`

**Interfaces:**
- Consumes: `REPO_LAWS_AND_REGULATIONS.md`.
- Produces: consistent automatic discovery/loading path for generic agents, Claude, Copilot, and older references.

- [ ] **Step 1: Replace duplicated governance summaries with short mandatory loaders**

Each AI-specific file must require reading `REPO_LAWS_AND_REGULATIONS.md` before meaningful design, research, testing, analysis, or implementation.

- [ ] **Step 2: Preserve backward compatibility**

Replace `MODEL_OPERATING_RULES.md` with a short compatibility notice stating that its former contents have been superseded by `REPO_LAWS_AND_REGULATIONS.md` and that the canonical file must be followed.

- [ ] **Step 3: Update README visibility**

Place the AI governance entrypoint near the top of `README.md`; explicitly state that the root law file is canonical and model-specific loaders are pointers only.

- [ ] **Step 4: Commit**

```bash
git add README.md AGENTS.md CLAUDE.md .github/copilot-instructions.md MODEL_OPERATING_RULES.md
git commit -m "docs: route all model entrypoints through repo laws"
```

---

### Task 3: Deterministic governance contract test

**Files:**
- Create: `tests/test_repo_governance.py`

**Interfaces:**
- Consumes: repository root instruction files.
- Produces: pytest failure if the canonical law file disappears, loses core laws, or an automatic AI entrypoint no longer references it.

- [ ] **Step 1: Write the failing governance test**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = "REPO_LAWS_AND_REGULATIONS.md"
ENTRYPOINTS = (
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    "MODEL_OPERATING_RULES.md",
)


def test_canonical_repo_laws_exist_and_preserve_core_principles() -> None:
    text = (ROOT / CANONICAL).read_text(encoding="utf-8")
    assert "My suggestion is a floor, not a ceiling" in text
    assert "Data collection is cheap; retesting is not" in text
    assert "smallest" in text.lower()
    assert "ship" in text.lower()


def test_all_model_entrypoints_reference_canonical_repo_laws() -> None:
    for relative_path in ENTRYPOINTS:
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert CANONICAL in text, relative_path
```

- [ ] **Step 2: Run test and verify it fails before pointer migration is complete**

Run:

```bash
pytest -q tests/test_repo_governance.py
```

Expected before implementation: failure because `REPO_LAWS_AND_REGULATIONS.md` and/or all pointers are not yet present.

- [ ] **Step 3: Complete Tasks 1-2 and rerun**

Run:

```bash
pytest -q tests/test_repo_governance.py
```

Expected: PASS.

- [ ] **Step 4: Run full regression suite**

Run:

```bash
pytest -q
```

Expected: PASS with no benchmark behavior changed by documentation/governance work.

- [ ] **Step 5: Commit**

```bash
git add tests/test_repo_governance.py
git commit -m "test: enforce canonical model governance entrypoints"
```

---

### Task 4: Final adversarial governance review

**Files:**
- Review: `REPO_LAWS_AND_REGULATIONS.md`
- Review: all entrypoint files
- Review: `tests/test_repo_governance.py`

**Interfaces:**
- Consumes: completed governance implementation and test output.
- Produces: promotion decision for this governance layer.

- [ ] **Step 1: Attack the design**

Attempt to falsify these claims:

- a future model can determine its work mode without the user re-explaining project departments;
- broad research is amplified without authorizing endless search;
- user suggestions force improvement search without forcing architecture growth;
- cheap data capture reduces retest risk without authorizing unsafe/contaminating collection;
- project loyalty can override a low-value request without overriding an explicit objective/law amendment;
- the governance layer itself earns its complexity.

- [ ] **Step 2: Verify no duplicate canonical source remains**

Search repository-root AI instruction files for large duplicated rule blocks. The only full canonical governance source must be `REPO_LAWS_AND_REGULATIONS.md`.

- [ ] **Step 3: Verify repository tests**

```bash
pytest -q tests/test_repo_governance.py
pytest -q
```

Both must pass before declaring completion.

- [ ] **Step 4: Final disposition**

Promote only if the result is simpler than the prior duplicated rule arrangement while materially improving model role selection, evidence discipline, research behavior, convergence, and shipping alignment.
