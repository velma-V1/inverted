from __future__ import annotations

import json
import random
import shutil
from dataclasses import asdict
from pathlib import Path

from .contracts import DifficultyVector, TaskSpec
from .task_manifest import prompt_fingerprint

GRAMMARS = (
    "dependency_repair",
    "stale_state",
    "constraint_interaction",
    "evidence_selection",
    "reconciliation",
    "interface_novelty",
)


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _answer_token(rng: random.Random) -> str:
    return f"ANS_{rng.getrandbits(64):016x}"


def _generic_verifier() -> str:
    return '''import json\nimport sys\nfrom pathlib import Path\n\nworkspace = Path(sys.argv[1])\ngold = json.loads((Path(__file__).with_name("gold.json")).read_text())\nproblems = []\nfor rel, expected in gold["expected_files"].items():\n    path = workspace / rel\n    actual = path.read_text(encoding="utf-8") if path.exists() else None\n    if actual != expected:\n        problems.append({"file": rel, "expected": expected, "actual": actual})\nfiles = sorted(p.relative_to(workspace).as_posix() for p in workspace.rglob("*") if p.is_file())\nfor forbidden in gold.get("forbidden_files", []):\n    if forbidden in files:\n        problems.append({"forbidden_file": forbidden})\npassed = not problems\nprint(json.dumps({"passed": passed, "problems": problems, "files": files}, sort_keys=True))\nsys.exit(0 if passed else 1)\n'''


def _dependency_repair(rng: random.Random, d: DifficultyVector):
    depth = max(1, d.dependency_depth)
    nodes = [f"node_{i}" for i in range(depth + 1)]
    target = rng.randint(30, 99)
    mapping = {nodes[i]: nodes[i + 1] for i in range(depth)}
    mapping[nodes[-1]] = target
    for i in range(d.distractors):
        mapping[f"decoy_{i}"] = rng.randint(100, 999)
    config = {"primary": rng.randint(1, 9), "fallback": rng.randint(10, 19), "version": 3, "active": -1}
    expected = dict(config)
    expected["active"] = target
    prompt = (
        "Repair config.json only. Follow the dependency chain beginning at node_0 in "
        "dependency_map.json until it reaches an integer, set config.active to that integer, "
        "and preserve every other config field exactly. Do not create files."
    )
    files = {"config.json": config, "dependency_map.json": mapping}
    return prompt, files, {"config.json": json.dumps(expected, indent=2, sort_keys=True) + "\n"}, ["preserve_other_fields", "follow_dependency_chain"]


def _stale_state(rng: random.Random, d: DifficultyVector):
    current_generation = 10 + max(1, d.stale_evidence_risk)
    current_value = rng.randint(100, 999)
    source = {"generation": current_generation, "value": current_value, "authoritative": True}
    snapshot = {"generation": current_generation - 1, "value": current_value + rng.randint(1, 20), "authoritative": False}
    result = {"selected_generation": 0, "value": None, "audit": "preserve-me"}
    expected = {"selected_generation": current_generation, "value": current_value, "audit": "preserve-me"}
    files = {"source.json": source, "snapshot.json": snapshot, "result.json": result}
    for i in range(d.distractors):
        files[f"snapshot_old_{i}.json"] = {
            "generation": max(0, current_generation - 2 - i),
            "value": rng.randint(100, 999), "authoritative": False,
        }
    prompt = (
        "Reconcile result.json only. Use the authoritative record with the highest generation from the visible JSON records. "
        "Copy its generation and value into selected_generation and value while preserving result.audit exactly. Do not create files."
    )
    return prompt, files, {"result.json": json.dumps(expected, indent=2, sort_keys=True) + "\n"}, ["authoritative_source", "preserve_audit"]


def _constraint_interaction(rng: random.Random, d: DifficultyVector):
    names = ["amber", "birch", "cobalt", "delta"]
    mode = rng.choice(["safe", "steady", "strict"])
    target = {"mode": mode, "enabled": ["amber", "cobalt"]}
    settings = {"mode": mode, "enabled": ["amber", "delta"]}
    requirements = {
        "exact_enabled": 2,
        "requires": {"amber": "cobalt"},
        "conflicts": [["cobalt", "delta"]],
        "preserve": ["mode"],
    }
    for i in range(d.distractors):
        requirements.setdefault("notes", []).append(f"decoy-note-{rng.randint(10,99)}")
    prompt = (
        "Repair settings.json only so every machine-readable rule in requirements.json is satisfied. "
        "Preserve fields named by requirements.preserve and do not add settings fields or files."
    )
    files = {"settings.json": settings, "requirements.json": requirements}
    return prompt, files, {"settings.json": json.dumps(target, indent=2, sort_keys=True) + "\n"}, ["all_requirements", "no_extra_fields"]


