"""Public compatibility surface plus fail-closed Test-2 runtime hardening.

The bulk campaign remains in ``test2_local_hardened``. This module adds the
small number of experiment-boundary guarantees that must survive refactors:
zero-inference identity preflight, a disjoint/condition-balanced repair-model
selection split, explicit failed-call evidence, uncached primary repair cells,
and key-based validator lineage.
"""

from __future__ import annotations

from typing import Any

from . import test2_local_hardened as _hardened
from .models import ModelCallError
from .test2_integrity import attach_repair_validator_outcomes
from .test2_local_hardened import *  # noqa: F401,F403
from .test2_local_hardened import LOCAL_PHASE_LIMITS, LocalTest2Plan
from .test2_provenance import collect_ollama_provenance


_SCREEN_CONDITIONS = (
    ("raw", "regenerate"),
    ("raw", "targeted"),
    ("structured", "regenerate"),
    ("structured", "targeted"),
)
_PRIMARY_SUFFIXES = tuple(
    f"-{feedback}-{strategy}"
    for feedback in ("raw", "structured")
    for strategy in ("regenerate", "targeted")
)


class BoundedModelCaller(_hardened.BoundedModelCaller):
    """Bounded caller that preserves failed physical calls as failed evidence.

    Adapter transport retries remain disabled. A failed request therefore
    consumes exactly one physical-call slot, is never cached, and returns an
    empty completion so the fixed experimental cell is scored as a failure
    rather than disappearing or aborting the remaining campaign.
    """

    def complete(
        self,
        model: Any,
        messages: list[dict[str, str]],
        *,
        role: str,
        context: dict[str, Any],
        response_schema: Any = None,
        allow_cache: bool = True,
    ) -> BoundedCompletion:
        trial_id = str(context.get("trial_id") or "")
        if role == "repairer" and (trial_id.endswith("-screen") or trial_id.endswith(_PRIMARY_SUFFIXES)):
            allow_cache = False
        try:
            return super().complete(
                model,
                messages,
                role=role,
                context=context,
                response_schema=response_schema,
                allow_cache=allow_cache,
            )
        except ModelCallError as exc:
            # ``super`` has already consumed exactly one physical budget slot.
            identity = _hardened.CallIdentity.build(
                model=str(getattr(model, "model", "unknown")),
                role=role,
                messages=messages,
                settings=self._settings(model),
                response_schema=response_schema,
            ).digest
            item = BoundedCompletion(
                text="",
                record=exc.record,
                identity=identity,
                cache_hit=False,
                prompt=messages,
                response="",
                logical_index=len(self.calls) + 1,
                physical_call_number=self.budget.physical_calls,
            )
            self.calls.append(item)
            return item


class _PartitionedRepairBank(list):
    """Expose the frozen ten failures as 4 screen-only + 6 primary-only cases.

    The legacy core asks for ``[:5]`` and ``[:6]``. Returning the preregistered
    partitions here lets us harden the experiment without duplicating the large
    stable campaign implementation. All ordinary iteration/indexing remains a
    normal ten-item list.
    """

    def __getitem__(self, key):
        if isinstance(key, slice) and key.start is None and key.step is None:
            if key.stop == 5:
                return list.__getitem__(self, slice(0, 4))
            if key.stop == 6:
                return list.__getitem__(self, slice(4, 10))
        return list.__getitem__(self, key)


def build_local_plan() -> LocalTest2Plan:
    """Report the frozen 480-call reservation, not optimistic realized use."""
    total = sum(LOCAL_PHASE_LIMITS.values())
    if total != 480:
        raise AssertionError(f"local Test-2 phase reservations must sum to 480, got {total}")
    return LocalTest2Plan(planned_max_physical_calls=480)


def _ollama_context(models) -> tuple[str, tuple[str, ...]] | None:
    model_list = list(models)
    if not model_list or any(str(getattr(model, "provider", "")) != "ollama" for model in model_list):
        return None
    base_urls = {str(getattr(model, "base_url", "")).rstrip("/") for model in model_list}
    if len(base_urls) != 1 or not next(iter(base_urls)):
        raise AssertionError("all Test-2 Ollama adapters must use one explicit base_url")
    return next(iter(base_urls)), tuple(str(getattr(model, "model", "")) for model in model_list)


def _validate_identity_snapshot(snapshot: dict[str, Any], model_names: tuple[str, ...]) -> None:
    if not str(snapshot.get("server_version") or "").strip():
        raise AssertionError("Ollama provenance identity preflight missing server_version")
    rows = snapshot.get("models")
    if not isinstance(rows, dict) or set(rows) != set(model_names):
        raise AssertionError("Ollama provenance identity preflight does not contain exactly the requested models")
    for model in model_names:
        row = rows.get(model) or {}
        if str(row.get("requested_name") or "") != model:
            raise AssertionError(f"Ollama provenance identity mismatch for requested model {model}")
        if str(row.get("tag_name") or "") != model:
            raise AssertionError(f"Ollama provenance identity tag mismatch for {model}")
        if not str(row.get("tag_digest") or "").strip():
            raise AssertionError(f"Ollama provenance digest missing for {model}")
        if not str(row.get("show_payload_sha256") or "").strip():
            raise AssertionError(f"Ollama provenance /api/show identity digest missing for {model}")


