from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Iterable, Mapping
import uuid

from .hd_next1_authorization import validate_owner_authorization
from .hd_next1_budget import HDNext1BudgetState
from .hd_next1_cases import generate_hd_next1_cases, generate_protected_case_pool
from .hd_next1_decisions import compile_model_ownership
from .hd_next1_randomization import default_confirmation_resolution_policy, freeze_confirmation_resolution, freeze_protected_assignments
from .hd_next1_scheduler import Candidate, HDNext1Scheduler
from .hd_next1_space import build_zero_call_design, render_treatment_messages
from .models import ModelAdapter
from .types import Disposition, stable_hash


@dataclass(frozen=True)
class ExecutionUnit:
    unit_id: str
    stage: str
    model_key: str
    pool: str
    case_id: str
    treatment_id: str
    factor_vector: dict[str, str]
    treatment_role: str = ""
    expected_seconds: float = 1.0


@dataclass(frozen=True)
class HDNext1CampaignResult:
    physical_model_calls: int
    final_state: str


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(row), sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().lower().replace("-", "_").replace(" ", "_")
    return value


def _parse_answer(text: str) -> Any:
    raw = str(text).strip()
    if raw.startswith("```") and raw.endswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1])
        if raw.lstrip().lower().startswith("json"):
            raw = raw.lstrip()[4:].lstrip()
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return payload.get("answer") if isinstance(payload, dict) else None


def _expected_answer(case: Any) -> Any:
    expected = case.oracle.expected if isinstance(case.oracle.expected, dict) else {}
    return expected.get("answer")


def _compile_disposition(case: Any) -> Disposition:
    info = dict((case.metadata or {}).get("d3_information", {}))
    state = dict(info.get("I2", {}))
    authority = dict(info.get("I3", {}))
    evidence = dict(info.get("I4", {}))
    if state.get("global_state_valid") is False:
        return Disposition.SAFE_STOP
    requested = authority.get("requested_resource", state.get("requested_resource"))
    allowed = set(authority.get("allowed_resources", authority.get("scope", [])) or [])
    if requested is not None and allowed and requested not in allowed:
        return Disposition.ESCALATE
    if str(evidence.get("external_effect_status", "NOT_COMMITTED")) == "UNKNOWN":
        return Disposition.ESCALATE
    if evidence.get("missing"):
        return Disposition.ACQUIRE_EVIDENCE
    return Disposition.EXECUTE


