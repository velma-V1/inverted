from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .d3_closure_adequacy import ClaimAdequacyInputs, evaluate_claim_adequacy
from .d3_closure_cases import generate_closure_cases, one_per_family
from .d3_closure_covering import CoveringRequirement, generate_covering_design, measure_pairwise_coverage
from .d3_closure_prior_evidence import PriorEvidenceRecord, inventory_prior_evidence, write_prior_evidence_ledger
from .d3_closure_r0_state import derive_action_frontier, derive_pre_state
from .d3_closure_search_space import build_primary_search_space, treatment_equivalence_key
from .d3_closure_treatment import ClosureTreatmentPlan, derive_treatment_exposure, render_treatment


@dataclass(frozen=True)
class R0PackageSummary:
    final_state: str
    physical_model_calls: int
    physical_execution_authorized: bool
    treatment_count: int
    equivalence_class_count: int
    prior_record_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "final_state": self.final_state,
            "physical_model_calls": self.physical_model_calls,
            "physical_execution_authorized": self.physical_execution_authorized,
            "treatment_count": self.treatment_count,
            "equivalence_class_count": self.equivalence_class_count,
            "prior_record_count": self.prior_record_count,
        }


def _stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), sort_keys=True) + "\n")


def _live_factor_levels() -> dict[str, tuple[str, ...]]:
    factors = build_primary_search_space().factor_levels()
    # PROGRESSIVE requires a true multi-step delivery protocol. It remains a
    # live uncovered region rather than being faked as a one-call label.
    factors["timing"] = tuple(level for level in factors["timing"] if level != "PROGRESSIVE")
    return factors


def _row_is_legal(row: Mapping[str, str]) -> bool:
    return any(row[f"I{i}"] == "ON" for i in range(1, 11))


def _required_three_way_obligations() -> tuple[CoveringRequirement, ...]:
    # Every obligation includes at least one ON content field so the required
    # row is physically legal. Model/family three-way obligations are tracked
    # separately as effect-modifier obligations below.
    return (
        CoveringRequirement(("I4", "representation", "A3"), ("ON", "TYPED_FIELDS", "TARGET")),
        CoveringRequirement(("I7", "representation", "A2"), ("ON", "ADMISSIBLE_ACTION_MATRIX", "TARGET")),
        CoveringRequirement(("I2", "ordering", "A1"), ("ON", "STATE_FIRST", "TARGET")),
        CoveringRequirement(("I3", "ordering", "placement"), ("ON", "SAFETY_STATE_EVIDENCE_FIRST", "SYSTEM_CONTEXT")),
        CoveringRequirement(("I1", "amount", "timing"), ("ON", "OVERLOADED", "JUST_IN_TIME")),
    )


