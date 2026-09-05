from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import statistics
import time
from typing import Any, Iterable, Mapping
import uuid

from .hd_next1_authorization import validate_owner_authorization
from .hd_next1_budget import HDNext1BudgetState
from .hd_next1_cases import (
    CONFIRMATION_FAMILY_MAP,
    describe_observable_stratum,
    generate_hd_next1_cases,
    generate_protected_case_pool,
)
from .hd_next1_final_analysis import analyze_protected_evidence
from .hd_next1_local_search import (
    LOCAL_SEARCH_RULE_HASH,
    LocalVariant,
    active_support_components,
    generate_local_variants,
    variant_identity,
)
from .hd_next1_randomization import (
    ProtectedEvidenceState,
    default_confirmation_resolution_policy,
    freeze_confirmation_resolution,
    freeze_protected_assignments,
)
from .hd_next1_scheduler import Candidate, HDNext1Scheduler
from .hd_next1_space import build_zero_call_design, render_treatment_messages
from .models import ModelAdapter
from .types import Disposition, stable_hash


COST_SAFETY_MULTIPLIER = 2.0


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
    execution_position: int = -1
    local_search_kind: str = ""
    component_ids: tuple[str, ...] = ()
    expected_seconds: float = 1.0


@dataclass(frozen=True)
class HDNext1CampaignResult:
    physical_model_calls: int
    final_state: str


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(row), sort_keys=True) + "\n")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
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
    if evidence.get("deterministic_verifier") == "FAIL":
        return Disposition.ACQUIRE_EVIDENCE
    if evidence.get("missing"):
        return Disposition.ACQUIRE_EVIDENCE
    return Disposition.EXECUTE


def _complexity(vector: Mapping[str, str]) -> int:
    return len(active_support_components(vector))