def _evidence_selection(rng: random.Random, d: DifficultyVector):
    nonce = f"n{rng.randint(1000,9999)}"
    winner_value = rng.randint(200, 900)
    records = [
        {"signed": True, "epoch": 5, "nonce": nonce, "value": winner_value},
        {"signed": False, "epoch": 9, "nonce": nonce, "value": winner_value + 7},
        {"signed": True, "epoch": 8, "nonce": "wrong", "value": winner_value + 11},
    ]
    for _ in range(d.distractors):
        records.append({"signed": bool(rng.randint(0, 1)), "epoch": rng.randint(1, 7), "nonce": f"x{rng.randint(1,99)}", "value": rng.randint(1,999)})
    rng.shuffle(records)
    files = {"policy.json": {"required_nonce": nonce, "require_signed": True}, "decision.json": {"value": None}}
    for i, record in enumerate(records):
        files[f"evidence/record_{i}.json"] = record
    expected = {"value": winner_value}
    prompt = (
        "Update decision.json only. From evidence/*.json choose the signed record whose nonce matches policy.required_nonce; "
        "if several match, choose the greatest epoch. Set decision.value to that record's value. Do not create files."
    )
    return prompt, files, {"decision.json": json.dumps(expected, indent=2, sort_keys=True) + "\n"}, ["signed_evidence", "matching_nonce", "highest_epoch"]


def _reconciliation(rng: random.Random, d: DifficultyVector):
    states = ["uncertain", "committed", "none"]
    state = rng.choice(states)
    codes = {s: f"op_{rng.randint(100,999)}" for s in states}
    ledger = {"action_code": "unset", "preserve": rng.randint(1, 9)}
    expected = {"action_code": codes[state], "preserve": ledger["preserve"]}
    files = {
        "remote_status.json": {"external_effect": state, "revision": 10 + d.temporal_depth},
        "policy.json": {"action_by_external_effect": codes},
        "ledger.json": ledger,
    }
    prompt = (
        "Update ledger.json only. Read remote_status.external_effect, look up the exact corresponding code in "
        "policy.action_by_external_effect, and store it in ledger.action_code. Preserve every other ledger field."
    )
    return prompt, files, {"ledger.json": json.dumps(expected, indent=2, sort_keys=True) + "\n"}, ["policy_lookup", "preserve_ledger"]


def _interface_novelty(rng: random.Random, d: DifficultyVector):
    fields = [f"f{rng.randint(100,999)}" for _ in range(3)]
    while len(set(fields)) < 3:
        fields = [f"f{rng.randint(100,999)}" for _ in range(3)]
    left, right, out = fields
    a, b = rng.randint(2, 20), rng.randint(2, 20)
    op = rng.choice(["sum", "difference", "product"])
    if op == "sum":
        value = a + b
    elif op == "difference":
        value = a - b
    else:
        value = a * b
    schema = {"left_field": left, "right_field": right, "output_field": out, "operation": op}
    payload = {left: a, right: b, "preserve": f"p{rng.randint(10,99)}"}
    output = {out: None, "preserve": payload["preserve"]}
    expected = {out: value, "preserve": payload["preserve"]}
    files = {"schema.json": schema, "payload.json": payload, "output.json": output}
    for i in range(d.ontology_novelty + d.distractors):
        files[f"docs/unused_{i}.json"] = {f"q{rng.randint(100,999)}": rng.randint(1, 99)}
    prompt = (
        "Repair output.json only by interpreting schema.json: read the payload fields named by left_field and right_field, "
        "apply schema.operation, and write the result to the field named by output_field. Preserve output.preserve exactly."
    )
    return prompt, files, {"output.json": json.dumps(expected, indent=2, sort_keys=True) + "\n"}, ["schema_driven_interface", "preserve_output"]


_BUILDERS = {
    "dependency_repair": _dependency_repair,
    "stale_state": _stale_state,
    "constraint_interaction": _constraint_interaction,
    "evidence_selection": _evidence_selection,
    "reconciliation": _reconciliation,
    "interface_novelty": _interface_novelty,
}


def generate_task(
    grammar: str,
    difficulty: DifficultyVector,
    seed: int,
    root: Path,
    forbidden_prompt_hashes: set[str] | None = None,
) -> TaskSpec:
    if grammar not in _BUILDERS:
        raise ValueError(f"unknown grammar: {grammar}")
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    (root / "workspace").mkdir(parents=True)
    (root / "verify").mkdir(parents=True)
    rng = random.Random(f"{grammar}:{seed}:{difficulty.key()}")
    answer_token = _answer_token(rng)
    prompt, visible_files, expected_files, constraints = _BUILDERS[grammar](rng, difficulty)
    fingerprint = prompt_fingerprint(prompt)
    if forbidden_prompt_hashes and fingerprint in forbidden_prompt_hashes:
        raise ValueError("contamination: prompt fingerprint already exists")

    for rel, value in visible_files.items():
        path = root / "workspace" / rel
        if isinstance(value, (dict, list)):
            _write_json(path, value)
        else:
            _write_text(path, str(value))
    task_id = f"brain2-{grammar}-{seed:08d}"
    task_json = {
        "id": task_id,
        "grammar": grammar,
        "seed": seed,
        "difficulty": asdict(difficulty),
        "prompt": prompt,
        "constraints": constraints,
        "prohibited_actions": ["create_unrequested_files", "modify_verifier"],
        "verifier": "verify/verify.py",
        "prompt_sha256": fingerprint,
    }
    _write_json(root / "task.json", task_json)
    _write_json(root / "verify" / "gold.json", {
        "answer_token": answer_token,
        "expected_files": expected_files,
        "forbidden_files": [],
    })
    _write_text(root / "verify" / "verify.py", _generic_verifier())
    return TaskSpec(task_id=task_id, grammar=grammar, seed=seed, difficulty=difficulty, root=str(root))
