from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, TextIO
import uuid

from inverted.progress import InPlaceProgress

from .d3_closure_analysis import ensure_closure_output_skeleton, finalize_closure_package
from .d3_closure_assistance import AssistanceMode, apply_predecision_assistance
from .d3_closure_cases import generate_closure_cases, one_per_family
from .d3_closure_information import (
    ClosureAmount,
    ClosureInformationPlan,
    ClosureOrdering,
    render_closure_packet,
)
from .d3_closure_scheduler import ClosureDecision, ClosureScheduler
from .d3_closure_scoring import (
    CompletionClass,
    SystemSemantics,
    classify_completion,
    compile_system_disposition,
    score_semantic_action,
)
from .models import ModelAdapter
from .statistics import sequential_evidence
from .types import stable_hash


_BASE_SYSTEM = (
    "INVERTED D3-CLOSURE-v2 controlled measurement. Use only the supplied task and context. "
    "Return exactly one JSON object containing key answer. Do not invent a system disposition."
)


@dataclass(frozen=True)
class ClosureExperiment:
    experiment_id: str
    block: str
    model_key: str
    case: Any
    arm: str
    sealed: bool = False
    assistance_mechanism: str | None = None
    assistance_mode: AssistanceMode | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "block": self.block,
            "model_key": self.model_key,
            "case_id": self.case.case_id,
            "family": self.case.family,
            "arm": self.arm,
            "sealed": self.sealed,
            "assistance_mechanism": self.assistance_mechanism,
            "assistance_mode": self.assistance_mode.value if self.assistance_mode else None,
        }


@dataclass(frozen=True)
class ClosurePlan:
    experiments: tuple[ClosureExperiment, ...]
    max_calls: int = 200
    sealed_reserve: int = 48

    @property
    def planned_physical_calls(self) -> int:
        return len(self.experiments)


@dataclass(frozen=True)
class ClosureCampaignResult:
    physical_model_calls: int
    final_state: str
    planned_physical_calls: int


def _experiment_id(block: str, model_key: str, case_id: str, arm: str) -> str:
    return f"{block}:{model_key}:{case_id}:{arm}"