def _identity_projection(snapshot: dict, model_names: tuple[str, ...]) -> dict:
    rows = snapshot.get("models") or {}
    return {
        "server_version": snapshot.get("server_version"),
        "models": {
            model: {
                "requested_name": (rows.get(model) or {}).get("requested_name"),
                "tag_name": (rows.get(model) or {}).get("tag_name"),
                "tag_digest": (rows.get(model) or {}).get("tag_digest"),
                "tag_size": (rows.get(model) or {}).get("tag_size"),
                "tag_details": (rows.get(model) or {}).get("tag_details"),
                "show_details": (rows.get(model) or {}).get("show_details"),
                "template_sha256": (rows.get(model) or {}).get("template_sha256"),
                "system_sha256": (rows.get(model) or {}).get("system_sha256"),
                "show_payload_sha256": (rows.get(model) or {}).get("show_payload_sha256"),
            }
            for model in model_names
        },
    }


def run_local_campaign(models, run_id: str = "test2-local", hard_limit: int = 480):
    """Run the fixed Test-2 campaign with fail-closed experiment boundaries."""
    model_list = list(models)
    if hard_limit != 480:
        raise ValueError("decisive Test-2 local campaign hard_limit must be exactly 480")

    ollama = _ollama_context(model_list)
    before = None
    if ollama is not None:
        base_url, model_names = ollama
        if model_names != LOCAL_MODELS:
            raise ValueError(f"decisive Test-2 Ollama models must be exactly {LOCAL_MODELS!r}")
        before = collect_ollama_provenance(base_url, model_names)
        _validate_identity_snapshot(before, model_names)  # before any inference

    original_caller = _hardened.BoundedModelCaller
    original_bank_builder = _hardened.build_repair_candidate_bank
    original_repair = _hardened._repair
    original_validator = _hardened._validator_row
    original_call_row = _hardened._call_row

    screen_condition_by_case: dict[str, tuple[str, str]] = {}
    primary_completion: dict[tuple[str, str, str, str], BoundedCompletion] = {}
    repair_candidate_lineage: dict[str, dict[str, str]] = {}
    pending_primary_lineage: dict[str, str] | None = None

    def partitioned_bank_builder():
        bank = list(original_bank_builder())
        if len(bank) != 10:
            raise AssertionError(f"frozen repair bank must contain exactly 10 cases, got {len(bank)}")
        for case, condition in zip(bank[:4], _SCREEN_CONDITIONS):
            screen_condition_by_case[str(case.case_id)] = condition
        return _PartitionedRepairBank(bank)

    def call_row_hook(completion, *, phase, task_id, model, role, pipeline=None):
        row = original_call_row(
            completion,
            phase=phase,
            task_id=task_id,
            model=model,
            role=role,
            pipeline=pipeline,
        )
        telemetry = dict(row.get("telemetry") or {})
        telemetry["logical_call_index"] = completion.logical_index
        telemetry["physical_call_number"] = completion.physical_call_number
        row["telemetry"] = telemetry
        return row

    def repair_hook(*args, **kwargs):
        nonlocal pending_primary_lineage
        trial_id = str(kwargs.get("trial_id") or "")
        phase = str(kwargs.get("phase") or "")
        model_name = str(getattr(kwargs.get("model"), "model", ""))
        feedback = str(kwargs.get("feedback_style") or "structured")
        strategy = str(kwargs.get("strategy") or "targeted")
        case_id: str | None = None

        if phase == "repair_factorial" and trial_id.endswith("-screen"):
            case_id = trial_id[: -len("-screen")]
            try:
                feedback, strategy = screen_condition_by_case[case_id]
            except KeyError as exc:
                raise AssertionError(f"repair screen case {case_id!r} is outside the frozen selection partition") from exc
            kwargs["feedback_style"] = feedback
            kwargs["strategy"] = strategy
        elif phase == "repair_factorial":
            suffix = f"-{feedback}-{strategy}"
            if trial_id.endswith(suffix):
                case_id = trial_id[: -len(suffix)]

        candidate, completion = original_repair(*args, **kwargs)
        if phase == "repair_factorial" and case_id is not None and not trial_id.endswith("-screen"):
            key = (model_name, case_id, feedback, strategy)
            if key in primary_completion:
                raise AssertionError(f"duplicate primary repair inference cell {key!r}")
            primary_completion[key] = completion
            pending_primary_lineage = {
                "model": model_name,
                "task_id": case_id,
                "feedback_style": feedback,
                "strategy": strategy,
            }
            if candidate is not None:
                repair_candidate_lineage[str(candidate.id)] = dict(pending_primary_lineage)
        return candidate, completion

    def validator_hook(task, candidate, *, phase, task_id, stage, pipeline=None):
        nonlocal pending_primary_lineage
        row = original_validator(task, candidate, phase=phase, task_id=task_id, stage=stage, pipeline=pipeline)
        if phase == "repair_factorial" and str(stage).startswith("repair_"):
            lineage = repair_candidate_lineage.get(str(getattr(candidate, "id", ""))) if candidate is not None else None
            lineage = lineage or pending_primary_lineage
            if not lineage:
                raise AssertionError("repair-factorial validator has no model/condition lineage")
            expected_stage = f"repair_{lineage['feedback_style']}_{lineage['strategy']}"
            if str(task_id) != lineage["task_id"] or str(stage) != expected_stage:
                raise AssertionError("repair-factorial validator lineage does not match the immediately preceding repair cell")
            row["model"] = lineage["model"]
            row["evaluation_id"] = _hardened._evaluation_id(
                "repair_factorial",
                "repairer",
                str(task_id),
                feedback_style=lineage["feedback_style"],
                strategy=lineage["strategy"],
            )
            pending_primary_lineage = None
        return row

    _hardened.BoundedModelCaller = BoundedModelCaller
    _hardened.build_repair_candidate_bank = partitioned_bank_builder
    _hardened._repair = repair_hook
    _hardened._validator_row = validator_hook
    _hardened._call_row = call_row_hook
    try:
        result = _hardened.run_local_campaign(model_list, run_id=run_id, hard_limit=hard_limit)
    finally:
        _hardened.BoundedModelCaller = original_caller
        _hardened.build_repair_candidate_bank = original_bank_builder
        _hardened._repair = original_repair
        _hardened._validator_row = original_validator
        _hardened._call_row = original_call_row

    # Correct the legacy screen-row labels to the actual balanced conditions.
    screen_rows = [row for row in result.get("records", []) if row.get("phase") == "repair_screen"]
    for row in screen_rows:
        case_id = str(row.get("task_id") or "")
        feedback, strategy = screen_condition_by_case[case_id]
        row["feedback_style"] = feedback
        row["strategy"] = strategy
        row["evaluation_id"] = _hardened._evaluation_id(
            "repair_screen", "repairer", case_id, feedback_style=feedback, strategy=strategy
        )

    screen_tasks = {str(row.get("task_id")) for row in screen_rows}
    repair_rows = [row for row in result.get("records", []) if row.get("phase") == "repair_factorial"]
    primary_tasks = {str(row.get("task_id")) for row in repair_rows}
    if screen_tasks & primary_tasks:
        raise AssertionError(f"repair selection contaminated primary tasks: {sorted(screen_tasks & primary_tasks)!r}")
    for model in LOCAL_MODELS:
        model_screen = [row for row in screen_rows if str(row.get("model")) == model]
        observed = {(str(row.get("feedback_style")), str(row.get("strategy"))) for row in model_screen}
        if len(model_screen) != 4 or observed != set(_SCREEN_CONDITIONS):
            raise AssertionError(f"repair selection screen for {model} is not exactly one call per factorial condition")

    # Attach the physical-call evidence used by the primary verdict contract.
    for row in repair_rows:
        key = (
            str(row.get("model") or ""),
            str(row.get("task_id") or ""),
            str(row.get("feedback_style") or ""),
            str(row.get("strategy") or ""),
        )
        completion = primary_completion.get(key)
        if completion is None:
            raise AssertionError(f"repair-factorial trial has no model-call lineage {key!r}")
        row["call_identity"] = completion.identity
        row["cache_hit"] = bool(completion.cache_hit)
        row["physical_call_number"] = completion.physical_call_number
        record = completion.record.to_dict() if hasattr(completion.record, "to_dict") else {}
        row["call_error_class"] = record.get("error_class")
        row["call_error_message"] = record.get("error_message")
        row["call_timeout"] = bool(record.get("timeout", False))
        row["call_status_code"] = record.get("status_code")

    attach_repair_validator_outcomes(result)

    if ollama is not None:
        base_url, model_names = ollama
        try:
            after = collect_ollama_provenance(base_url, model_names)
            _validate_identity_snapshot(after, model_names)
            identity_match = _identity_projection(before or {}, model_names) == _identity_projection(after, model_names)
            result["ollama_provenance"] = {"before": before, "after": after, "identity_match": identity_match}
        except Exception as exc:
            # Do not throw away an already-paid campaign. Preserve evidence and
            # force the post-analysis verdict to INCONCLUSIVE.
            result["ollama_provenance"] = {
                "before": before,
                "after": None,
                "identity_match": False,
                "after_capture_error": f"{type(exc).__name__}: {exc}",
            }
    else:
        result["ollama_provenance"] = {"capture_skipped": True, "reason": "non-Ollama test adapter"}
    return result
