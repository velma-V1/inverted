from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from .config import CAMPAIGN_RUN_CEILING
from .contracts import DifficultyVector, TrialResult
from .evidence import append_jsonl, write_json, write_manifest
from .frontier import FrontierSampler
from .taskgen import GRAMMARS, generate_task
from .task_manifest import freeze_task, verify_task
from .verifier import evaluate_process, verify_outcome

PHASES = (
    "preflight", "frontier", "harvest", "localize", "ablate",
    "candidate_dev", "holdout", "complete",
)


def load_task_payload(task_root: Path) -> dict:
    task_root = Path(task_root).resolve()
    data = json.loads((task_root / "task.json").read_text(encoding="utf-8"))
    data["_task_root"] = str(task_root)
    return data


def _copy_workspace(task_root: Path, target: Path) -> Path:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(Path(task_root) / "workspace", target)
    return target
class CampaignController:
    def __init__(self, output_dir: Path, run_ceiling: int = CAMPAIGN_RUN_CEILING, resume: bool = True):
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint = self.output_dir / "checkpoint.json"
        self.events = self.output_dir / "campaign_events.jsonl"
        self.run_ceiling = int(run_ceiling)
        self.state = {"phase": "preflight", "agent_runs": 0, "completed_trials": [], "invalid_trials": []}
        if resume and self.checkpoint.exists():
            self.state = json.loads(self.checkpoint.read_text(encoding="utf-8"))

    @property
    def phase(self) -> str:
        return self.state["phase"]

    def save(self) -> None:
        write_json(self.checkpoint, self.state)

    def advance(self, phase: str) -> None:
        if phase not in PHASES:
            raise ValueError(phase)
        current = PHASES.index(self.phase)
        target = PHASES.index(phase)
        if target < current:
            raise RuntimeError("campaign phases cannot move backward")
        self.state["phase"] = phase
        append_jsonl(self.events, {"event": "phase", "phase": phase})
        self.save()

    def reserve_run(self, trial_id: str, arm: str) -> None:
        if self.state["agent_runs"] >= self.run_ceiling:
            raise RuntimeError("campaign agent-run ceiling reached")
        self.state["agent_runs"] += 1
        append_jsonl(self.events, {"event": "agent_run_reserved", "trial_id": trial_id, "arm": arm, "count": self.state["agent_runs"]})
        self.save()

    def record_trial(self, result: TrialResult) -> None:
        record = {"trial_id": result.trial_id, "arm": result.arm, "status": result.status, "outcome_passed": result.outcome_passed, "process_passed": result.process_passed}
        if result.status in {"ABORTED_INFRASTRUCTURE", "INVALID_EVIDENCE"}:
            self.state["invalid_trials"].append(record)
        else:
            self.state["completed_trials"].append(record)
        append_jsonl(self.events, {"event": "trial", **record})
        self.save()
def execute_scored_trial(controller: CampaignController, adapter, task_root: Path, run_dir: Path, seed: int) -> TrialResult:
    task_root = Path(task_root).resolve()
    if verify_task(task_root):
        raise RuntimeError("task manifest mismatch")
    task = load_task_payload(task_root)
    arm = getattr(adapter, "arm", type(adapter).__name__)
    controller.reserve_run(task["id"], arm)
    arm_root = Path(run_dir) / task["id"] / arm
    workspace = _copy_workspace(task_root, arm_root / "workspace")
    evidence_dir = arm_root / "evidence"
    result = adapter.run(workspace, task, evidence_dir, seed=seed)
    outcome = verify_outcome(task, workspace) if result.status == "COMPLETE" else None
    events = result.events
    if not events and hasattr(adapter, "normalize_evidence"):
        events = adapter.normalize_evidence(evidence_dir)
    process = evaluate_process(task, events, result.status)
    result.outcome_passed = bool(outcome and outcome.passed)
    result.process_passed = process.passed
    result.events = events
    result.metadata.update({"grammar": task["grammar"], "task_root": str(task_root), "outcome": asdict(outcome) if outcome else None, "process": asdict(process)})
    write_json(arm_root / "scored_result.json", asdict(result))
    controller.record_trial(result)
    return result


def generate_frontier_pool(root: Path, count: int, seed: int = 310000) -> list[Path]:
    root = Path(root)
    roots: list[Path] = []
    for index in range(count):
        grammar = GRAMMARS[index % len(GRAMMARS)]
        level = 1 + index // max(1, len(GRAMMARS) * 3)
        d = DifficultyVector(
            constraints=1 + min(level, 4),
            dependency_depth=1 + min(level, 4),
            mutation_depth=1 + min(level, 3),
            stale_evidence_risk=min(level, 4),
            distractors=min(level, 5),
            repair_branching=1 + min(level, 3),
            negative_constraints=min(level, 3),
            evidence_ambiguity=min(level, 3),
            tool_pressure=min(level, 3),
            temporal_depth=min(level, 3),
            downstream_interaction=min(level, 3),
            ontology_novelty=min(level, 4),
        )
        task_root = root / f"task-{index:03d}"
        generate_task(grammar, d, seed + index, task_root)
        freeze_task(task_root)
        roots.append(task_root)
    return roots