def build_closure_plan(config: Mapping[str, Any]) -> ClosurePlan:
    seeds = config["seeds"]
    counts = config["cases_per_family"]
    models = tuple(str(key) for key in config["models"])
    development = generate_closure_cases(
        "closure-development", seed=int(seeds["development"]), per_family=int(counts["development"])
    )
    fresh = generate_closure_cases(
        "closure-fresh", seed=int(seeds["fresh"]), per_family=int(counts["fresh"])
    )
    sealed = generate_closure_cases(
        "closure-sealed", seed=int(seeds["sealed"]), per_family=int(counts["sealed"])
    )

    experiments: list[ClosureExperiment] = []

    # C1: one fresh raw case per family across both primary models.
    for case in one_per_family(fresh):
        for model_key in models:
            arm = "RAW"
            experiments.append(
                ClosureExperiment(_experiment_id("C1", model_key, case.case_id, arm), "C1", model_key, case, arm)
            )

    # C2: two real information amounts on nine structurally distinct families.
    for case in one_per_family(development)[:9]:
        for model_key in models:
            for amount in (ClosureAmount.MINIMUM, ClosureAmount.FULL):
                arm = f"INFO_{amount.value}"
                experiments.append(
                    ClosureExperiment(_experiment_id("C2", model_key, case.case_id, arm), "C2", model_key, case, arm)
                )

    # C3: real pre-decision assistance TARGET vs SHAM, rotating A1-A4.
    assistance_cases = one_per_family(development)[:9]
    for index, case in enumerate(assistance_cases):
        mechanism = f"A{(index % 4) + 1}"
        for model_key in models:
            for mode in (AssistanceMode.TARGET, AssistanceMode.SHAM):
                arm = f"ASSIST_{mechanism}_{mode.value}"
                experiments.append(
                    ClosureExperiment(
                        _experiment_id("C3", model_key, case.case_id, arm),
                        "C3",
                        model_key,
                        case,
                        arm,
                        assistance_mechanism=mechanism,
                        assistance_mode=mode,
                    )
                )

    # C4: recovery/first-error exposure on high-consequence/recovery families.
    recovery_families = {"AUTHORITY", "TRANSACTION", "VERIFIER_ORACLE", "RECOVERY", "GLOBAL_INTERACTION"}
    recovery_cases = tuple(case for case in development if case.family in recovery_families)
    for case in recovery_cases:
        for model_key in models:
            arm = "RECOVERY_CONTEXT"
            experiments.append(
                ClosureExperiment(_experiment_id("C4", model_key, case.case_id, arm), "C4", model_key, case, arm)
            )

    # C5 and C6 are reserved for evidence-driven transition localization and contradiction checks.
    # They are not pre-spent before an observed unresolved boundary justifies them.

    # C7: one untouched sealed case per family, RAW vs SUPPORTED, both primary models.
    for case in one_per_family(sealed):
        for model_key in models:
            for arm in ("SEALED_RAW", "SEALED_SUPPORTED"):
                experiments.append(
                    ClosureExperiment(
                        _experiment_id("C7", model_key, case.case_id, arm),
                        "C7",
                        model_key,
                        case,
                        arm,
                        sealed=True,
                    )
                )

    plan = ClosurePlan(
        experiments=tuple(experiments),
        max_calls=int(config["max_calls"]),
        sealed_reserve=int(config["sealed_reserve"]),
    )
    if plan.max_calls != 200:
        raise ValueError("D3-Closure v2 absolute call ceiling must remain 200")
    if plan.sealed_reserve != 48:
        raise ValueError("D3-Closure v2 confirmation reserve must remain 48")
    if len([row for row in plan.experiments if row.block == "C7"]) > plan.sealed_reserve:
        raise ValueError("closure sealed plan exceeds protected reserve")
    if plan.planned_physical_calls > plan.max_calls:
        raise ValueError("closure plan exceeds physical-call ceiling")
    return plan


def _case_context(case: Any) -> dict[str, Any]:
    information = dict((case.metadata or {}).get("d3_information", {}))
    state = dict(information.get("I2", {}))
    authority = dict(information.get("I3", {}))
    evidence = dict(information.get("I4", {}))
    consequence = dict(information.get("I5", {}))
    actions = dict(information.get("I7", {}))
    dependencies = dict(information.get("I8", {}))
    uncertainty = dict(information.get("I10", {}))
    requested = authority.get("requested_resource", state.get("requested_resource"))
    allowed = authority.get("allowed_resources", authority.get("scope", []))
    authority_allows = requested is None or requested in set(allowed or [])
    hard_invariant_ok = not (
        case.family == "GLOBAL_INTERACTION" or state.get("global_state_valid") is False
    )
    return {
        "canonical_state": state,
        "candidate_actions": list(actions.get("admissible_actions", [])),
        "admissible_actions": list(actions.get("admissible_actions", [])),
        "required_evidence": list(evidence.get("required", [])),
        "available_evidence": list(evidence.get("available", [])),
        "missing_evidence": list(evidence.get("missing", [])),
        "dependencies": dependencies,
        "postcondition_met": hard_invariant_ok and evidence.get("deterministic_verifier") != "FAIL",
        "hard_invariant_ok": hard_invariant_ok,
        "external_effect_status": str(evidence.get("external_effect_status", "NOT_COMMITTED")),
        "authority_allows": authority_allows,
        "irreversible": consequence.get("reversible") is False,
        "risk": consequence.get("risk", "UNKNOWN"),
        "novelty": uncertainty.get("novelty", ""),
        "boundary_exceeded": bool(uncertainty.get("boundary_exceeded", False)),
    }


def _expected_answer(case: Any) -> Any:
    expected = case.oracle.expected if isinstance(case.oracle.expected, dict) else {}
    return expected.get("answer")