def _raw_baseline_vector() -> dict[str, str]:
    row = {f"I{i}": "OFF" for i in range(1, 11)}
    row["I1"] = "ON"
    row.update({f"A{i}": "OFF" for i in range(1, 5)})
    row.update(
        {
            "representation": "RAW_PROSE",
            "ordering": "DEFAULT",
            "amount": "MINIMUM",
            "timing": "UPFRONT",
            "placement": "TASK_CONTEXT",
        }
    )
    return row


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
            "hd-next1-development",
            seed=int(self.config["seeds"]["development"]),
            per_family=4,
        )
        self.protected_cases = generate_protected_case_pool(self.config)
        self.case_by_id = {row.case_id: row for row in self.development_cases + self.protected_cases}
        self.treatment_by_id: dict[str, dict[str, Any]] = {
            str(row["treatment_id"]): dict(row) for row in self.design.treatments
        }
        self.budget = HDNext1BudgetState.default(max_inference_seconds=86400.0)
        self.calls_used = 0
        self.previous_call_id: str | None = None
        self.expected_seconds_by_model = {"SMALL_A": 0.5, "QWEN": 75.0}

    def run_model_free(self) -> HDNext1CampaignResult:
        return HDNext1CampaignResult(0, "MODEL_FREE_ONLY")

    def _assert_safe_start(self) -> None:
        if _read_jsonl(self.root / "physical_call_ledger.jsonl") or _read_jsonl(self.root / "campaign_journal.jsonl"):
            raise ValueError("HD-NEXT-1 refuses automatic resume/replay of an existing physical campaign")

    def _expected(self, model_key: str) -> float:
        return max(0.0001, float(self.expected_seconds_by_model[model_key]))

    def _register_variant(self, variant: LocalVariant) -> dict[str, Any]:
        row = {
            "treatment_id": variant.variant_id,
            "factor_vector": dict(variant.factor_vector),
            "kind": variant.kind,
            "component_ids": list(variant.component_ids),
            "local_search_rule_hash": LOCAL_SEARCH_RULE_HASH,
        }
        self.treatment_by_id[variant.variant_id] = row
        return row

    def _register_generated(
        self,
        *,
        kind: str,
        component_ids: tuple[str, ...],
        factor_vector: Mapping[str, str],
    ) -> dict[str, Any]:
        treatment_id = variant_identity(kind, component_ids, factor_vector)
        row = {
            "treatment_id": treatment_id,
            "factor_vector": dict(factor_vector),
            "kind": kind,
            "component_ids": list(component_ids),
            "local_search_rule_hash": LOCAL_SEARCH_RULE_HASH,
        }
        self.treatment_by_id[treatment_id] = row
        return row

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
                            unit_id=stable_hash(
                                {"stage": "T1", "case": case.case_id, "model": model_key, "rep": repetition}
                            ),
                            stage="T1_CALIBRATION",
                            model_key=model_key,
                            pool="calibration",
                            case_id=case.case_id,
                            treatment_id=str(baseline["treatment_id"]),
                            factor_vector=dict(baseline["factor_vector"]),
                            expected_seconds=self._expected(model_key),
                        )
                    )
        if len(rows) != 24:
            raise ValueError("HD-NEXT-1 calibration must remain exactly 24 calls")
        return tuple(rows)

    def _freeze_cost_calibration(self) -> None:
        rows = [row for row in _read_jsonl(self.root / "normalized_model_calls.jsonl") if row.get("stage") == "T1_CALIBRATION"]
        if len(rows) != 24:
            raise ValueError("cost calibration cannot freeze before all 24 calibration calls commit")
        medians: dict[str, float] = {}
        for model_key in ("SMALL_A", "QWEN"):
            values = [max(0.0001, float(row.get("actual_seconds", 0.0))) for row in rows if row.get("model_key") == model_key]
            if len(values) != 12:
                raise ValueError(f"calibration requires 12 observations for {model_key}")
            medians[model_key] = statistics.median(values)
            self.expected_seconds_by_model[model_key] = max(values) * COST_SAFETY_MULTIPLIER
        remaining_small = 576 - 12
        remaining_qwen = 96 - 12
        projected_remaining = COST_SAFETY_MULTIPLIER * (
            remaining_small * self.expected_seconds_by_model["SMALL_A"]
            + remaining_qwen * self.expected_seconds_by_model["QWEN"]
        )
        self.budget.max_inference_seconds = max(
            self.budget.inference_seconds_reserved + projected_remaining,
            self.budget.inference_seconds_reserved + 1.0,
        )
        _write_json(
            self.root / "cost_calibration_result.json",
            {
                "median_seconds": medians,
                "reserved_expected_seconds": dict(self.expected_seconds_by_model),
                "safety_multiplier": COST_SAFETY_MULTIPLIER,
                "frozen_max_inference_seconds": self.budget.max_inference_seconds,
                "physical_model_calls": 24,
            },
        )

    def _broad_small_a_units(self) -> tuple[ExecutionUnit, ...]:
        treatments = tuple(self.design.treatments)
        if len(treatments) > 216:
            raise ValueError(
                f"zero-call design requires {len(treatments)} broad treatments but T2 ceiling is 216; claim-space adequacy fails"
            )
        rows: list[ExecutionUnit] = []
        seen_pairs: set[tuple[str, str]] = set()
        round_index = 0
        while len(rows) < 216:
            made_progress = False
            for index, treatment in enumerate(treatments):
                case = self.development_cases[(index + round_index) % len(self.development_cases)]
                pair = (str(treatment["treatment_id"]), case.case_id)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                made_progress = True
                rows.append(
                    ExecutionUnit(
                        unit_id=stable_hash({"stage": "T2", "treatment": pair[0], "case": pair[1]}),
                        stage="T2_SMALL_A_SCREEN",
                        model_key="SMALL_A",
                        pool="development",
                        case_id=case.case_id,
                        treatment_id=pair[0],
                        factor_vector=dict(treatment["factor_vector"]),
                        expected_seconds=self._expected("SMALL_A"),
                    )
                )
                if len(rows) == 216:
                    break
            if not made_progress:
                raise ValueError("T2 cannot create 216 unique treatment/case observations")
            round_index += 1
        observed_treatments = {row.treatment_id for row in rows}
        if observed_treatments != {str(row["treatment_id"]) for row in treatments}:
            raise ValueError("T2 failed to physically represent every admitted zero-call treatment")
        return tuple(rows)

    def _score_treatments(self, stage: str) -> dict[str, dict[str, float]]:
        rows = [row for row in _read_jsonl(self.root / "normalized_model_calls.jsonl") if row.get("stage") == stage]
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(str(row["treatment_id"]), []).append(row)
        result: dict[str, dict[str, float]] = {}
        for treatment_id, values in grouped.items():
            result[treatment_id] = {
                "n": float(len(values)),
                "verified": float(sum(bool(row.get("verified_outcome_correct")) for row in values)),
                "success_rate": sum(bool(row.get("verified_outcome_correct")) for row in values) / len(values),
                "latency_ms": sum(float(row.get("latency_ms", 0.0)) for row in values) / len(values),
            }
        return result

    def _preliminary_winner(self) -> dict[str, Any]:
        scores = self._score_treatments("T2_SMALL_A_SCREEN")
        if not scores:
            raise ValueError("T2 produced no development evidence")
        ranked = sorted(
            scores,
            key=lambda treatment_id: (
                scores[treatment_id]["success_rate"],
                -_complexity(self.treatment_by_id[treatment_id]["factor_vector"]),
                -scores[treatment_id]["latency_ms"],
                treatment_id,
            ),
            reverse=True,
        )
        return self.treatment_by_id[ranked[0]]

    def _representative_confirmation_families(self) -> tuple[Any, ...]:
        rows: list[Any] = []
        for family in CONFIRMATION_FAMILY_MAP.values():
            match = next(case for case in self.development_cases if case.family == family)
            rows.append(match)
        return tuple(rows)

    def _local_minimality_units(self, preliminary: Mapping[str, Any]) -> tuple[ExecutionUnit, ...]:
        base_id = str(preliminary["treatment_id"])
        base_vector = dict(preliminary["factor_vector"])
        variants = tuple(generate_local_variants(base_vector))
        for variant in variants:
            self._register_variant(variant)
        reps = self._representative_confirmation_families()
        ablation_cases = reps[:3]
        rows: list[ExecutionUnit] = []
        seen_pairs: set[tuple[str, str]] = set()

        def add(treatment_id: str, vector: Mapping[str, str], case: Any, kind: str, components: tuple[str, ...]) -> None:
            pair = (treatment_id, case.case_id)
            if pair in seen_pairs or len(rows) >= 96:
                return
            seen_pairs.add(pair)
            rows.append(
                ExecutionUnit(
                    unit_id=stable_hash({"stage": "T3", "treatment": treatment_id, "case": case.case_id}),
                    stage="T3_LOCAL_MINIMALITY",
                    model_key="SMALL_A",
                    pool="development",
                    case_id=case.case_id,
                    treatment_id=treatment_id,
                    factor_vector=dict(vector),
                    local_search_kind=kind,
                    component_ids=components,
                    expected_seconds=self._expected("SMALL_A"),
                )
            )

        for case in reps:
            add(base_id, base_vector, case, "BASE", ())
        for variant in variants:
            if variant.kind in {"LEAVE_ONE_OUT", "JOINT_REMOVAL"}:
                for case in ablation_cases:
                    add(variant.variant_id, variant.factor_vector, case, variant.kind, variant.component_ids)
        for variant in variants:
            if variant.kind == "NEGATIVE_TRANSFER":
                for case in reps:
                    add(variant.variant_id, variant.factor_vector, case, variant.kind, variant.component_ids)

        policies = [(base_id, base_vector, "BASE", ())] + [
            (row.variant_id, row.factor_vector, row.kind, row.component_ids) for row in variants
        ]
        for treatment_id, vector, kind, components in policies:
            for case in self.development_cases:
                add(treatment_id, vector, case, kind, components)
                if len(rows) == 96:
                    break
            if len(rows) == 96:
                break
        if len(rows) != 96:
            raise ValueError(f"T3 local-minimality design produced {len(rows)} calls; expected exactly 96")
        return tuple(rows)

    def _matched_t3(self, left_id: str, right_id: str) -> tuple[int, int, int]:
        rows = [row for row in _read_jsonl(self.root / "normalized_model_calls.jsonl") if row.get("stage") == "T3_LOCAL_MINIMALITY"]
        by_case: dict[str, dict[str, bool]] = {}
        for row in rows:
            treatment_id = str(row.get("treatment_id"))
            if treatment_id not in {left_id, right_id}:
                continue
            by_case.setdefault(str(row["case_id"]), {})[treatment_id] = bool(row.get("verified_outcome_correct"))
        left_only = right_only = n = 0
        for values in by_case.values():
            if left_id not in values or right_id not in values:
                continue
            n += 1
            left_only += int(values[left_id] and not values[right_id])
            right_only += int(values[right_id] and not values[left_id])
        return left_only, right_only, n

    def _select_promoted_candidate(self, preliminary: Mapping[str, Any]) -> dict[str, Any]:
        base_id = str(preliminary["treatment_id"])
        candidates = [preliminary]
        for treatment_id, row in self.treatment_by_id.items():
            if row.get("kind") not in {"LEAVE_ONE_OUT", "JOINT_REMOVAL"}:
                continue
            base_only, candidate_only, n = self._matched_t3(base_id, treatment_id)
            if n >= 3 and candidate_only >= base_only:
                candidates.append(row)
        candidates.sort(
            key=lambda row: (
                _complexity(row["factor_vector"]),
                str(row["treatment_id"]),
            )
        )
        return dict(candidates[0])

    def _detect_candidate_boundary(self, base_id: str, negative_ids: tuple[str, ...]) -> dict[str, object] | None:
        rows = [row for row in _read_jsonl(self.root / "normalized_model_calls.jsonl") if row.get("stage") == "T3_LOCAL_MINIMALITY"]
        by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            treatment_id = str(row.get("treatment_id"))
            if treatment_id == base_id or treatment_id in negative_ids:
                by_key[(str(row["case_id"]), treatment_id)] = row
        features = ("evidence_missing", "irreversible", "invariant_sensitive", "boundary_exceeded", "risk")
        best: tuple[float, str, str, object, int, int] | None = None
        for negative_id in negative_ids:
            paired: list[tuple[dict[str, object], int]] = []
            case_ids = sorted({case_id for case_id, treatment_id in by_key if treatment_id == base_id})
            for case_id in case_ids:
                base = by_key.get((case_id, base_id))
                extra = by_key.get((case_id, negative_id))
                if not base or not extra:
                    continue
                effect = int(bool(extra.get("verified_outcome_correct"))) - int(bool(base.get("verified_outcome_correct")))
                paired.append((dict(base.get("observable_stratum") or {}), effect))
            for feature in features:
                values = sorted({str(stratum.get(feature)) for stratum, _ in paired})
                for value in values:
                    inside = [effect for stratum, effect in paired if str(stratum.get(feature)) == value]
                    outside = [effect for stratum, effect in paired if str(stratum.get(feature)) != value]
                    if len(inside) < 2 or len(outside) < 2:
                        continue
                    inside_mean = sum(inside) / len(inside)
                    outside_mean = sum(outside) / len(outside)
                    if inside_mean == 0.0 or outside_mean == 0.0 or inside_mean * outside_mean >= 0.0:
                        continue
                    contrast = abs(inside_mean - outside_mean)
                    candidate = (
                        contrast,
                        negative_id,
                        feature,
                        value,
                        1 if inside_mean > 0 else -1,
                        1 if outside_mean > 0 else -1,
                    )
                    if best is None or candidate > best:
                        best = candidate
        if best is None:
            return None
        contrast, negative_id, feature, value, inside_direction, outside_direction = best
        return {
            "field": feature,
            "equals": value,
            "negative_treatment_id": negative_id,
            "expected_inside_direction": inside_direction,
            "expected_outside_direction": outside_direction,
            "development_contrast": contrast,
            "predicate_is_pre_outcome": True,
            "frozen_before_confirmation": True,
            "prevents_material_safety_regression": False,
        }

    @staticmethod
    def _protected_spec(record: Mapping[str, Any]) -> dict[str, object]:
        spec = {
            "treatment_id": str(record["treatment_id"]),
            "factor_vector": dict(record["factor_vector"]),
        }
        if record.get("local_search_rule_hash"):
            spec.update(
                {
                    "kind": str(record.get("kind") or ""),
                    "component_ids": list(record.get("component_ids") or ()),
                    "local_search_rule_hash": str(record["local_search_rule_hash"]),
                }
            )
        return spec

    def _development_freeze(self, preliminary: Mapping[str, Any]) -> dict[str, object]:
        promoted = self._select_promoted_candidate(preliminary)
        promoted_id = str(promoted["treatment_id"])
        promoted_vector = dict(promoted["factor_vector"])

        local_variants = tuple(generate_local_variants(promoted_vector))
        for variant in local_variants:
            self._register_variant(variant)
        leave_one_out = [row for row in local_variants if row.kind == "LEAVE_ONE_OUT"]
        strongest: LocalVariant | None = None
        if leave_one_out:
            scored: list[tuple[int, int, str, LocalVariant]] = []
            for variant in leave_one_out:
                base_only, challenger_only, n = self._matched_t3(promoted_id, variant.variant_id)
                scored.append((challenger_only - base_only, n, variant.variant_id, variant))
            scored.sort(reverse=True, key=lambda row: (row[0], row[1], row[2]))
            strongest = scored[0][3]
        if strongest is None:
            raw_vector = _raw_baseline_vector()
            strongest_record = self._register_generated(
                kind="RAW_BASELINE",
                component_ids=("NO_LEGAL_LEAVE_ONE_OUT",),
                factor_vector=raw_vector,
            )
            strongest_component = None
        else:
            strongest_record = self._register_variant(strongest)
            strongest_component = strongest.component_ids[0] if len(strongest.component_ids) == 1 else None

        raw_record = self._register_generated(
            kind="RAW_BASELINE",
            component_ids=("I1_ONLY",),
            factor_vector=_raw_baseline_vector(),
        )
        negative_variants = [row for row in local_variants if row.kind == "NEGATIVE_TRANSFER"]
        for row in negative_variants:
            self._register_variant(row)
        negative_ids = tuple(row.variant_id for row in negative_variants)
        boundary = self._detect_candidate_boundary(promoted_id, negative_ids) if promoted_id == str(preliminary["treatment_id"]) else None
        if boundary:
            negative_record = self.treatment_by_id[str(boundary["negative_treatment_id"])]
        elif negative_variants:
            overloaded = next((row for row in negative_variants if row.factor_vector["amount"] == "OVERLOADED"), negative_variants[0])
            negative_record = self._register_variant(overloaded)
        else:
            negative_record = raw_record

        snapshot = {
            "evidence_tier": "DEVELOPMENT",
            "winner_treatment_id": promoted_id,
            "winner_factor_vector": promoted_vector,
            "retained_components": list(active_support_components(promoted_vector)),
            "strongest_ablation_component": strongest_component,
            "candidate_boundary": boundary,
            "local_search_rule_hash": LOCAL_SEARCH_RULE_HASH,
            "protected_treatments": {
                "CONFIRM_PROMOTED_POLICY": self._protected_spec(promoted),
                "CONFIRM_RAW_BASELINE": self._protected_spec(raw_record),
                "CONFIRM_STRONGEST_CHALLENGER": self._protected_spec(strongest_record),
                "CONFIRM_NEGATIVE_TRANSFER_CONTROL": self._protected_spec(negative_record),
            },
            "source_hash": stable_hash(
                [
                    row
                    for row in _read_jsonl(self.root / "normalized_model_calls.jsonl")
                    if row.get("stage") in {"T2_SMALL_A_SCREEN", "T3_LOCAL_MINIMALITY"}
                ]
            ),
        }
        return snapshot

    def _qwen_development_units(self, snapshot: Mapping[str, object]) -> tuple[ExecutionUnit, ...]:
        protected = dict(snapshot["protected_treatments"])
        role_order = (
            "CONFIRM_PROMOTED_POLICY",
            "CONFIRM_STRONGEST_CHALLENGER",
            "CONFIRM_NEGATIVE_TRANSFER_CONTROL",
        )
        cases = self._representative_confirmation_families()[:7]
        rows: list[ExecutionUnit] = []
        for case in cases:
            for role in role_order:
                spec = dict(protected[role])
                rows.append(
                    ExecutionUnit(
                        unit_id=stable_hash({"stage": "T4T5", "case": case.case_id, "role": role}),
                        stage="T4T5_QWEN_DISCRIMINATION",
                        model_key="QWEN",
                        pool="development",
                        case_id=case.case_id,
                        treatment_id=str(spec["treatment_id"]),
                        factor_vector={str(key): str(value) for key, value in dict(spec["factor_vector"]).items()},
                        treatment_role=role,
                        expected_seconds=self._expected("QWEN"),
                    )
                )
        if len(rows) != 21:
            raise ValueError("T4/T5 Qwen discrimination must remain exactly 21 calls")
        return tuple(rows)

    def _resolve_protected(self, snapshot: Mapping[str, object]):
        policy = default_confirmation_resolution_policy(self.design)
        assignments = freeze_protected_assignments(
            self.protected_cases,
            self.design,
            policy,
            seed=int(self.config["randomization_seed"]),
        )
        resolved = freeze_confirmation_resolution(assignments, self.design, snapshot)
        _write_jsonl(
            self.root / "confirmation_assignment_resolution.jsonl",
            (row.to_dict() for row in resolved),
        )
        return resolved

    def _protected_units(self, resolved: Iterable[Any], partition: str) -> tuple[ExecutionUnit, ...]:
        rows: list[ExecutionUnit] = []
        for assignment in resolved:
            if assignment.partition != partition:
                continue
            if not assignment.resolved_factor_vector:
                raise ValueError("protected assignment lacks a frozen resolved factor vector")
            rows.append(
                ExecutionUnit(
                    unit_id=assignment.assignment_id,
                    stage="T6_FRESH_CONFIRMATION" if partition == "hd-next1-fresh" else "T6_SEALED_CONFIRMATION",
                    model_key=assignment.model_key,
                    pool="confirmation",
                    case_id=assignment.case_id,
                    treatment_id=str(assignment.resolved_treatment_id),
                    factor_vector=dict(assignment.resolved_factor_vector),
                    treatment_role=assignment.treatment_role,
                    execution_position=int(assignment.execution_position),
                    expected_seconds=self._expected(assignment.model_key),
                )
            )
        return tuple(sorted(rows, key=lambda row: row.execution_position))

    def _execute_unit(self, unit: ExecutionUnit) -> None:
        if unit.model_key not in self.adapters:
            raise ValueError(f"missing adapter for {unit.model_key}")
        case = self.case_by_id[unit.case_id]
        adapter = self.adapters[unit.model_key]
        self.budget.reserve(unit.model_key, unit.pool, expected_seconds=unit.expected_seconds)
        _append_jsonl(
            self.root / "cost_budget_state.jsonl",
            {"event": "RESERVED", "unit_id": unit.unit_id, **self.budget.to_dict()},
        )
        system, prompt, treatment_meta = render_treatment_messages(case, unit.factor_vector)
        call_id = f"hdnext1-call-{uuid.uuid4().hex}"
        request = {
            "physical_model_call_id": call_id,
            "previous_physical_model_call_id": self.previous_call_id,
            "unit_id": unit.unit_id,
            "stage": unit.stage,
            "model_key": unit.model_key,
            "model_id": str(getattr(adapter, "model_id", "unknown")),
            "model_digest": str(getattr(adapter, "model_digest", "SYNTHETIC_OR_UNAVAILABLE")),
            "case_id": case.case_id,
            "partition": str((case.metadata or {}).get("partition", "")),
            "treatment_id": unit.treatment_id,
            "treatment_role": unit.treatment_role,
            "execution_position": unit.execution_position,
            "local_search_kind": unit.local_search_kind,
            "component_ids": list(unit.component_ids),
            "factor_vector": dict(unit.factor_vector),
            "factor_vector_hash": stable_hash(unit.factor_vector),
            "system": system,
            "prompt": prompt,
            "generation_options": dict(getattr(adapter, "generation_options", {}) or {}),
            "system_message_hash": treatment_meta["system_message_hash"],
            "user_message_hash": treatment_meta["user_message_hash"],
        }
        _append_jsonl(self.root / "raw_model_requests.jsonl", request)
        _append_jsonl(
            self.root / "campaign_journal.jsonl",
            {"physical_model_call_id": call_id, "unit_id": unit.unit_id, "state": "STARTED"},
        )
        start = time.perf_counter()
        try:
            response = adapter.complete(prompt, system=system)
            actual_seconds = max(0.000001, time.perf_counter() - start)
            answer = _parse_answer(response.text)
            answer_correct = _normalize(answer) == _normalize(_expected_answer(case))
            compiled = _compile_disposition(case)
            disposition_correct = compiled is case.expected_disposition
            verified = bool(answer_correct and disposition_correct)
            raw_response = {
                "physical_model_call_id": call_id,
                "unit_id": unit.unit_id,
                "text": response.text,
                "payload": dict(response.raw),
            }
            completion_class = "SEMANTIC_RESULT"
            input_tokens = response.input_tokens
            output_tokens = response.output_tokens
            latency_ms = response.latency_ms
            model_id = response.model
        except Exception as exc:
            actual_seconds = max(0.000001, time.perf_counter() - start)
            answer_correct = False
            compiled = _compile_disposition(case)
            disposition_correct = compiled is case.expected_disposition
            verified = False
            raw_response = {
                "physical_model_call_id": call_id,
                "unit_id": unit.unit_id,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            completion_class = "INFRASTRUCTURE_OR_ADAPTER"
            input_tokens = 0
            output_tokens = 0
            latency_ms = actual_seconds * 1000.0
            model_id = str(getattr(adapter, "model_id", "unknown"))

        self.budget.reconcile(
            unit.model_key,
            unit.pool,
            expected_seconds=unit.expected_seconds,
            actual_seconds=actual_seconds,
        )
        normalized = {
            "physical_model_call_id": call_id,
            "previous_physical_model_call_id": self.previous_call_id,
            "unit_id": unit.unit_id,
            "stage": unit.stage,
            "model_key": unit.model_key,
            "model_id": model_id,
            "model_digest": str(getattr(adapter, "model_digest", "SYNTHETIC_OR_UNAVAILABLE")),
            "case_id": case.case_id,
            "family": case.family,
            "partition": str((case.metadata or {}).get("partition", "")),
            "observable_stratum": describe_observable_stratum(case),
            "treatment_id": unit.treatment_id,
            "treatment_role": unit.treatment_role,
            "execution_position": unit.execution_position,
            "local_search_kind": unit.local_search_kind,
            "component_ids": list(unit.component_ids),
            "factor_vector_hash": stable_hash(unit.factor_vector),
            "answer_correct": answer_correct,
            "compiled_disposition": compiled.value,
            "compiled_disposition_correct": disposition_correct,
            "verified_outcome_correct": verified,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "actual_seconds": actual_seconds,
            "completion_class": completion_class,
        }
        _append_jsonl(self.root / "raw_model_responses.jsonl", raw_response)
        _append_jsonl(self.root / "normalized_model_calls.jsonl", normalized)
        _append_jsonl(
            self.root / "runtime_telemetry.jsonl",
            {
                "physical_model_call_id": call_id,
                "unit_id": unit.unit_id,
                "latency_ms": latency_ms,
                "actual_seconds": actual_seconds,
                "completion_class": completion_class,
            },
        )
        _append_jsonl(
            self.root / "physical_call_ledger.jsonl",
            {
                "physical_model_call_id": call_id,
                "unit_id": unit.unit_id,
                "attempt": 1,
                "automatic_retry": False,
                "committed": True,
            },
        )
        _append_jsonl(
            self.root / "campaign_journal.jsonl",
            {"physical_model_call_id": call_id, "unit_id": unit.unit_id, "state": "COMMITTED"},
        )
        _append_jsonl(
            self.root / "cost_budget_state.jsonl",
            {"event": "RECONCILED", "unit_id": unit.unit_id, **self.budget.to_dict()},
        )
        self.calls_used += 1
        self.previous_call_id = call_id

    def _run_units(self, units: Iterable[ExecutionUnit], limit: int) -> bool:
        for unit in units:
            if self.calls_used >= limit:
                return False
            self._execute_unit(unit)
        return True

    def _fresh_gate_passes(self) -> bool:
        rows = [
            row
            for row in _read_jsonl(self.root / "normalized_model_calls.jsonl")
            if row.get("stage") == "T6_FRESH_CONFIRMATION"
        ]
        promoted = [row for row in rows if row.get("treatment_role") == "CONFIRM_PROMOTED_POLICY"]
        by_case: dict[str, dict[str, bool]] = {}
        for row in promoted:
            by_case.setdefault(str(row["case_id"]), {})[str(row["model_key"])] = bool(
                row.get("verified_outcome_correct")
            )
        matched = [value for value in by_case.values() if "QWEN" in value and "SMALL_A" in value]
        qwen_only = sum(value["QWEN"] and not value["SMALL_A"] for value in matched)
        small_success = sum(value["SMALL_A"] for value in matched)
        challenger_pairs: dict[str, dict[str, bool]] = {}
        for row in rows:
            if row.get("model_key") != "SMALL_A" or row.get("treatment_role") not in {
                "CONFIRM_PROMOTED_POLICY",
                "CONFIRM_STRONGEST_CHALLENGER",
            }:
                continue
            challenger_pairs.setdefault(str(row["case_id"]), {})[str(row["treatment_role"])] = bool(
                row.get("verified_outcome_correct")
            )
        challenger_only = sum(
            value.get("CONFIRM_STRONGEST_CHALLENGER", False)
            and not value.get("CONFIRM_PROMOTED_POLICY", False)
            for value in challenger_pairs.values()
            if len(value) == 2
        )
        pass_model = bool(matched) and qwen_only / len(matched) <= 0.05
        pass_candidate = bool(matched) and small_success / len(matched) >= 0.50 and challenger_only == 0
        passed = pass_model and pass_candidate
        _write_json(
            self.root / "fresh_gate_report.json",
            {
                "matched_model_cases": len(matched),
                "qwen_only_wins": qwen_only,
                "small_a_promoted_successes": small_success,
                "challenger_only_wins": challenger_only,
                "fresh_gate_passed": passed,
            },
        )
        return passed

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
        self._assert_safe_start()

        if not self._run_units(self._calibration_units(), limit):
            return HDNext1CampaignResult(self.calls_used, "EVIDENCE_CEILING_REACHED")
        self._freeze_cost_calibration()

        broad = self._broad_small_a_units()
        if not self._run_units(broad, limit):
            return HDNext1CampaignResult(self.calls_used, "EVIDENCE_CEILING_REACHED")
        preliminary = self._preliminary_winner()

        local_units = self._local_minimality_units(preliminary)
        if not self._run_units(local_units, limit):
            return HDNext1CampaignResult(self.calls_used, "EVIDENCE_CEILING_REACHED")
        snapshot = self._development_freeze(preliminary)
        _write_json(self.root / "development_freeze.json", snapshot)

        if not self._run_units(self._qwen_development_units(snapshot), limit):
            return HDNext1CampaignResult(self.calls_used, "EVIDENCE_CEILING_REACHED")

        resolved = self._resolve_protected(snapshot)
        evidence_state = ProtectedEvidenceState(resolved)
        evidence_state.open_partition("hd-next1-fresh")
        if not self._run_units(self._protected_units(resolved, "hd-next1-fresh"), limit):
            return HDNext1CampaignResult(self.calls_used, "EVIDENCE_CEILING_REACHED")
        if not self._fresh_gate_passes():
            return HDNext1CampaignResult(self.calls_used, "FRESH_CONFIRMATION_REFUTED")
        evidence_state.mark_fresh_gate_passed()
        evidence_state.open_partition("hd-next1-sealed")
        if not self._run_units(self._protected_units(resolved, "hd-next1-sealed"), limit):
            return HDNext1CampaignResult(self.calls_used, "EVIDENCE_CEILING_REACHED")

        rows = _read_jsonl(self.root / "normalized_model_calls.jsonl")
        decisions = analyze_protected_evidence(rows, snapshot)
        _write_json(self.root / "final_architecture_decisions.json", decisions)
        infrastructure_failures = sum(row.get("completion_class") == "INFRASTRUCTURE_OR_ADAPTER" for row in rows)
        if self.calls_used != 672:
            state = "EVIDENCE_CEILING_REACHED"
        elif infrastructure_failures:
            state = "INVALID_INFRASTRUCTURE"
        else:
            state = "COMPLETE"
        return HDNext1CampaignResult(self.calls_used, state)