def _remaining(controller: CampaignController) -> int:
    return max(0, controller.run_ceiling - int(controller.state["agent_runs"]))


def _clean_failure(result: TrialResult) -> bool:
    return result.status == "COMPLETE" and not (result.outcome_passed and result.process_passed)


def _clean_pass(result: TrialResult) -> bool:
    return result.status == "COMPLETE" and result.outcome_passed and result.process_passed


def _task_root_from_result(result: TrialResult) -> Path:
    return Path(result.metadata["task_root"])


def _best_teacher(claude: TrialResult, codex: TrialResult) -> TrialResult | None:
    if _clean_pass(claude) and _clean_pass(codex):
        return claude if (claude.wall_seconds or 1e9) <= (codex.wall_seconds or 1e9) else codex
    if _clean_pass(claude):
        return claude
    if _clean_pass(codex):
        return codex
    return None
def _trial_from_json(path: Path) -> TrialResult:
    from .contracts import AgentEvent
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    payload["events"] = [AgentEvent(**event) if isinstance(event, dict) else event for event in payload.get("events", [])]
    return TrialResult(**payload)


def execute_or_load_trial(controller: CampaignController, adapter, task_root: Path, run_dir: Path, seed: int) -> TrialResult:
    task = load_task_payload(task_root)
    arm = getattr(adapter, "arm", type(adapter).__name__)
    scored = Path(run_dir) / task["id"] / arm / "scored_result.json"
    if scored.exists():
        append_jsonl(controller.events, {"event": "resume_existing_trial", "trial_id": task["id"], "arm": arm})
        return _trial_from_json(scored)
    return execute_scored_trial(controller, adapter, task_root, run_dir, seed)
def run_campaign_replay(controller: CampaignController, adapter, task_root: Path, intervention, replay_root: Path, repetitions: int, seed: int):
    from .contracts import ReplayResult
    task = load_task_payload(task_root)
    passes = 0
    evidence_ids = []
    for rep in range(repetitions):
        controller.reserve_run(task["id"], f"{adapter.arm}:{intervention.kind}")
        target = Path(replay_root) / intervention.intervention_id / f"rep-{rep:02d}"
        workspace = _copy_workspace(task_root, target / "workspace")
        result = adapter.run_intervention(workspace, task, intervention, seed + rep)
        passed = _clean_pass(result)
        passes += int(passed)
        write_json(target / "result.json", asdict(result))
        evidence_id = f"{intervention.intervention_id}:rep-{rep:02d}:{int(passed)}"
        evidence_ids.append(evidence_id)
        append_jsonl(controller.events, {"event":"replay","evidence_id":evidence_id,"task_id":task["id"],"arm":adapter.arm,"kind":intervention.kind,"passed":passed})
        controller.save()
    return ReplayResult(intervention.intervention_id, repetitions, passes, repetitions-passes, passes/repetitions if repetitions else 0.0, evidence_ids)
def _spec_for_root(task_root: Path):
    from .contracts import TaskSpec
    payload = load_task_payload(task_root)
    return TaskSpec(
        task_id=payload["id"], grammar=payload["grammar"], seed=int(payload["seed"]),
        difficulty=DifficultyVector(**payload["difficulty"]), root=str(Path(task_root).resolve()),
    )


def _load_results(paths: list[str]) -> list[TrialResult]:
    return [_trial_from_json(Path(path)) for path in paths]


def _score_path(run_root: Path, task_root: Path, arm: str) -> Path:
    task = load_task_payload(task_root)
    return Path(run_root) / task["id"] / arm / "scored_result.json"


def _ensure_generated_pool(root: Path, count: int, seed: int) -> list[Path]:
    root = Path(root)
    existing = sorted(p for p in root.glob("task-*") if (p / "task.json").exists()) if root.exists() else []
    if len(existing) == count and all(not verify_task(p) for p in existing):
        return existing
    return generate_frontier_pool(root, count, seed)