def _build_messages(experiment: ClosureExperiment) -> tuple[str, str]:
    prompt = experiment.case.prompt
    context = _case_context(experiment.case)

    if experiment.arm == "INFO_MINIMUM":
        packet = render_closure_packet(
            experiment.case,
            ClosureInformationPlan(amount=ClosureAmount.MINIMUM, ordering=ClosureOrdering.SAFETY_STATE_EVIDENCE_FIRST),
        )
        prompt = f"<CLOSURE_CONTEXT>\n{packet.rendered}\n</CLOSURE_CONTEXT>\n{prompt}"
    elif experiment.arm == "INFO_FULL":
        packet = render_closure_packet(
            experiment.case,
            ClosureInformationPlan(amount=ClosureAmount.FULL, ordering=ClosureOrdering.SAFETY_STATE_EVIDENCE_FIRST),
        )
        prompt = f"<CLOSURE_CONTEXT>\n{packet.rendered}\n</CLOSURE_CONTEXT>\n{prompt}"
    elif experiment.block == "C3" and experiment.assistance_mechanism and experiment.assistance_mode:
        assistance = apply_predecision_assistance(
            experiment.assistance_mechanism,
            experiment.assistance_mode,
            context,
        )
        prompt = (
            f"<PREDECISION_ASSISTANCE mode=\"{experiment.assistance_mode.value}\">\n"
            f"{json.dumps(assistance.model_visible_additions, sort_keys=True)}\n"
            f"</PREDECISION_ASSISTANCE>\n{prompt}"
        )
    elif experiment.arm == "RECOVERY_CONTEXT":
        packet = render_closure_packet(
            experiment.case,
            ClosureInformationPlan(amount=ClosureAmount.MINIMUM, ordering=ClosureOrdering.SAFETY_STATE_EVIDENCE_FIRST),
        )
        prompt = f"<RECOVERY_CONTEXT>\n{packet.rendered}\n</RECOVERY_CONTEXT>\n{prompt}"
    elif experiment.arm == "SEALED_SUPPORTED":
        packet = render_closure_packet(
            experiment.case,
            ClosureInformationPlan(amount=ClosureAmount.MINIMUM, ordering=ClosureOrdering.SAFETY_STATE_EVIDENCE_FIRST),
        )
        additions: dict[str, Any] = {}
        for mechanism in ("A1", "A2", "A3", "A4"):
            support = apply_predecision_assistance(mechanism, AssistanceMode.TARGET, context)
            additions.update(support.model_visible_additions)
        prompt = (
            f"<CLOSURE_CONTEXT>\n{packet.rendered}\n</CLOSURE_CONTEXT>\n"
            f"<PREDECISION_ASSISTANCE>\n{json.dumps(additions, sort_keys=True)}\n</PREDECISION_ASSISTANCE>\n"
            f"{prompt}"
        )
    return _BASE_SYSTEM, prompt


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), sort_keys=True) + "\n")


def _existing_completed(root: Path) -> tuple[int, set[str]]:
    ledger = root / "closure_call_ledger.jsonl"
    if not ledger.exists():
        return 0, set()
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    return len(rows), {str(row.get("experiment_id")) for row in rows if row.get("experiment_id")}


