from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import json
from pathlib import Path
import random
from statistics import median
from typing import Any, Mapping

from .d3_closure_cases import generate_closure_cases, one_per_family
from .d3_closure_cost import CostObservation, CostProfile, classify_cost
from .d3_closure_scoring import score_semantic_action
from .models import ModelAdapter


R1_MAX_CALLS = 24
_R1_SYSTEM = (
    "INVERTED R1 reproducibility/cost calibration. Use only the supplied task. "
    "Return exactly one JSON object containing key answer."
)


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
            "execution_order": "seeded block-randomized case order with stable within-case model order",
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


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(value), sort_keys=True) + "\n")
        handle.flush()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _assert_unambiguous_resume(root: Path) -> None:
    started: set[str] = set()
    for row in _read_jsonl(root / "closure_r1_campaign_journal.jsonl"):
        experiment_id = str(row.get("experiment_id") or "")
        if not experiment_id:
            continue
        if str(row.get("state")) == "STARTED":
            started.add(experiment_id)
        elif str(row.get("state")) == "COMMITTED":
            started.discard(experiment_id)
    committed = {
        str(row.get("experiment_id"))
        for row in _read_jsonl(root / "closure_r1_call_ledger.jsonl")
        if row.get("committed") and row.get("experiment_id")
    }
    ambiguous = sorted(started - committed)
    if ambiguous:
        raise ValueError(
            "ambiguous in-flight R1 physical call on resume; automatic replay forbidden: "
            + ", ".join(ambiguous)
        )


def _selected_cases(config: Mapping[str, Any]) -> tuple[Any, ...]:
    seed = int(config["seeds"]["development"])
    per_family = max(1, int(config["cases_per_family"]["development"]))
    cases = one_per_family(generate_closure_cases("closure-r1-calibration", seed=seed, per_family=per_family))
    if len(cases) < 3:
        raise ValueError("R1 calibration requires at least three structurally distinct families")
    return tuple(cases[:3])


def _expected_answer(case: Any) -> Any:
    expected = case.oracle.expected if isinstance(case.oracle.expected, dict) else {}
    return expected.get("answer")


def build_r1_plan(config: Mapping[str, Any]) -> R1Plan:
    if set(str(key) for key in config["models"]) != {"SMALL_A", "QWEN"} or len(config["models"]) != 2:
        raise ValueError("R1 calibration requires exactly SMALL_A and QWEN")
    models = ("SMALL_A", "QWEN")
    selected = _selected_cases(config)
    sentinel_case_id = selected[0].case_id
    seed = int(config["generation_options"].get("seed", 20260902))
    rows: list[R1Experiment] = []
    for repeat_index in range(1, 5):
        block_cases = list(selected)
        random.Random(seed + repeat_index).shuffle(block_cases)
        for case in block_cases:
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


def _write_checksums(root: Path) -> None:
    checksum_path = root / "SHA256SUMS.csv"
    files = sorted(path for path in root.iterdir() if path.is_file() and path.name != checksum_path.name)
    with checksum_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sha256", "file"])
        for path in files:
            writer.writerow([_sha256(path), path.name])


