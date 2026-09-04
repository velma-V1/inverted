from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, TextIO
import uuid

from inverted.progress import InPlaceProgress

from .d3_closure_cases import generate_closure_cases
from .d3_closure_scoring import score_semantic_action
from .d4_qwen_policy import classify_qwen_completion, select_qwen_policy
from .models import ModelAdapter


@dataclass(frozen=True)
class D4Experiment:
    experiment_id: str
    policy_id: str
    case: Any


@dataclass(frozen=True)
class D4Plan:
    experiments: tuple[D4Experiment, ...]
    case_ids: tuple[str, ...]
    max_calls: int = 48

    @property
    def planned_physical_calls(self) -> int:
        return len(self.experiments)


@dataclass(frozen=True)
class D4CampaignResult:
    physical_model_calls: int
    final_state: str
    policy_state: str


def _balanced_cases(cases: tuple[Any, ...], count: int) -> tuple[Any, ...]:
    buckets: dict[str, list[Any]] = {}
    order: list[str] = []
    for case in cases:
        if case.family not in buckets:
            buckets[case.family] = []
            order.append(case.family)
        buckets[case.family].append(case)
    chosen: list[Any] = []
    depth = 0
    while len(chosen) < count:
        added = False
        for family in order:
            rows = buckets[family]
            if depth < len(rows):
                chosen.append(rows[depth])
                added = True
                if len(chosen) >= count:
                    break
        if not added:
            break
        depth += 1
    if len(chosen) < count:
        raise ValueError("D4 case generator did not produce enough balanced cases")
    return tuple(chosen)