def run_campaign(config: dict, output_dir: Path, resume: bool = True, adapters: dict | None = None) -> dict:
    from .adapters import QwenBrainAdapter, ClaudeRawAdapter, CodexRawAdapter
    from .constraint_ledger import build_constraint_ledger
    from .divergence import localize_critical_divergence
    from .interventions import plan_interventions
    from .mechanisms import extract_candidate, validate_candidate
    from .retention import decide_retention

    output_dir = Path(output_dir).resolve()
    controller = CampaignController(output_dir, int(config.get("run_ceiling", CAMPAIGN_RUN_CEILING)), resume=resume)
    write_json(output_dir / "config.json", config)
    adapters = adapters or {
        "qwen": QwenBrainAdapter(),
        "claude": ClaudeRawAdapter(),
        "codex": CodexRawAdapter(),
    }
    task_root = output_dir / "sealed_tasks"
    run_root = output_dir / "runs"
    run_root.mkdir(parents=True, exist_ok=True)

    if controller.phase == "preflight":
        controller.advance("frontier")

    if controller.phase == "frontier":
        pool = _ensure_generated_pool(task_root / "frontier", int(config.get("frontier_pool", 60)), 310000)
        specs = [_spec_for_root(p) for p in pool]
        sampler = FrontierSampler(seed=771)
        remaining = list(specs)
        results: list[TrialResult] = []
        passes = 0; failures = 0
        while remaining and _remaining(controller) > 0:
            batch = sampler.next_batch(remaining, min(6, len(remaining)))
            for spec in batch:
                result = execute_or_load_trial(controller, adapters["qwen"], Path(spec.root), run_root, spec.seed)
                results.append(result)
                sampler.observe(spec, _clean_pass(result))
                passes += int(_clean_pass(result)); failures += int(_clean_failure(result))
                remaining.remove(spec)
            if failures >= int(config.get("harvest_cases", 20)) and passes >= 6:
                break
        paths = [str(_score_path(run_root, _task_root_from_result(r), r.arm)) for r in results]
        write_json(output_dir / "frontier_index.json", {"result_paths": paths, "passes": passes, "failures": failures})
        controller.advance("harvest")
    if controller.phase == "harvest":
        frontier_meta = json.loads((output_dir / "frontier_index.json").read_text(encoding="utf-8"))
        frontier_results = _load_results(frontier_meta["result_paths"])
        failures = [r for r in frontier_results if _clean_failure(r)]
        failures.sort(key=lambda r: sum(DifficultyVector(**load_task_payload(_task_root_from_result(r))["difficulty"]).key()))
        selected = failures[: int(config.get("harvest_cases", 20))]
        harvest_rows = []
        for qwen in selected:
            root = _task_root_from_result(qwen)
            seed = int(load_task_payload(root)["seed"])
            if _remaining(controller) < 2:
                break
            claude = execute_or_load_trial(controller, adapters["claude"], root, run_root, seed)
            codex = execute_or_load_trial(controller, adapters["codex"], root, run_root, seed)
            harvest_rows.append({
                "task_root": str(root),
                "qwen_result": str(_score_path(run_root, root, qwen.arm)),
                "claude_result": str(_score_path(run_root, root, claude.arm)),
                "codex_result": str(_score_path(run_root, root, codex.arm)),
            })
        write_json(output_dir / "harvest_index.json", harvest_rows)
        controller.advance("localize")

    if controller.phase == "localize":
        rows = json.loads((output_dir / "harvest_index.json").read_text(encoding="utf-8"))
        divergences = []
        for row in rows:
            qwen = _trial_from_json(Path(row["qwen_result"]))
            claude = _trial_from_json(Path(row["claude_result"]))
            codex = _trial_from_json(Path(row["codex_result"]))
            teacher = _best_teacher(claude, codex)
            if teacher is None:
                continue
            task = load_task_payload(Path(row["task_root"]))
            ledger = build_constraint_ledger(task, qwen.events)
            divergence = localize_critical_divergence(qwen.events, teacher.events, ledger, task)
            if divergence.confidence <= 0 or not divergence.candidate_behavior:
                continue
            divergences.append({
                "task_root": row["task_root"],
                "teacher_arm": teacher.arm,
                "divergence": asdict(divergence),
            })
        write_json(output_dir / "divergences.json", divergences)
        controller.advance("ablate")
    if controller.phase == "ablate":
        from .contracts import CriticalDivergence
        rows = json.loads((output_dir / "divergences.json").read_text(encoding="utf-8"))
        chosen = None
        candidate_payload = None
        for row in rows[:10]:
            if _remaining(controller) < 4:
                break
            divergence = CriticalDivergence(**row["divergence"])
            root = Path(row["task_root"])
            teacher = adapters["claude"] if row["teacher_arm"].startswith("CLAUDE") else adapters["codex"]
            specs = plan_interventions(divergence, [])
            remove = next(s for s in specs if s.kind == "remove")
            force = next(s for s in specs if s.kind == "force")
            teacher_remove = run_campaign_replay(controller, teacher, root, remove, output_dir / "replays" / divergence.task_id / "teacher_remove", 2, 510000)
            qwen_force = run_campaign_replay(controller, adapters["qwen"], root, force, output_dir / "replays" / divergence.task_id / "qwen_force", 2, 520000)
            candidate = extract_candidate(divergence, [teacher_remove, qwen_force])
            candidate_payload = asdict(candidate)
            write_json(output_dir / "candidate_attempts" / f"{divergence.task_id}.json", candidate_payload)
            if candidate.status == "causally_supported" and not validate_candidate(candidate):
                chosen = candidate
                break
        if chosen is None:
            write_json(output_dir / "candidate.json", candidate_payload or {"status":"none_supported"})
            controller.advance("complete")
        else:
            write_json(output_dir / "candidate.json", asdict(chosen))
            controller.advance("candidate_dev")

    if controller.phase == "candidate_dev":
        from .contracts import MechanismCandidate
        from .adapters import QwenBrainAdapter
        candidate = MechanismCandidate(**json.loads((output_dir / "candidate.json").read_text(encoding="utf-8")))
        dev_roots = _ensure_generated_pool(task_root / "candidate_dev", 6, 710000)
        addendum = f"{candidate.trigger}. REQUIRED BEHAVIOR: {candidate.replacement_behavior}."
        factory = adapters.get("candidate_factory") if isinstance(adapters, dict) else None
        candidate_adapter = factory(addendum) if callable(factory) else QwenBrainAdapter(candidate_addendum=addendum)
        candidate_adapter.arm = "QWEN_BRAIN_CANDIDATE"
        base_results = []; cand_results = []
        for root in dev_roots:
            seed = int(load_task_payload(root)["seed"])
            base_results.append(execute_or_load_trial(controller, adapters["qwen"], root, run_root, seed))
            cand_results.append(execute_or_load_trial(controller, candidate_adapter, root, run_root, seed))
        lift = sum(1 for b,c in zip(base_results,cand_results) if not _clean_pass(b) and _clean_pass(c))
        regressions = sum(1 for b,c in zip(base_results,cand_results) if _clean_pass(b) and not _clean_pass(c))
        write_json(output_dir / "candidate_dev.json", {"lift":lift,"regressions":regressions})
        if lift >= 1 and regressions <= 1:
            candidate.status = "dev_passed"
            write_json(output_dir / "candidate.json", asdict(candidate))
            controller.advance("holdout")
        else:
            candidate.status = "rejected"
            write_json(output_dir / "candidate.json", asdict(candidate))
            controller.advance("complete")
    if controller.phase == "holdout":
        from .contracts import MechanismCandidate
        from .adapters import QwenBrainAdapter
        candidate = MechanismCandidate(**json.loads((output_dir / "candidate.json").read_text(encoding="utf-8")))
        holdout_count = int(config.get("fresh_holdout", 24))
        holdout_roots = _ensure_generated_pool(task_root / "fresh_holdout", holdout_count, 910000)
        write_json(output_dir / "holdout_freeze.json", {
            "task_roots": [str(p) for p in holdout_roots],
            "manifests": {str(p): json.loads((p / "manifest.json").read_text(encoding="utf-8")) for p in holdout_roots},
        })
        addendum = f"{candidate.trigger}. REQUIRED BEHAVIOR: {candidate.replacement_behavior}."
        factory = adapters.get("candidate_factory") if isinstance(adapters, dict) else None
        candidate_adapter = factory(addendum) if callable(factory) else QwenBrainAdapter(candidate_addendum=addendum)
        candidate_adapter.arm = "QWEN_BRAIN_CANDIDATE"
        base_results = []; cand_results = []
        for root in holdout_roots:
            if _remaining(controller) < 2:
                break
            seed = int(load_task_payload(root)["seed"])
            base_results.append(execute_or_load_trial(controller, adapters["qwen"], root, run_root, seed))
            cand_results.append(execute_or_load_trial(controller, candidate_adapter, root, run_root, seed))
        decision = decide_retention(candidate, base_results, cand_results)
        candidate.status = "retained" if decision.retained else ("bounded" if decision.bounded_scope and not decision.reasons else "rejected")
        write_json(output_dir / "retention_decision.json", asdict(decision))
        write_json(output_dir / "candidate.json", asdict(candidate))
        controller.advance("complete")

    if controller.phase == "complete":
        write_json(output_dir / "summary.json", {
            "phase": controller.phase,
            "agent_runs": controller.state["agent_runs"],
            "valid_trials": len(controller.state["completed_trials"]),
            "invalid_trials": len(controller.state["invalid_trials"]),
            "candidate": json.loads((output_dir / "candidate.json").read_text(encoding="utf-8")) if (output_dir / "candidate.json").exists() else None,
            "retention": json.loads((output_dir / "retention_decision.json").read_text(encoding="utf-8")) if (output_dir / "retention_decision.json").exists() else None,
        })
        write_manifest(output_dir)
    return json.loads((output_dir / "summary.json").read_text(encoding="utf-8")) if (output_dir / "summary.json").exists() else {"phase": controller.phase, "agent_runs": controller.state["agent_runs"]}