def build_r1_model_free_package(output_root: str | Path, config: Mapping[str, Any]) -> dict[str, object]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    plan = build_r1_plan(config)
    config_hash = hashlib.sha256(_stable_json(dict(config)).encode("utf-8")).hexdigest()
    _write_json(root / "closure_r1_plan.json", plan.to_dict())
    _write_json(root / "closure_r1_readiness.json", {
        "protocol": "D3-CLOSURE-v2", "stage": "R1_CALIBRATION", "state": "R1_MODEL_FREE_COMPLETE",
        "config_hash": config_hash, "physical_model_calls": 0, "max_physical_calls": R1_MAX_CALLS,
        "legacy_closure_path_allowed": False, "runtime_identity_verified": False,
        "d4_policy_verified": False, "fresh_r0_verified": False, "historical_d3_verified": False,
        "ready_for_physical_r1": False, "ready_for_test5": False,
    })
    _write_json(root / "closure_reproducibility_calibration.json", {
        "protocol": "D3-CLOSURE-v2", "stage": "R1_CALIBRATION", "state": "NOT_RUN",
        "physical_model_calls": 0, "empirical_noise_floor": None, "byte_stability": None,
        "semantic_stability": None, "verified_outcome_stability": None,
    })
    _write_json(root / "closure_cost_calibration.json", {
        "protocol": "D3-CLOSURE-v2", "stage": "R1_CALIBRATION", "state": "NOT_RUN",
        "physical_model_calls": 0, "cost_classes": {}, "latency_seconds": {}, "token_statistics": {},
    })
    master = {
        "protocol": "D3-CLOSURE-v2", "stage": "R1_CALIBRATION", "mode": "MODEL_FREE",
        "final_state": "R1_MODEL_FREE_COMPLETE", "physical_model_calls": 0,
        "planned_physical_calls": len(plan.experiments), "max_physical_calls": R1_MAX_CALLS,
        "ready_for_physical_r1": False, "ready_for_test5": False, "blind_retries_allowed": False,
    }
    _write_json(root / "00-HARVEST-D-D3-CLOSURE-R1-MASTER-INDEX.json", master)
    _write_checksums(root)
    return dict(master)


