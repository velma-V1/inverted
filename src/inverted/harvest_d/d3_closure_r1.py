from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .d3_closure_cases import generate_closure_cases, one_per_family


R1_MAX_CALLS = 24


@dataclass(frozen=True)
class R1Experiment:
    experiment_id: str
    stage: str
    model_key: str
    case_id: str
    family: str
    repeat_index: int
    sentinel: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id,
            "stage": self.stage,
            "model_key": self.model_key,
            "case_id": self.case_id,
            "family": self.family,
            "repeat_index": self.repeat_index,
            "sentinel": self.sentinel,
        }


@dataclass(frozen=True)
class R1Plan:
    experiments: tuple[R1Experiment, ...]
    max_calls: int = R1_MAX_CALLS

    def to_dict(self) -> dict[str, object]:
        return {
            "protocol": "D3-CLOSURE-v2",
            "stage": "R1_CALIBRATION",
            "max_physical_calls": self.max_calls,
            "planned_physical_calls": len(self.experiments),
            "design": "2 models x 3 structurally distinct cases x 4 exact repeats",
            "experiments": [row.to_dict() for row in self.experiments],
        }


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_r1_plan(config: Mapping[str, Any]) -> R1Plan:
    models = tuple(sorted(str(key) for key in config["models"]))
    if len(models) != 2 or set(models) != {"QWEN", "SMALL_A"}:
        raise ValueError("R1 calibration requires exactly SMALL_A and QWEN")
    seed = int(config["seeds"]["development"])
    per_family = max(1, int(config["cases_per_family"]["development"]))
    cases = one_per_family(generate_closure_cases("closure-r1-calibration", seed=seed, per_family=per_family))
    if len(cases) < 3:
        raise ValueError("R1 calibration requires at least three structurally distinct families")
    selected = tuple(cases[:3])
    sentinel_case_id = selected[0].case_id

    rows: list[R1Experiment] = []
    # Round-major ordering deliberately intersperses repeats instead of running
    # four identical calls back-to-back. This makes the sentinel useful for
    # detecting runtime drift while preserving exact matched cells.
    for repeat_index in range(1, 5):
        rotated = selected[(repeat_index - 1) % len(selected):] + selected[: (repeat_index - 1) % len(selected)]
        for case in rotated:
            for model_key in models:
                rows.append(
                    R1Experiment(
                        experiment_id=f"R1:{model_key}:{case.case_id}:R{repeat_index}",
                        stage="R1_CALIBRATION",
                        model_key=model_key,
                        case_id=case.case_id,
                        family=str(case.family),
                        repeat_index=repeat_index,
                        sentinel=case.case_id == sentinel_case_id,
                    )
                )
    if len(rows) != R1_MAX_CALLS:
        raise ValueError(f"R1 plan must contain exactly {R1_MAX_CALLS} calls")
    return R1Plan(tuple(rows))


def validate_r1_stage_authorization(raw: Mapping[str, Any]) -> None:
    if int(raw.get("schema_version", 0)) != 1:
        raise ValueError("R1 authorization schema mismatch")
    if str(raw.get("protocol")) != "D3-CLOSURE-v2":
        raise ValueError("R1 authorization protocol mismatch")
    if str(raw.get("stage")) != "R1_CALIBRATION":
        raise ValueError("R1 authorization stage mismatch")
    if raw.get("stage_physical_execution_authorized") is not True:
        raise ValueError("R1 physical calibration is not authorized")
    if int(raw.get("max_physical_calls", -1)) != R1_MAX_CALLS:
        raise ValueError("R1 authorization must be capped at exactly 24 calls")
    if raw.get("legacy_closure_physical_execution_authorized") is not False:
        raise ValueError("legacy Closure physical execution must remain blocked")


def build_r1_model_free_package(output_root: str | Path, config: Mapping[str, Any]) -> dict[str, object]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    plan = build_r1_plan(config)
    config_hash = hashlib.sha256(_stable_json(dict(config)).encode("utf-8")).hexdigest()

    _write_json(root / "closure_r1_plan.json", plan.to_dict())
    _write_json(
        root / "closure_r1_readiness.json",
        {
            "protocol": "D3-CLOSURE-v2",
            "stage": "R1_CALIBRATION",
            "state": "R1_MODEL_FREE_COMPLETE",
            "config_hash": config_hash,
            "physical_model_calls": 0,
            "max_physical_calls": R1_MAX_CALLS,
            "legacy_closure_path_allowed": False,
            "runtime_identity_verified": False,
            "d4_policy_verified": False,
            "fresh_r0_verified": False,
            "ready_for_physical_r1": False,
            "ready_for_test5": False,
        },
    )
    _write_json(
        root / "closure_reproducibility_calibration.json",
        {
            "protocol": "D3-CLOSURE-v2",
            "stage": "R1_CALIBRATION",
            "state": "NOT_RUN",
            "physical_model_calls": 0,
            "empirical_noise_floor": None,
            "byte_stability": None,
            "semantic_stability": None,
            "verified_outcome_stability": None,
        },
    )
    _write_json(
        root / "closure_cost_calibration.json",
        {
            "protocol": "D3-CLOSURE-v2",
            "stage": "R1_CALIBRATION",
            "state": "NOT_RUN",
            "physical_model_calls": 0,
            "cost_classes": {},
            "latency_seconds": {},
            "token_statistics": {},
        },
    )
    master = {
        "protocol": "D3-CLOSURE-v2",
        "stage": "R1_CALIBRATION",
        "mode": "MODEL_FREE",
        "final_state": "R1_MODEL_FREE_COMPLETE",
        "physical_model_calls": 0,
        "planned_physical_calls": len(plan.experiments),
        "max_physical_calls": R1_MAX_CALLS,
        "ready_for_physical_r1": False,
        "ready_for_test5": False,
        "blind_retries_allowed": False,
    }
    _write_json(root / "00-HARVEST-D-D3-CLOSURE-R1-MASTER-INDEX.json", master)

    checksum_path = root / "SHA256SUMS.csv"
    files = sorted(path for path in root.iterdir() if path.is_file() and path.name != checksum_path.name)
    with checksum_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sha256", "file"])
        for path in files:
            writer.writerow([_sha256(path), path.name])
    return dict(master)