def build_d4_plan(config: Mapping[str, Any]) -> D4Plan:
    all_cases = generate_closure_cases(
        "closure-development",
        seed=int(config["case_seed"]),
        per_family=int(config["cases_per_family"]),
    )
    cases = _balanced_cases(all_cases, 24)
    experiments: list[D4Experiment] = []
    # Keep each matched pair adjacent so interruption cannot create large policy imbalance.
    for case in cases:
        for policy_id in ("DEFAULT", "THINK_OFF"):
            experiments.append(
                D4Experiment(
                    experiment_id=f"D4:{case.case_id}:{policy_id}",
                    policy_id=policy_id,
                    case=case,
                )
            )
    plan = D4Plan(tuple(experiments), tuple(case.case_id for case in cases), int(config["max_calls"]))
    if plan.max_calls != 48 or plan.planned_physical_calls != 48:
        raise ValueError("D4 must remain 24 matched cases x 2 policies = 48-call ceiling")
    return plan


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ensure_outputs(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name in (
        "d4_call_ledger.jsonl",
        "d4_raw_model_requests.jsonl",
        "d4_raw_model_responses.jsonl",
        "d4_normalized_model_calls.jsonl",
        "d4_runtime_telemetry.jsonl",
    ):
        path = root / name
        if not path.exists():
            path.write_text("", encoding="utf-8")


def _finalize(root: Path, *, config: Mapping[str, Any], plan: D4Plan, calls: int, state: str, policy: Mapping[str, Any], model_free: bool) -> None:
    _write_json(root / "d4_frozen_policy.json", dict(policy))
    master = {
        "protocol": "D4-QWEN-POLICY-v1",
        "mode": "MODEL_FREE" if model_free else "REAL_LOCAL",
        "physical_model_calls": int(calls),
        "planned_physical_calls": plan.planned_physical_calls,
        "max_calls": plan.max_calls,
        "final_state": state,
        "policy_state": policy.get("state"),
        "blind_retries_allowed": False,
    }
    _write_json(root / "00-HARVEST-D-D4-QWEN-POLICY-MASTER-INDEX.json", master)
    _write_json(
        root / "d4_plan.json",
        {
            "protocol": "D4-QWEN-POLICY-v1",
            "case_ids": list(plan.case_ids),
            "policies": list(config["policies"].keys()),
            "planned_physical_calls": plan.planned_physical_calls,
            "max_calls": plan.max_calls,
        },
    )
    checksum = root / "SHA256SUMS.csv"
    files = sorted(path for path in root.iterdir() if path.is_file() and path.name != checksum.name)
    with checksum.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sha256", "file"])
        for path in files:
            writer.writerow([_sha256(path), path.name])


class D4QwenCampaign:
    def __init__(
        self,
        root: str | Path,
        *,
        config: Mapping[str, Any],
        adapters: Mapping[str, ModelAdapter] | None = None,
        progress_stream: TextIO | None = None,
    ) -> None:
        self.root = Path(root)
        self.config = dict(config)
        self.adapters = dict(adapters or {})
        self.progress_stream = progress_stream
        self.plan = build_d4_plan(self.config)

    def _ensure_provenance(self) -> None:
        _ensure_outputs(self.root)
        path = self.root / "d4_provenance.json"
        current = {
            "protocol": "D4-QWEN-POLICY-v1",
            "model": self.config["model"],
            "case_seed": self.config["case_seed"],
            "generation_options": self.config["generation_options"],
            "policies": self.config["policies"],
            "max_calls": 48,
            "blind_retries_allowed": False,
        }
        if path.exists():
            if json.loads(path.read_text(encoding="utf-8")) != current:
                raise ValueError("D4 provenance mismatch; refuse unsafe resume")
        else:
            _write_json(path, current)

    def run_model_free(self) -> D4CampaignResult:
        self._ensure_provenance()
        progress = InPlaceProgress(stream=self.progress_stream, min_interval_s=0.0)
        progress.update(
            completed=0,
            total=self.plan.planned_physical_calls,
            current="D4 Qwen policy model-free",
            calls_used=0,
            calls_available=48,
            force=True,
        )
        progress.finish()
        policy = {
            "state": "NOT_RUN",
            "policy_id": None,
            "model_id": self.config["model"],
            "chat_options": {},
            "matched_cases": 0,
            "semantic_decision": "UNRESOLVED",
        }
        _finalize(self.root, config=self.config, plan=self.plan, calls=0, state="MODEL_FREE_COMPLETE", policy=policy, model_free=True)
        return D4CampaignResult(0, "MODEL_FREE_COMPLETE", "NOT_RUN")

    def run(self, *, max_calls: int | None = None) -> D4CampaignResult:
        self._ensure_provenance()
        if set(self.adapters) != {"DEFAULT", "THINK_OFF"}:
            raise ValueError("D4 real run requires DEFAULT and THINK_OFF adapters")
        limit = 48 if max_calls is None else int(max_calls)
        if not 0 <= limit <= 48:
            raise ValueError("D4 max_calls must be in [0,48]")

        ledger = _read_jsonl(self.root / "d4_call_ledger.jsonl")
        completed = {str(row["experiment_id"]) for row in ledger if row.get("committed")}
        calls_used = len(completed)
        if calls_used > limit:
            raise ValueError("existing D4 calls exceed requested ceiling")

        progress = InPlaceProgress(stream=self.progress_stream, min_interval_s=0.0, initial_completed=calls_used)
        progress.update(
            completed=calls_used,
            total=max(1, limit),
            current="D4 Qwen policy",
            calls_used=calls_used,
            calls_available=48,
            force=True,
        )

        for experiment in self.plan.experiments:
            if calls_used >= limit:
                break
            if experiment.experiment_id in completed:
                continue
            adapter = self.adapters[experiment.policy_id]
            call_id = f"d4-call-{uuid.uuid4().hex}"
            prompt = experiment.case.prompt
            system = "INVERTED D4 controlled Qwen policy measurement. Return exactly the requested answer JSON."
            _append_jsonl(
                self.root / "d4_raw_model_requests.jsonl",
                {
                    "physical_model_call_id": call_id,
                    "experiment_id": experiment.experiment_id,
                    "case_id": experiment.case.case_id,
                    "policy_id": experiment.policy_id,
                    "model_id": str(getattr(adapter, "model_id", "unknown")),
                    "system": system,
                    "prompt": prompt,
                    "generation_options": dict(getattr(adapter, "generation_options", {}) or {}),
                    "chat_options": dict(getattr(adapter, "chat_options", {}) or {}),
                },
            )
            try:
                response = adapter.complete(prompt, system=system)
                payload = dict(response.raw)
                completion = classify_qwen_completion(
                    done_reason=payload.get("done_reason"),
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    num_ctx=int((getattr(adapter, "generation_options", {}) or {}).get("num_ctx", 4096)),
                    final_text=response.text,
                )
                expected = experiment.case.oracle.expected if isinstance(experiment.case.oracle.expected, dict) else {}
                score = score_semantic_action(response.text, expected_answer=expected.get("answer"))
                normalized = {
                    "physical_model_call_id": call_id,
                    "experiment_id": experiment.experiment_id,
                    "case_id": experiment.case.case_id,
                    "family": experiment.case.family,
                    "policy_id": experiment.policy_id,
                    "model_id": response.model,
                    "completion_class": completion.value,
                    "semantic_action_correct": score.semantic_action_correct,
                    "parseable_json": score.parseable_json,
                    "format_valid": score.format_valid,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "latency_ms": response.latency_ms,
                }
                raw_response = {
                    "physical_model_call_id": call_id,
                    "experiment_id": experiment.experiment_id,
                    "text": response.text,
                    "payload": payload,
                }
                runtime = {
                    "physical_model_call_id": call_id,
                    "policy_id": experiment.policy_id,
                    "completion_class": completion.value,
                    "done_reason": payload.get("done_reason"),
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "latency_ms": response.latency_ms,
                }
            except Exception as exc:  # one physical attempt; never retry
                normalized = {
                    "physical_model_call_id": call_id,
                    "experiment_id": experiment.experiment_id,
                    "case_id": experiment.case.case_id,
                    "family": experiment.case.family,
                    "policy_id": experiment.policy_id,
                    "model_id": str(getattr(adapter, "model_id", "unknown")),
                    "completion_class": "INFRASTRUCTURE_OR_ADAPTER",
                    "semantic_action_correct": False,
                    "parseable_json": False,
                    "format_valid": False,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "latency_ms": 0.0,
                }
                raw_response = {
                    "physical_model_call_id": call_id,
                    "experiment_id": experiment.experiment_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                runtime = {
                    "physical_model_call_id": call_id,
                    "policy_id": experiment.policy_id,
                    "completion_class": "INFRASTRUCTURE_OR_ADAPTER",
                    "error_type": type(exc).__name__,
                }

            _append_jsonl(self.root / "d4_raw_model_responses.jsonl", raw_response)
            _append_jsonl(self.root / "d4_normalized_model_calls.jsonl", normalized)
            _append_jsonl(self.root / "d4_runtime_telemetry.jsonl", runtime)
            _append_jsonl(
                self.root / "d4_call_ledger.jsonl",
                {
                    "physical_model_call_id": call_id,
                    "experiment_id": experiment.experiment_id,
                    "attempt": 1,
                    "committed": True,
                },
            )
            calls_used += 1
            completed.add(experiment.experiment_id)
            progress.update(
                completed=calls_used,
                total=max(1, limit),
                current=f"D4 {experiment.policy_id}",
                calls_used=calls_used,
                calls_available=48,
                force=True,
            )

            # Only evaluate after a complete matched pair.
            if calls_used % 2 == 0 and calls_used >= 24:
                rows = _read_jsonl(self.root / "d4_normalized_model_calls.jsonl")
                policy = select_qwen_policy(rows, model_id=str(self.config["model"]))
                if policy["state"] == "FROZEN":
                    break

        progress.finish()
        rows = _read_jsonl(self.root / "d4_normalized_model_calls.jsonl")
        policy = select_qwen_policy(rows, model_id=str(self.config["model"]))
        if calls_used < 48 and policy["state"] != "FROZEN":
            policy = {**policy, "state": "INCOMPLETE"}
            final_state = "EVIDENCE_CEILING_REACHED"
        elif policy["state"] == "FROZEN":
            final_state = "COMPLETE"
        else:
            final_state = "UNRESOLVED"
        _finalize(self.root, config=self.config, plan=self.plan, calls=calls_used, state=final_state, policy=policy, model_free=False)
        return D4CampaignResult(calls_used, final_state, str(policy["state"]))