def _claim_contract() -> list[dict[str, object]]:
    return [
        {
            "claim_id": "INFORMATION_FIELD_VALUE",
            "objective": "SCREEN_INTERACTION_OPTIMIZE",
            "factors": [f"I{i}" for i in range(1, 11)],
            "effect_modifiers": ["model", "family", "missing_evidence", "dependency_depth", "novelty"],
            "required_evidence_tiers": ["E2_FRESH_DEVELOPMENT", "E3_FRESH_SEALED"],
            "controls": ["matched_removal", "token_burden_control"],
            "current_claim_ceiling": "SCREEN",
        },
        {
            "claim_id": "DELIVERY_POLICY",
            "objective": "SCREEN_INTERACTION_OPTIMIZE",
            "factors": ["representation", "ordering", "amount", "timing", "placement"],
            "effect_modifiers": ["model", "family", "context_burden"],
            "required_evidence_tiers": ["E2_FRESH_DEVELOPMENT", "E3_FRESH_SEALED"],
            "controls": ["semantic_equivalence", "shuffled_order", "token_matched_burden"],
            "current_claim_ceiling": "SCREEN",
        },
        {
            "claim_id": "MODEL_VISIBLE_ASSISTANCE",
            "objective": "CAUSAL_INTERACTION_MINIMALITY",
            "factors": ["A1", "A2", "A3", "A4"],
            "effect_modifiers": ["model", "family", "action_space_size", "missing_evidence"],
            "required_evidence_tiers": ["E2_FRESH_DEVELOPMENT", "E3_FRESH_SEALED"],
            "controls": ["TARGET", "SHAM", "RAW", "leave_one_out"],
            "current_claim_ceiling": "SCREEN",
        },
        {
            "claim_id": "MODEL_SUBSTITUTION_ROUTING",
            "objective": "BOUNDARY",
            "factors": ["model", "support_policy", "reasoning_policy"],
            "effect_modifiers": ["family", "novelty", "dependency_depth", "action_space_size", "irreversibility"],
            "required_evidence_tiers": ["E2_FRESH_DEVELOPMENT", "E3_FRESH_SEALED"],
            "controls": ["same_case_same_support", "cost_matched_analysis"],
            "current_claim_ceiling": "UNRESOLVED",
        },
        {
            "claim_id": "REAL_RECOVERY",
            "objective": "CAUSAL_TRANSITION",
            "factors": ["failure_class", "detection", "recovery_frontier", "recovery_action"],
            "effect_modifiers": ["model", "family", "external_effect_state"],
            "required_evidence_tiers": ["E2_FRESH_DEVELOPMENT", "E3_FRESH_SEALED"],
            "controls": ["actual_second_action", "independent_verification"],
            "current_claim_ceiling": "UNRESOLVED",
        },
        {
            "claim_id": "NEGATIVE_TRANSFER",
            "objective": "BOUNDARY",
            "factors": ["information_quality", "amount", "support", "reasoning_depth"],
            "effect_modifiers": ["model", "family", "novelty"],
            "required_evidence_tiers": ["E2_FRESH_DEVELOPMENT", "E3_FRESH_SEALED"],
            "controls": ["matched_raw", "token_matched_irrelevant", "stale_or_misleading_non_authoritative"],
            "current_claim_ceiling": "UNRESOLVED",
        },
        {
            "claim_id": "RESPONSIBILITY_BOUNDARY",
            "objective": "CAUSAL_OWNERSHIP",
            "factors": ["state", "authority", "invariants", "disposition", "verification", "recovery", "routing"],
            "effect_modifiers": ["family", "risk", "reversibility"],
            "required_evidence_tiers": ["E0_DETERMINISTIC", "E2_FRESH_DEVELOPMENT", "E3_FRESH_SEALED"],
            "controls": ["system_replay", "model_visible_ablation", "matched_intervention"],
            "current_claim_ceiling": "SCREEN",
        },
    ]


def _prior_value(records: tuple[PriorEvidenceRecord, ...], family: str) -> tuple[float, tuple[str, ...]]:
    relevant = [
        record
        for record in records
        if record.present
        and record.scheduler_prior_weight > 0
        and (not record.families or family in record.families)
    ]
    relevant.sort(key=lambda record: (-record.scheduler_prior_weight, record.evidence_source_id))
    if not relevant:
        return 0.0, ()
    score = min(1.0, sum(record.scheduler_prior_weight for record in relevant) / len(relevant))
    return score, tuple(record.evidence_source_id for record in relevant)


def _treatment_plan(row: Mapping[str, str]) -> ClosureTreatmentPlan:
    return ClosureTreatmentPlan(
        field_ids=tuple(f"I{i}" for i in range(1, 11) if row[f"I{i}"] == "ON"),
        representation=row["representation"],
        ordering=row["ordering"],
        amount=row["amount"],
        timing=row["timing"],
        placement=row["placement"],
        assistance=tuple(f"A{i}" for i in range(1, 5) if row[f"A{i}"] == "TARGET"),
    )


def _required_artifacts() -> set[str]:
    return {
        "closure_claim_space_manifest.json",
        "closure_search_space_manifest.json",
        "closure_candidate_equivalence_classes.jsonl",
        "closure_candidate_pruning_ledger.jsonl",
        "closure_prior_evidence_ledger.jsonl",
        "closure_treatment_catalog.jsonl",
        "closure_treatment_exposure.jsonl",
        "closure_pre_state_catalog.jsonl",
        "closure_action_frontier_catalog.jsonl",
        "closure_combinatorial_coverage.json",
        "closure_interaction_coverage.json",
        "closure_uncovered_space.json",
        "closure_claim_adequacy_report.json",
    }