class HDNext1Campaign:
    def __init__(
        self,
        root: str | Path,
        *,
        prereg_root: str | Path,
        config: dict[str, Any],
        adapters: Mapping[str, ModelAdapter] | None = None,
        owner_authorization: dict[str, object] | None = None,
    ) -> None:
        self.root = Path(root)
        self.prereg_root = Path(prereg_root)
        self.config = dict(config)
        self.adapters = dict(adapters or {})
        self.owner_authorization = owner_authorization
        self.design = build_zero_call_design(self.config)
        self.development_cases = generate_hd_next1_cases(
            "hd-next1-development", seed=int(self.config["seeds"]["development"]), per_family=4
        )
        self.case_by_id = {row.case_id: row for row in self.development_cases}
        for row in generate_protected_case_pool(self.config):
            self.case_by_id[row.case_id] = row
        self.treatment_by_id = {row["treatment_id"]: row for row in self.design.treatments}
        self.budget = HDNext1BudgetState.default(max_inference_seconds=10**9)
        self.calls_used = 0

    def run_model_free(self) -> HDNext1CampaignResult:
        return HDNext1CampaignResult(0, "MODEL_FREE_ONLY")

    def _calibration_units(self) -> tuple[ExecutionUnit, ...]:
        cases: list[Any] = []
        seen: set[str] = set()
        for case in self.development_cases:
            if case.family not in seen:
                cases.append(case)
                seen.add(case.family)
            if len(cases) == 4:
                break
        baseline = self.design.treatments[0]
        rows: list[ExecutionUnit] = []
        for case in cases:
            for model_key in ("SMALL_A", "QWEN"):
                for repetition in range(3):
                    rows.append(
                        ExecutionUnit(
                            unit_id=stable_hash({"stage": "T1", "case": case.case_id, "model": model_key, "rep": repetition}),
                            stage="T1_CALIBRATION",
                            model_key=model_key,
                            pool="calibration",
                            case_id=case.case_id,
                            treatment_id=baseline["treatment_id"],
                            factor_vector=dict(baseline["factor_vector"]),
                            expected_seconds=0.5 if model_key == "SMALL_A" else 75.0,
                        )
                    )
        return tuple(rows)

    def _broad_small_a_units(self) -> tuple[ExecutionUnit, ...]:
        rows = []
        for treatment in self.design.treatments[:216]:
            rows.append(
                ExecutionUnit(
                    unit_id=stable_hash({"stage": "T2", "treatment": treatment["treatment_id"]}),
                    stage="T2_SMALL_A_SCREEN",
                    model_key="SMALL_A",
                    pool="development",
                    case_id=treatment["case_id"],
                    treatment_id=treatment["treatment_id"],
                    factor_vector=dict(treatment["factor_vector"]),
                    expected_seconds=0.5,
                )
            )
        return tuple(rows)

    def _adaptive_small_a_units(self, tested: set[str]) -> tuple[ExecutionUnit, ...]:
        scheduler = HDNext1Scheduler(seed=int(self.config["randomization_seed"]), protected_random_fraction=float(self.config["scheduler"]["protected_random_stream_fraction"]))
        candidates: list[Candidate] = []
        for treatment in self.design.treatments:
            if treatment["treatment_id"] in tested:
                continue
            factors = treatment["factor_vector"]
            high_value = float(
                (factors["I4"] == "ON" and factors["A3"] == "TARGET")
                or (factors["I7"] == "ON" and factors["A2"] == "TARGET")
                or factors["amount"] == "OVERLOADED"
            )
            candidates.append(
                Candidate(
                    candidate_id=treatment["treatment_id"],
                    mechanism_id=treatment["treatment_id"],
                    model_key="SMALL_A",
                    decision_id="D-SUPPORT-BOUNDARY",
                    decision_change_reason="untested interaction can change minimum-support or negative-transfer boundary",
                    architecture_changing_uncertainty=1.0,
                    uncovered_high_value_interaction=high_value,
                    minimum_support_uncertainty=1.0,
                    negative_transfer_boundary=high_value,
                    expected_seconds=0.5,
                )
            )
        picks = scheduler.plan_block(candidates, block_size=96)
        rows = []
        for pick in picks:
            treatment = self.treatment_by_id[pick.candidate_id]
            rows.append(
                ExecutionUnit(
                    unit_id=stable_hash({"stage": "T3", "treatment": treatment["treatment_id"]}),
                    stage="T3_ADAPTIVE_SMALL_A",
                    model_key="SMALL_A",
                    pool="development",
                    case_id=treatment["case_id"],
                    treatment_id=treatment["treatment_id"],
                    factor_vector=dict(treatment["factor_vector"]),
                    expected_seconds=0.5,
                )
            )
        return tuple(rows)

    def _development_snapshot(self) -> dict[str, object]:
        rows = [row for row in _read_jsonl(self.root / "normalized_model_calls.jsonl") if row.get("model_key") == "SMALL_A" and str(row.get("stage", "")).startswith(("T2", "T3"))]
        scores: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            scores.setdefault(str(row["treatment_id"]), []).append(row)
        if not scores:
            winner = self.design.treatments[0]["treatment_id"]
            challenger = self.design.treatments[-1]["treatment_id"]
        else:
            ranked = sorted(
                scores,
                key=lambda treatment_id: (
                    sum(bool(row.get("verified_outcome_correct")) for row in scores[treatment_id]) / len(scores[treatment_id]),
                    -sum(float(row.get("latency_ms", 0.0)) for row in scores[treatment_id]) / len(scores[treatment_id]),
                    treatment_id,
                ),
                reverse=True,
            )
            winner = ranked[0]
            challenger = ranked[1] if len(ranked) > 1 else self.design.treatments[-1]["treatment_id"]
        return {
            "evidence_tier": "DEVELOPMENT",
            "winner_treatment_id": winner,
            "challenger_treatment_id": challenger,
            "source_hash": stable_hash(rows),
        }

    def _qwen_development_units(self, snapshot: Mapping[str, object]) -> tuple[ExecutionUnit, ...]:
        candidate_ids = [str(snapshot["winner_treatment_id"]), str(snapshot["challenger_treatment_id"])]
        high_risk = [row["treatment_id"] for row in self.design.treatments if row["factor_vector"]["amount"] == "OVERLOADED"]
        candidate_ids.extend(high_risk[:19])
        unique = []
        for item in candidate_ids:
            if item in self.treatment_by_id and item not in unique:
                unique.append(item)
            if len(unique) == 21:
                break
        rows = []
        for treatment_id in unique:
            treatment = self.treatment_by_id[treatment_id]
            rows.append(
                ExecutionUnit(
                    unit_id=stable_hash({"stage": "T4T5", "treatment": treatment_id}),
                    stage="T4T5_QWEN_DISCRIMINATION",
                    model_key="QWEN",
                    pool="development",
                    case_id=treatment["case_id"],
                    treatment_id=treatment_id,
                    factor_vector=dict(treatment["factor_vector"]),
                    expected_seconds=75.0,
                )
            )
        return tuple(rows[:21])

    def _protected_units(self, snapshot: Mapping[str, object], partition: str) -> tuple[ExecutionUnit, ...]:
        pool = generate_protected_case_pool(self.config)
        policy = default_confirmation_resolution_policy(self.design)
        assignments = freeze_protected_assignments(pool, self.design, policy, seed=int(self.config["randomization_seed"]))
        resolved = freeze_confirmation_resolution(assignments, self.design, snapshot)
        rows = []
        for assignment in resolved:
            if assignment.partition != partition:
                continue
            treatment = self.treatment_by_id[str(assignment.resolved_treatment_id)]
            rows.append(
                ExecutionUnit(
                    unit_id=assignment.assignment_id,
                    stage="T6_FRESH_CONFIRMATION" if partition == "hd-next1-fresh" else "T6_SEALED_CONFIRMATION",
                    model_key=assignment.model_key,
                    pool="confirmation",
                    case_id=assignment.case_id,
                    treatment_id=str(assignment.resolved_treatment_id),
                    factor_vector=dict(treatment["factor_vector"]),
                    treatment_role=assignment.treatment_role,
                    expected_seconds=0.5 if assignment.model_key == "SMALL_A" else 75.0,
                )
            )
        return tuple(sorted(rows, key=lambda row: row.unit_id))

    def _execute_unit(self, unit: ExecutionUnit) -> None:
        if unit.model_key not in self.adapters:
            raise ValueError(f"missing adapter for {unit.model_key}")
        case = self.case_by_id[unit.case_id]
        adapter = self.adapters[unit.model_key]
        self.budget.reserve(unit.model_key, unit.pool, expected_seconds=unit.expected_seconds)
        _append_jsonl(self.root / "cost_budget_state.jsonl", {"event": "RESERVED", "unit_id": unit.unit_id, **self.budget.to_dict()})
        system, prompt, treatment_meta = render_treatment_messages(case, unit.factor_vector)
        call_id = f"hdnext1-call-{uuid.uuid4().hex}"
        _append_jsonl(
            self.root / "raw_model_requests.jsonl",
            {
                "physical_model_call_id": call_id,
                "unit_id": unit.unit_id,
                "stage": unit.stage,
                "model_key": unit.model_key,
                "model_id": str(getattr(adapter, "model_id", "unknown")),
                "case_id": case.case_id,
                "treatment_id": unit.treatment_id,
                "treatment_role": unit.treatment_role,
                "system": system,
                "prompt": prompt,
                "generation_options": dict(getattr(adapter, "generation_options", {}) or {}),
                "system_message_hash": treatment_meta["system_message_hash"],
                "user_message_hash": treatment_meta["user_message_hash"],
            },
        )
        _append_jsonl(self.root / "campaign_journal.jsonl", {"physical_model_call_id": call_id, "unit_id": unit.unit_id, "state": "STARTED"})
        start = time.perf_counter()
        try:
            response = adapter.complete(prompt, system=system)
            actual_seconds = max(0.0, (time.perf_counter() - start))
            answer = _parse_answer(response.text)
            answer_correct = _normalize(answer) == _normalize(_expected_answer(case))
            compiled = _compile_disposition(case)
            disposition_correct = compiled is case.expected_disposition
            verified = bool(answer_correct and disposition_correct)
            raw_response = {"physical_model_call_id": call_id, "unit_id": unit.unit_id, "text": response.text, "payload": dict(response.raw)}
            normalized = {
                "physical_model_call_id": call_id,
                "unit_id": unit.unit_id,
                "stage": unit.stage,
                "model_key": unit.model_key,
                "model_id": response.model,
                "case_id": case.case_id,
                "family": case.family,
                "treatment_id": unit.treatment_id,
                "treatment_role": unit.treatment_role,
                "answer_correct": answer_correct,
                "compiled_disposition": compiled.value,
                "compiled_disposition_correct": disposition_correct,
                "verified_outcome_correct": verified,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "latency_ms": response.latency_ms,
                "completion_class": "SEMANTIC_RESULT",
            }
        except Exception as exc:
            actual_seconds = max(0.0, (time.perf_counter() - start))
            raw_response = {"physical_model_call_id": call_id, "unit_id": unit.unit_id, "error_type": type(exc).__name__, "error": str(exc)}
            normalized = {
                "physical_model_call_id": call_id,
                "unit_id": unit.unit_id,
                "stage": unit.stage,
                "model_key": unit.model_key,
                "model_id": str(getattr(adapter, "model_id", "unknown")),
                "case_id": case.case_id,
                "family": case.family,
                "treatment_id": unit.treatment_id,
                "treatment_role": unit.treatment_role,
                "answer_correct": False,
                "compiled_disposition": _compile_disposition(case).value,
                "compiled_disposition_correct": _compile_disposition(case) is case.expected_disposition,
                "verified_outcome_correct": False,
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": actual_seconds * 1000.0,
                "completion_class": "INFRASTRUCTURE_OR_ADAPTER",
            }
        self.budget.reconcile(unit.model_key, unit.pool, expected_seconds=unit.expected_seconds, actual_seconds=actual_seconds)
        _append_jsonl(self.root / "raw_model_responses.jsonl", raw_response)
        _append_jsonl(self.root / "normalized_model_calls.jsonl", normalized)
        _append_jsonl(self.root / "runtime_telemetry.jsonl", {"physical_model_call_id": call_id, "unit_id": unit.unit_id, "latency_ms": normalized["latency_ms"], "completion_class": normalized["completion_class"]})
        _append_jsonl(self.root / "physical_call_ledger.jsonl", {"physical_model_call_id": call_id, "unit_id": unit.unit_id, "attempt": 1, "automatic_retry": False, "committed": True})
        _append_jsonl(self.root / "campaign_journal.jsonl", {"physical_model_call_id": call_id, "unit_id": unit.unit_id, "state": "COMMITTED"})
        _append_jsonl(self.root / "cost_budget_state.jsonl", {"event": "RECONCILED", "unit_id": unit.unit_id, **self.budget.to_dict()})
        self.calls_used += 1

    def _run_units(self, units: Iterable[ExecutionUnit], limit: int) -> bool:
        for unit in units:
            if self.calls_used >= limit:
                return False
            self._execute_unit(unit)
        return True

    def _fresh_gate_passes(self) -> bool:
        rows = [row for row in _read_jsonl(self.root / "normalized_model_calls.jsonl") if row.get("stage") == "T6_FRESH_CONFIRMATION" and row.get("treatment_role") == "CONFIRM_PROMOTED_POLICY"]
        by_case: dict[str, dict[str, bool]] = {}
        for row in rows:
            by_case.setdefault(str(row["case_id"]), {})[str(row["model_key"])] = bool(row.get("verified_outcome_correct"))
        matched = [value for value in by_case.values() if "QWEN" in value and "SMALL_A" in value]
        qwen_only = sum(value["QWEN"] and not value["SMALL_A"] for value in matched)
        passes = not matched or (qwen_only / len(matched) <= 0.05)
        (self.root / "fresh_gate_report.json").write_text(
            json.dumps({"matched_cases": len(matched), "qwen_only_wins": qwen_only, "fresh_gate_passed": passes}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return passes

    def run_authorized(self, *, max_calls: int | None = None) -> HDNext1CampaignResult:
        if self.owner_authorization is None:
            raise ValueError("owner execution authorization is required")
        validate_owner_authorization(self.prereg_root, self.owner_authorization)
        if set(self.adapters) != {"SMALL_A", "QWEN"}:
            raise ValueError("HD-NEXT-1 requires SMALL_A and QWEN adapters")
        limit = 672 if max_calls is None else int(max_calls)
        if not 0 <= limit <= 672:
            raise ValueError("requested max_calls exceeds frozen HD-NEXT-1 ceiling")
        self.root.mkdir(parents=True, exist_ok=True)
        if not self._run_units(self._calibration_units(), limit):
            return HDNext1CampaignResult(self.calls_used, "EVIDENCE_CEILING_REACHED")
        broad = self._broad_small_a_units()
        if not self._run_units(broad, limit):
            return HDNext1CampaignResult(self.calls_used, "EVIDENCE_CEILING_REACHED")
        tested = {unit.treatment_id for unit in broad}
        adaptive = self._adaptive_small_a_units(tested)
        if not self._run_units(adaptive, limit):
            return HDNext1CampaignResult(self.calls_used, "EVIDENCE_CEILING_REACHED")
        snapshot = self._development_snapshot()
        (self.root / "development_freeze.json").write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if not self._run_units(self._qwen_development_units(snapshot), limit):
            return HDNext1CampaignResult(self.calls_used, "EVIDENCE_CEILING_REACHED")
        if not self._run_units(self._protected_units(snapshot, "hd-next1-fresh"), limit):
            return HDNext1CampaignResult(self.calls_used, "EVIDENCE_CEILING_REACHED")
        if not self._fresh_gate_passes():
            return HDNext1CampaignResult(self.calls_used, "FRESH_CONFIRMATION_REFUTED")
        if not self._run_units(self._protected_units(snapshot, "hd-next1-sealed"), limit):
            return HDNext1CampaignResult(self.calls_used, "EVIDENCE_CEILING_REACHED")
        rows = _read_jsonl(self.root / "normalized_model_calls.jsonl")
        promoted = [row for row in rows if row.get("stage") in {"T6_FRESH_CONFIRMATION", "T6_SEALED_CONFIRMATION"} and row.get("treatment_role") == "CONFIRM_PROMOTED_POLICY"]
        by_case: dict[str, dict[str, bool]] = {}
        for row in promoted:
            by_case.setdefault(str(row["case_id"]), {})[str(row["model_key"])] = bool(row.get("verified_outcome_correct"))
        matched = [value for value in by_case.values() if "QWEN" in value and "SMALL_A" in value]
        qwen_only = sum(value["QWEN"] and not value["SMALL_A"] for value in matched)
        model_decision = compile_model_ownership(qwen_only_wins=qwen_only, matched_n=max(1, len(matched)))
        (self.root / "final_architecture_decisions.json").write_text(
            json.dumps({"model_substitution": {"state": model_decision.state, "action": model_decision.action, "detail": model_decision.detail}, "matched_cases": len(matched), "qwen_only_wins": qwen_only}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        infrastructure_failures = sum(row.get("completion_class") == "INFRASTRUCTURE_OR_ADAPTER" for row in rows)
        state = "INVALID_INFRASTRUCTURE" if infrastructure_failures else "COMPLETE"
        return HDNext1CampaignResult(self.calls_used, state)