class D3ClosureCampaign:
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
        self.plan = build_closure_plan(self.config)
        self.scheduler = ClosureScheduler()

    def _ensure_provenance(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        ensure_closure_output_skeleton(self.root)
        path = self.root / "closure_provenance.json"
        current = {
            "protocol": "D3-CLOSURE-v2",
            "config_hash": stable_hash(self.config),
            "blind_retries_allowed": False,
        }
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing.get("config_hash") != current["config_hash"]:
                raise ValueError("closure provenance/config mismatch; refuse unsafe resume")
        else:
            path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def run_model_free(self) -> ClosureCampaignResult:
        self._ensure_provenance()
        progress = InPlaceProgress(stream=self.progress_stream, min_interval_s=0.0)
        progress.update(
            completed=0,
            total=max(1, self.plan.planned_physical_calls),
            current="D3-Closure v2 model-free",
            calls_used=0,
            calls_available=self.plan.max_calls,
            force=True,
        )
        progress.finish()
        result = ClosureCampaignResult(0, "MODEL_FREE_COMPLETE", self.plan.planned_physical_calls)
        finalize_closure_package(
            self.root,
            plan=self.plan,
            config=self.config,
            physical_calls=0,
            final_state=result.final_state,
            model_free=True,
        )
        return result

    def run(self, *, max_calls: int | None = None) -> ClosureCampaignResult:
        self._ensure_provenance()
        if not self.adapters:
            raise ValueError("real D3-Closure run requires model adapters")
        missing_models = set(self.config["models"]) - set(self.adapters)
        if missing_models:
            raise ValueError(f"closure adapters missing model keys: {sorted(missing_models)}")

        limit = int(self.plan.max_calls if max_calls is None else max_calls)
        if not 0 <= limit <= self.plan.max_calls:
            raise ValueError("closure max_calls exceeds frozen 200-call ceiling")

        existing_calls, completed = _existing_completed(self.root)
        if existing_calls > limit:
            raise ValueError("existing closure calls exceed requested resume ceiling")
        calls_used = existing_calls
        outcomes_by_arm: dict[str, list[float]] = {}
        progress = InPlaceProgress(
            stream=self.progress_stream,
            min_interval_s=0.0,
            initial_completed=existing_calls,
        )
        total_committed = min(limit, self.plan.planned_physical_calls)
        progress.update(
            completed=calls_used,
            total=max(1, total_committed),
            current="D3-Closure v2",
            calls_used=calls_used,
            calls_available=self.plan.max_calls,
            force=True,
        )

        for experiment in self.plan.experiments:
            if calls_used >= limit:
                break
            if experiment.experiment_id in completed:
                continue
            if "EXPERIMENT" not in self.scheduler.allowed_kinds(experiment.arm):
                continue

            adapter = self.adapters[experiment.model_key]
            system, prompt = _build_messages(experiment)
            call_id = f"closure-call-{uuid.uuid4().hex}"
            raw_request = {
                "physical_model_call_id": call_id,
                "experiment_id": experiment.experiment_id,
                "block": experiment.block,
                "case_id": experiment.case.case_id,
                "arm": experiment.arm,
                "model_key": experiment.model_key,
                "model_id": str(getattr(adapter, "model_id", "unknown")),
                "system": system,
                "prompt": prompt,
                "generation_options": dict(getattr(adapter, "generation_options", {}) or {}),
            }
            _append_jsonl(self.root / "closure_raw_model_requests.jsonl", raw_request)

            try:
                response = adapter.complete(prompt, system=system)
                final_text = response.text
                raw_payload = dict(response.raw)
                done_reason = raw_payload.get("done_reason")
                num_ctx = int((getattr(adapter, "generation_options", {}) or {}).get("num_ctx", 4096))
                completion = classify_completion(
                    done_reason=done_reason,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    num_ctx=num_ctx,
                    final_text=final_text,
                )
                semantic = score_semantic_action(final_text, expected_answer=_expected_answer(experiment.case))
                context = _case_context(experiment.case)
                compiled = compile_system_disposition(
                    SystemSemantics(
                        missing_required_evidence=bool(context["missing_evidence"]),
                        external_effect_status=str(context["external_effect_status"]),
                        hard_invariant_ok=bool(context["hard_invariant_ok"]),
                    )
                )
                disposition_correct = compiled is experiment.case.expected_disposition
                verified = (
                    completion is CompletionClass.SEMANTIC_RESULT
                    and semantic.semantic_action_correct
                    and disposition_correct
                )
                normalized = {
                    "physical_model_call_id": call_id,
                    "experiment_id": experiment.experiment_id,
                    "block": experiment.block,
                    "case_id": experiment.case.case_id,
                    "family": experiment.case.family,
                    "arm": experiment.arm,
                    "model_key": experiment.model_key,
                    "model_id": response.model,
                    "completion_class": completion.value,
                    "parseable_json": semantic.parseable_json,
                    "format_valid": semantic.format_valid,
                    "semantic_action_correct": semantic.semantic_action_correct,
                    "compiled_disposition": compiled.value,
                    "compiled_disposition_correct": disposition_correct,
                    "verified_outcome_correct": verified,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "latency_ms": response.latency_ms,
                }
                raw_response = {
                    "physical_model_call_id": call_id,
                    "experiment_id": experiment.experiment_id,
                    "text": final_text,
                    "payload": raw_payload,
                }
                runtime = {
                    "physical_model_call_id": call_id,
                    "model": response.model,
                    "done_reason": done_reason,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "latency_ms": response.latency_ms,
                    "completion_class": completion.value,
                }
            except Exception as exc:  # exactly one attempt; failure becomes evidence
                verified = False
                normalized = {
                    "physical_model_call_id": call_id,
                    "experiment_id": experiment.experiment_id,
                    "block": experiment.block,
                    "case_id": experiment.case.case_id,
                    "family": experiment.case.family,
                    "arm": experiment.arm,
                    "model_key": experiment.model_key,
                    "model_id": str(getattr(adapter, "model_id", "unknown")),
                    "completion_class": "INFRASTRUCTURE_OR_ADAPTER",
                    "parseable_json": False,
                    "format_valid": False,
                    "semantic_action_correct": False,
                    "compiled_disposition_correct": False,
                    "verified_outcome_correct": False,
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
                    "completion_class": "INFRASTRUCTURE_OR_ADAPTER",
                    "error_type": type(exc).__name__,
                }

            _append_jsonl(self.root / "closure_raw_model_responses.jsonl", raw_response)
            _append_jsonl(self.root / "closure_normalized_model_calls.jsonl", normalized)
            _append_jsonl(self.root / "closure_runtime_telemetry.jsonl", runtime)
            _append_jsonl(
                self.root / "closure_call_ledger.jsonl",
                {
                    "physical_model_call_id": call_id,
                    "experiment_id": experiment.experiment_id,
                    "attempt": 1,
                    "committed": True,
                },
            )
            _append_jsonl(
                self.root / "closure_system_events.jsonl",
                {
                    "event_id": f"closure-event-{uuid.uuid4().hex}",
                    "physical_model_call_id": call_id,
                    "experiment_id": experiment.experiment_id,
                    "case_id": experiment.case.case_id,
                    "event_type": "VERIFIED_OUTCOME",
                    "verified_outcome_correct": bool(verified),
                },
            )
            calls_used += 1
            completed.add(experiment.experiment_id)

            values = outcomes_by_arm.setdefault(experiment.arm, [])
            values.append(1.0 if verified else -1.0)
            if len(values) >= 4:
                evidence = sequential_evidence(values, margin=0.0)
                decision = ClosureDecision(evidence.decision.value)
                self.scheduler.observe(experiment.arm, decision)
                _append_jsonl(
                    self.root / "closure_sequential_decisions.jsonl",
                    {
                        "mechanism_id": experiment.arm,
                        "n": evidence.interval.n,
                        "mean": evidence.interval.mean,
                        "lower": evidence.interval.lower,
                        "upper": evidence.interval.upper,
                        "decision": decision.value,
                        "method": evidence.interval.method,
                    },
                )

            progress.update(
                completed=min(calls_used, total_committed),
                total=max(1, total_committed),
                current=f"{experiment.block} {experiment.model_key} {experiment.arm}",
                calls_used=calls_used,
                calls_available=self.plan.max_calls,
                force=True,
            )

        progress.finish()
        if calls_used >= limit and limit < self.plan.planned_physical_calls:
            state = "EVIDENCE_CEILING_REACHED"
        else:
            state = "COMPLETE"
        result = ClosureCampaignResult(calls_used, state, self.plan.planned_physical_calls)
        finalize_closure_package(
            self.root,
            plan=self.plan,
            config=self.config,
            physical_calls=calls_used,
            final_state=state,
            model_free=False,
        )
        return result