class R1CalibrationCampaign:
    def __init__(
        self,
        output_root: str | Path,
        *,
        config: Mapping[str, Any],
        adapters: Mapping[str, ModelAdapter],
        runtime_identity: Mapping[str, Mapping[str, Any]],
    ) -> None:
        self.root = Path(output_root)
        self.config = dict(config)
        self.adapters = dict(adapters)
        self.runtime_identity = {str(k): dict(v) for k, v in runtime_identity.items()}
        self.plan = build_r1_plan(self.config)
        if set(self.adapters) != {"SMALL_A", "QWEN"}:
            raise ValueError("R1 adapters must be exactly SMALL_A and QWEN")
        for key in ("SMALL_A", "QWEN"):
            identity = self.runtime_identity.get(key, {})
            if str(identity.get("model_id")) != str(self.config["models"][key]):
                raise ValueError(f"R1 runtime model identity mismatch: {key}")
            if not str(identity.get("model_digest") or ""):
                raise ValueError(f"R1 runtime model digest missing: {key}")

    def _finalize(self, calls_used: int, state: str) -> dict[str, object]:
        rows = _read_jsonl(self.root / "closure_r1_normalized_calls.jsonl")
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in rows:
            groups.setdefault((str(row["model_key"]), str(row["case_id"])), []).append(row)
        complete_cells = [cell for cell in groups.values() if len(cell) == 4]
        output_unstable = sum(1 for cell in complete_cells if len({row["output_hash"] for row in cell}) > 1)
        semantic_unstable = sum(1 for cell in complete_cells if len({row["semantic_answer_hash"] for row in cell}) > 1)
        outcome_unstable = sum(1 for cell in complete_cells if len({bool(row["verified_outcome_correct"]) for row in cell}) > 1)
        denom = len(complete_cells)
        infra_failures = sum(row.get("completion_class") == "INFRASTRUCTURE_OR_ADAPTER" for row in rows)
        repro_state = "INVALID_INFRASTRUCTURE" if infra_failures else ("MEASURED" if calls_used == R1_MAX_CALLS else "PARTIAL")
        _write_json(self.root / "closure_reproducibility_calibration.json", {
            "protocol": "D3-CLOSURE-v2", "stage": "R1_CALIBRATION", "state": repro_state,
            "physical_model_calls": calls_used, "exact_repeat_cells": denom,
            "infrastructure_failures": infra_failures,
            "empirical_noise_floor": {
                "output_hash_instability_rate": output_unstable / denom if denom else None,
                "semantic_instability_rate": semantic_unstable / denom if denom else None,
                "verified_outcome_instability_rate": outcome_unstable / denom if denom else None,
            },
            "byte_stability": {"stable_cells": denom - output_unstable, "unstable_cells": output_unstable},
            "semantic_stability": {"stable_cells": denom - semantic_unstable, "unstable_cells": semantic_unstable},
            "verified_outcome_stability": {"stable_cells": denom - outcome_unstable, "unstable_cells": outcome_unstable},
        })
        by_model: dict[str, dict[str, Any]] = {}
        profile = CostProfile(profile_id="R1_RUNTIME_CALIBRATION", residency_cliff_gib=9.5)
        for key in ("SMALL_A", "QWEN"):
            model_rows = [row for row in rows if row["model_key"] == key]
            successful_rows = [row for row in model_rows if row.get("completion_class") != "INFRASTRUCTURE_OR_ADAPTER"]
            latencies = [float(row["latency_ms"]) / 1000.0 for row in successful_rows]
            identity = self.runtime_identity[key]
            median_latency = median(latencies) if latencies else None
            cost_class = classify_cost(CostObservation(
                installed_size_gib=(float(identity["installed_size_gib"]) if identity.get("installed_size_gib") is not None else None),
                median_latency_s=median_latency,
                thinking=bool(identity.get("thinking", False)),
                offload_observed=bool(identity.get("offload_observed", False)),
                context_exhaustion_rate=(
                    sum(row.get("done_reason") == "length" for row in successful_rows) / len(successful_rows)
                    if successful_rows else 0.0
                ),
            ), profile).value
            by_model[key] = {
                "model_id": identity["model_id"], "model_digest": identity["model_digest"],
                "installed_size_gib": identity.get("installed_size_gib"), "offload_observed": identity.get("offload_observed"),
                "n": len(model_rows), "successful_n": len(successful_rows), "median_latency_s": median_latency,
                "cost_class": cost_class,
                "input_tokens_total": sum(int(row["input_tokens"]) for row in successful_rows),
                "output_tokens_total": sum(int(row["output_tokens"]) for row in successful_rows),
            }
        _write_json(self.root / "closure_cost_calibration.json", {
            "protocol": "D3-CLOSURE-v2", "stage": "R1_CALIBRATION",
            "state": "INVALID_INFRASTRUCTURE" if infra_failures else ("MEASURED" if calls_used == R1_MAX_CALLS else "PARTIAL"),
            "physical_model_calls": calls_used, "infrastructure_failures": infra_failures, "by_model": by_model,
        })
        master = {
            "protocol": "D3-CLOSURE-v2", "stage": "R1_CALIBRATION", "mode": "REAL_LOCAL",
            "final_state": state, "physical_model_calls": calls_used,
            "planned_physical_calls": R1_MAX_CALLS, "max_physical_calls": R1_MAX_CALLS,
            "infrastructure_failures": infra_failures, "ready_for_test5": False, "blind_retries_allowed": False,
        }
        _write_json(self.root / "00-HARVEST-D-D3-CLOSURE-R1-MASTER-INDEX.json", master)
        _write_checksums(self.root)
        return master

    def run(self, *, max_calls: int | None = None) -> dict[str, object]:
        limit = R1_MAX_CALLS if max_calls is None else int(max_calls)
        if not 0 <= limit <= R1_MAX_CALLS:
            raise ValueError("R1 max_calls must be between 0 and 24")
        self.root.mkdir(parents=True, exist_ok=True)
        _assert_unambiguous_resume(self.root)
        _write_json(self.root / "closure_r1_plan.json", self.plan.to_dict())
        _write_json(self.root / "closure_r1_runtime_identity.json", self.runtime_identity)
        existing = _read_jsonl(self.root / "closure_r1_call_ledger.jsonl")
        committed = {str(row["experiment_id"]) for row in existing if row.get("committed")}
        calls_used = len(committed)
        if calls_used > limit:
            raise ValueError("existing R1 calls exceed requested ceiling")
        case_map = {case.case_id: case for case in _selected_cases(self.config)}
        for experiment in self.plan.experiments:
            if calls_used >= limit:
                break
            if experiment.experiment_id in committed:
                continue
            adapter = self.adapters[experiment.model_key]
            case = case_map[experiment.case_id]
            _append_jsonl(self.root / "closure_r1_campaign_journal.jsonl", {
                "experiment_id": experiment.experiment_id, "state": "STARTED", "attempt": 1,
            })
            try:
                response = adapter.complete(case.prompt, system=_R1_SYSTEM)
                semantic = score_semantic_action(response.text, expected_answer=_expected_answer(case))
                semantic_hash = _text_hash(_stable_json(semantic.answer))
                row = {
                    "experiment_id": experiment.experiment_id, "model_key": experiment.model_key,
                    "case_id": experiment.case_id, "family": experiment.family,
                    "repeat_index": experiment.repeat_index, "sentinel": experiment.sentinel,
                    "model_id": response.model, "model_digest": self.runtime_identity[experiment.model_key]["model_digest"],
                    "output_hash": _text_hash(response.text), "output_text": response.text,
                    "semantic_answer_hash": semantic_hash, "semantic_action_correct": semantic.semantic_action_correct,
                    "verified_outcome_correct": semantic.semantic_action_correct,
                    "parseable_json": semantic.parseable_json, "format_valid": semantic.format_valid,
                    "input_tokens": response.input_tokens, "output_tokens": response.output_tokens,
                    "latency_ms": response.latency_ms, "done_reason": str(response.raw.get("done_reason") or ""),
                    "completion_class": "SEMANTIC_RESULT", "error_type": None,
                }
            except Exception as exc:  # exactly one physical attempt; never retry
                row = {
                    "experiment_id": experiment.experiment_id, "model_key": experiment.model_key,
                    "case_id": experiment.case_id, "family": experiment.family,
                    "repeat_index": experiment.repeat_index, "sentinel": experiment.sentinel,
                    "model_id": str(getattr(adapter, "model_id", self.config["models"][experiment.model_key])),
                    "model_digest": self.runtime_identity[experiment.model_key]["model_digest"],
                    "output_hash": f"ERROR:{type(exc).__name__}", "output_text": "",
                    "semantic_answer_hash": f"ERROR:{type(exc).__name__}", "semantic_action_correct": False,
                    "verified_outcome_correct": False, "parseable_json": False, "format_valid": False,
                    "input_tokens": 0, "output_tokens": 0, "latency_ms": 0.0, "done_reason": "ERROR",
                    "completion_class": "INFRASTRUCTURE_OR_ADAPTER", "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            _append_jsonl(self.root / "closure_r1_normalized_calls.jsonl", row)
            _append_jsonl(self.root / "closure_r1_call_ledger.jsonl", {
                "experiment_id": experiment.experiment_id, "attempt": 1, "committed": True,
                "completion_class": row["completion_class"],
            })
            _append_jsonl(self.root / "closure_r1_campaign_journal.jsonl", {
                "experiment_id": experiment.experiment_id, "state": "COMMITTED", "attempt": 1,
            })
            calls_used += 1
            committed.add(experiment.experiment_id)
        rows = _read_jsonl(self.root / "closure_r1_normalized_calls.jsonl")
        infra_failures = sum(row.get("completion_class") == "INFRASTRUCTURE_OR_ADAPTER" for row in rows)
        if infra_failures:
            state = "R1_CALIBRATION_INVALID_INFRASTRUCTURE"
        elif calls_used == R1_MAX_CALLS:
            state = "R1_CALIBRATION_COMPLETE"
        else:
            state = "R1_CALIBRATION_PARTIAL"
        return self._finalize(calls_used, state)