def build_r0_package(
    repo_root: str | Path,
    output_root: str | Path,
    config: Mapping[str, Any],
) -> R0PackageSummary:
    repo = Path(repo_root)
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)

    search_space = build_primary_search_space()
    factors = _live_factor_levels()
    required_three_way = _required_three_way_obligations()
    design = generate_covering_design(
        factors,
        seed=int(config.get("generation_options", {}).get("seed", 20260902)),
        required_tuples=required_three_way,
        row_is_legal=_row_is_legal,
    )
    pairwise = measure_pairwise_coverage(design.rows, factors)
    if pairwise.ratio != 1.0:
        raise ValueError("R0 pairwise covering design is incomplete")

    prior_records = inventory_prior_evidence(repo)
    write_prior_evidence_ledger(root, prior_records)

    cases = one_per_family(
        generate_closure_cases(
            "closure-development",
            seed=int(config["seeds"]["development"]),
            per_family=max(1, int(config["cases_per_family"]["development"])),
        )
    )
    if not cases:
        raise ValueError("R0 requires at least one development case")
    models = tuple(sorted(str(key) for key in config["models"]))
    if not models:
        raise ValueError("R0 requires at least one declared model role")

    pre_states: dict[str, dict[str, Any]] = {}
    frontiers: dict[str, dict[str, Any]] = {}
    exposures: dict[str, dict[str, Any]] = {}
    treatments: list[dict[str, Any]] = []
    equivalence_members: dict[str, list[str]] = {}
    pruning: list[dict[str, Any]] = [
        {
            "candidate_scope": "timing=PROGRESSIVE",
            "reason_code": "REQUIRES_REAL_MULTI_STEP_PROTOCOL",
            "action": "DEFER_FROM_ONE_CALL_SCREEN",
            "evidence_tier": "E0_DETERMINISTIC",
            "note": "Progressive delivery remains live for a later real multi-step protocol.",
        }
    ]

    for index, factor_row in enumerate(design.rows):
        case = cases[index % len(cases)]
        model_key = models[(index // len(cases)) % len(models)]
        plan = _treatment_plan(factor_row)
        rendered = render_treatment(case, plan)
        exposure = derive_treatment_exposure(rendered, case)
        pre_state = derive_pre_state(case)
        frontier = derive_action_frontier(case)
        equivalence_id = treatment_equivalence_key(
            semantic_field_hash=rendered.semantic_field_hash,
            rendered_hash=rendered.rendered_hash,
            system_message_hash=rendered.system_message_hash,
            user_message_hash=rendered.user_message_hash,
            field_order=rendered.field_order,
            assistance_hash=rendered.assistance_hash,
        )
        treatment_id = _stable_hash(
            {"case_id": case.case_id, "model_key": model_key, "equivalence_class_id": equivalence_id}
        )
        prior_value, prior_sources = _prior_value(prior_records, str(case.family))
        treatments.append(
            {
                "treatment_id": treatment_id,
                "equivalence_class_id": equivalence_id,
                "case_id": case.case_id,
                "family": case.family,
                "model_key": model_key,
                "factor_vector": dict(factor_row),
                "field_ids": list(plan.field_ids),
                "representation": plan.representation,
                "ordering": plan.ordering,
                "amount": plan.amount,
                "timing": plan.timing,
                "placement": plan.placement,
                "assistance": list(plan.assistance),
                "semantic_field_hash": rendered.semantic_field_hash,
                "rendered_payload_hash": rendered.rendered_hash,
                "system_message_hash": rendered.system_message_hash,
                "user_message_hash": rendered.user_message_hash,
                "field_order": list(rendered.field_order),
                "assistance_hash": rendered.assistance_hash,
                "approx_token_count": rendered.approx_token_count,
                "exposure_id": exposure.exposure_id,
                "pre_state_id": pre_state.pre_state_id,
                "action_frontier_id": frontier.frontier_id,
                "prior_evidence_value": prior_value,
                "prior_evidence_sources": list(prior_sources),
                "evidence_tier": "E0_DETERMINISTIC",
                "physical_model_calls": 0,
                "scheduler_metadata": {
                    "coverage_novelty": "PLANNED_PAIRWISE_OR_TARGETED_INTERACTION",
                    "historical_prior_only": bool(prior_sources),
                    "discovery_challenger_eligible": True,
                    "fresh_observation_count": 0,
                },
            }
        )
        pre_states.setdefault(pre_state.pre_state_id, pre_state.to_dict())
        frontiers.setdefault(frontier.frontier_id, frontier.to_dict())
        exposures.setdefault(exposure.exposure_id, exposure.to_dict())
        equivalence_members.setdefault(equivalence_id, []).append(treatment_id)

    if not treatments:
        raise ValueError("R0 treatment catalog is empty")

    equivalence_rows: list[dict[str, Any]] = []
    for equivalence_id, members in sorted(equivalence_members.items()):
        unique_members = tuple(sorted(set(members)))
        equivalence_rows.append(
            {
                "equivalence_class_id": equivalence_id,
                "treatment_ids": list(unique_members),
                "member_count": len(unique_members),
                "physical_identity_basis": "semantic+rendered+system+user+order+assistance hashes",
            }
        )
        if len(unique_members) > 1:
            pruning.append(
                {
                    "candidate_scope": equivalence_id,
                    "reason_code": "ACTUAL_EXPOSURE_EQUIVALENCE",
                    "action": "COLLAPSE_DUPLICATE_PHYSICAL_TREATMENT",
                    "evidence_tier": "E0_DETERMINISTIC",
                    "member_count": len(unique_members),
                }
            )

    _write_json(
        root / "closure_claim_space_manifest.json",
        {
            "protocol": "D3-CLOSURE-v2-R0",
            "claims": _claim_contract(),
            "physical_model_calls": 0,
            "fresh_evidence_collected": False,
            "test5_design_in_scope": False,
        },
    )
    _write_json(
        root / "closure_search_space_manifest.json",
        {
            "protocol": "D3-CLOSURE-v2-R0",
            **search_space.to_manifest(),
            "admitted_one_call_factor_levels": {key: list(value) for key, value in factors.items()},
            "admitted_covering_rows": len(design.rows),
            "actual_catalog_treatments": len(treatments),
            "actual_equivalence_classes": len(equivalence_rows),
            "physical_model_calls": 0,
            "note": "Raw theoretical count is algebraic; R0 never materializes the full Cartesian product.",
        },
    )
    _write_jsonl(root / "closure_candidate_equivalence_classes.jsonl", equivalence_rows)
    _write_jsonl(root / "closure_candidate_pruning_ledger.jsonl", pruning)
    _write_jsonl(root / "closure_treatment_catalog.jsonl", treatments)
    _write_jsonl(
        root / "closure_treatment_exposure.jsonl",
        (exposures[key] for key in sorted(exposures)),
    )
    _write_jsonl(
        root / "closure_pre_state_catalog.jsonl",
        (pre_states[key] for key in sorted(pre_states)),
    )
    _write_jsonl(
        root / "closure_action_frontier_catalog.jsonl",
        (frontiers[key] for key in sorted(frontiers)),
    )

    _write_json(
        root / "closure_combinatorial_coverage.json",
        {
            "protocol": "D3-CLOSURE-v2-R0",
            "coverable_pairs": pairwise.coverable_pairs,
            "planned_covered_pairs": pairwise.covered_pairs,
            "planned_pairwise_coverage_ratio": pairwise.ratio,
            "missing_planned_pairs": [list(item) for item in pairwise.missing_pairs],
            "covering_rows": len(design.rows),
            "physical_observations": 0,
            "coverage_kind": "MODEL_FREE_PLANNED_COVERAGE",
        },
    )

    interaction_rows = [
        {
            "factors": list(requirement.factors),
            "levels": list(requirement.levels),
            "planned_in_covering_design": any(
                all(row[factor] == level for factor, level in zip(requirement.factors, requirement.levels))
                for row in design.rows
            ),
            "physical_observed": False,
        }
        for requirement in required_three_way
    ]
    if not all(row["planned_in_covering_design"] for row in interaction_rows):
        raise ValueError("R0 required three-way obligation is absent from covering design")
    _write_json(
        root / "closure_interaction_coverage.json",
        {
            "protocol": "D3-CLOSURE-v2-R0",
            "required_three_way_obligations": interaction_rows,
            "planned_required_three_way_coverage_ratio": 1.0,
            "physical_observations": 0,
            "effect_modifier_obligations": [
                "content x representation x model",
                "content x amount x model",
                "content x A2/action-frontier x model",
                "missing-evidence x A3 x model",
                "state/version x A1 x family",
                "authority/invariant x ordering/placement x family",
                "amount x timing x model",
                "information x assistance x failure-family",
            ],
        },
    )
    _write_json(
        root / "closure_uncovered_space.json",
        {
            "protocol": "D3-CLOSURE-v2-R0",
            "physical_model_calls": 0,
            "fresh_evidence_collected": False,
            "explicit_uncovered_regions": [
                {
                    "region": "PROGRESSIVE_REAL_MULTI_STEP_DELIVERY",
                    "reason": "requires a real multi-step protocol; intentionally not represented as a one-call cosmetic treatment",
                    "later_round": "R3_OR_R5",
                },
                {
                    "region": "ROBUSTNESS_INFORMATION_QUALITY",
                    "reason": "stale/contradictory/noisy/misleading factors are second-stage boundary tests after a candidate exists",
                    "later_round": "R7",
                },
                {
                    "region": "FRESH_AND_SEALED_OUTCOMES",
                    "reason": "R0 is zero-call and cannot collect development or sealed physical evidence",
                    "later_round": "R1_TO_R8",
                },
                {
                    "region": "REAL_RECOVERY_TRANSITIONS",
                    "reason": "cognitive recovery requires a real second decision/action and is never synthesized in R0",
                    "later_round": "R5",
                },
            ],
        },
    )

    adequacy = evaluate_claim_adequacy(
        ClaimAdequacyInputs(
            claim_space_manifest_present=True,
            search_space_manifest_present=True,
            pairwise_coverage_ratio=pairwise.ratio,
            required_three_way_coverage_ratio=1.0,
            cost_calibration_complete=False,
            reproducibility_calibration_complete=False,
            cost_scaled_scheduler_ready=False,
            protected_discovery_ready=True,
            local_minimality_ready=False,
            real_recovery_ready=False,
            sealed_confirmation_protected=False,
            blocker_audit_green=False,
            launcher_path_green=False,
            unresolved_hard_blockers=0,
            unresolved_scientific_risks=0,
        )
    )
    adequacy_payload = adequacy.to_dict()
    adequacy_payload.update(
        {
            "protocol": "D3-CLOSURE-v2-R0",
            "physical_model_calls": 0,
            "evidence_tier_integrity": True,
            "r0_package_complete": True,
        }
    )
    _write_json(root / "closure_claim_adequacy_report.json", adequacy_payload)

    required = _required_artifacts()
    missing = sorted(name for name in required if not (root / name).exists())
    empty = sorted(name for name in required if (root / name).exists() and (root / name).stat().st_size == 0)
    r0_ready = not missing and not empty and pairwise.ratio == 1.0 and not adequacy.physical_execution_authorized
    readiness = {
        "protocol": "D3-CLOSURE-v2-R0",
        "final_state": "R0_MODEL_FREE_COMPLETE" if r0_ready else "R0_INCOMPLETE",
        "r0_ready": r0_ready,
        "physical_model_calls": 0,
        "physical_execution_authorized": False,
        "required_artifacts": sorted(required),
        "missing_artifacts": missing,
        "empty_artifacts": empty,
        "treatment_count": len(treatments),
        "equivalence_class_count": len(equivalence_rows),
        "prior_record_count": len(prior_records),
        "historical_prior_fresh_observation_count": 0,
        "pairwise_plan_complete": pairwise.ratio == 1.0,
        "required_three_way_plan_complete": True,
        "note": "R0 readiness is not physical Closure authorization; R1 and later gates remain mandatory.",
    }
    _write_json(root / "closure_r0_readiness_report.json", readiness)
    if not r0_ready:
        raise ValueError(f"R0 package incomplete: missing={missing}, empty={empty}")

    return R0PackageSummary(
        final_state="R0_MODEL_FREE_COMPLETE",
        physical_model_calls=0,
        physical_execution_authorized=False,
        treatment_count=len(treatments),
        equivalence_class_count=len(equivalence_rows),
        prior_record_count=len(prior_records),
    )
