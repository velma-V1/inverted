from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .test3_s0_types import (
    ActionRecord,
    EvidenceState,
    FeatureProvenance,
    OutcomeRecord,
    TransitionRecord,
)


@dataclass
class NormalizationResult:
    transitions: list[TransitionRecord] = field(default_factory=list)
    coverage: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    comparisons: list[dict[str, Any]] = field(default_factory=list)
    metadata_records: list[dict[str, Any]] = field(default_factory=list)
    source_file_inventory: list[dict[str, Any]] = field(default_factory=list)
    unknown_fields: list[dict[str, Any]] = field(default_factory=list)


def _canonical_hash(row: dict[str, Any]) -> str:
    encoded = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _first(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return default


def _to_int(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any, default: bool | None = None) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "pass", "passed", "success"}:
        return True
    if text in {"false", "0", "no", "fail", "failed"}:
        return False
    return default


def _tuple_strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value)
    return (str(value),)


def _feature_provenance(row: dict[str, Any], step: int | None) -> tuple[FeatureProvenance, ...]:
    mappings = {
        "task_family": ("family", "task_family"),
        "complexity": ("complexity", "level"),
        "representation": ("representation",),
        "candidate_status": ("candidate_status", "before_candidate_status"),
        "prior_model": ("prior_model", "model"),
        "prior_role": ("prior_role", "role"),
        "prior_attempts": ("prior_attempts", "attempt", "candidate_index"),
        "failure_signature": ("failure_signature", "before_failure_signature"),
        "failure_class": ("failure_class", "fault", "error_class"),
        "deterministic_result": ("before_deterministic_result", "deterministic_result"),
        "semantic_result": ("before_semantic_result", "semantic_result"),
        "retrieved_experience": ("retrieved_experience", "memory_hits"),
    }
    out: list[FeatureProvenance] = []
    explicit = row.get("feature_provenance")
    explicit_by_name: dict[str, dict[str, Any]] = {}
    if isinstance(explicit, list):
        for item in explicit:
            if isinstance(item, dict) and item.get("feature_name"):
                explicit_by_name[str(item["feature_name"])] = item
    for feature_name, keys in mappings.items():
        source = next((key for key in keys if key in row and row[key] is not None), None)
        if source is None:
            continue
        supplied = explicit_by_name.get(feature_name, {})
        post_dep = supplied.get("contains_post_action_dependency")
        available = supplied.get("available_before_action", True)
        dependencies = supplied.get("depends_on") or ()
        out.append(FeatureProvenance(
            feature_name=feature_name,
            observed_at_transition=_to_int(supplied.get("observed_at_transition"), step),
            derived_at_transition=_to_int(supplied.get("derived_at_transition"), step),
            observed_at_timestamp=supplied.get("observed_at_timestamp"),
            derived_at_timestamp=supplied.get("derived_at_timestamp"),
            source_event_ids=_tuple_strings(supplied.get("source_event_ids")),
            depends_on=_tuple_strings(dependencies),
            available_before_action=_to_bool(available, None),
            contains_post_action_dependency=_to_bool(post_dep, False) if post_dep is not None else False,
            source_field=source,
            derivation=supplied.get("derivation") or "direct_historical_field",
            metadata={
                "availability_basis": supplied.get("availability_basis", "historical_record_position"),
                **({"raw": supplied} if supplied else {}),
            },
        ))
    return tuple(out)


def _state(source_id: str, row: dict[str, Any]) -> EvidenceState:
    task_id = str(_first(row, "case_id", "task_id", "trial_id", "id", default=""))
    if not task_id:
        raise ValueError("record is missing task identity")
    step = _to_int(_first(row, "step", "transition_index", "attempt"))
    before_success = _to_bool(_first(row, "before_success"), None)
    deterministic = _first(row, "before_deterministic_result", "deterministic_result")
    if deterministic is None and before_success is not None:
        deterministic = "PASS" if before_success else "FAIL"
    return EvidenceState(
        task_id=task_id,
        task_family=_first(row, "family", "task_family"),
        causal_twin_id=_first(row, "causal_twin_id", "twin_id", "paired_task_id"),
        holdout_id=_first(row, "holdout_id", "holdout"),
        split=_first(row, "split", "dataset_split"),
        complexity=_to_float(_first(row, "complexity", "level")),
        representation=_first(row, "representation"),
        requirements=_tuple_strings(_first(row, "requirements", "requirement_ids")),
        candidate_status=_first(row, "candidate_status", "before_candidate_status"),
        prior_model=_first(row, "prior_model", "model"),
        prior_role=_first(row, "prior_role", "role"),
        prior_attempts=_to_int(_first(row, "prior_attempts", "attempt", "candidate_index"), 0) or 0,
        failure_signature=_first(row, "failure_signature", "before_failure_signature"),
        failure_class=_first(row, "failure_class", "fault", "error_class"),
        deterministic_result=deterministic,
        semantic_result=_first(row, "before_semantic_result", "semantic_result"),
        semantic_deterministic_disagreement=_to_bool(_first(row, "semantic_deterministic_disagreement"), None),
        verifier_results=tuple(item for item in (_first(row, "verifier_results", default=[]) or []) if isinstance(item, dict)),
        retrieved_experience=_tuple_strings(_first(row, "retrieved_experience", "memory_hits")),
        physical_calls_spent=_to_int(_first(row, "physical_calls_spent", "physical_calls"), 0) or 0,
        logical_calls_spent=_to_int(_first(row, "logical_calls_spent", "logical_calls")),
        tokens_spent=_to_int(_first(row, "tokens_spent", "total_tokens", "tokens")),
        prompt_tokens_spent=_to_int(_first(row, "prompt_tokens_spent", "prompt_tokens")),
        completion_tokens_spent=_to_int(_first(row, "completion_tokens_spent", "completion_tokens")),
        elapsed_ms=_to_float(_first(row, "elapsed_ms", "latency_ms")),
        cache_hits=_to_int(_first(row, "cache_hits")),
        cache_misses=_to_int(_first(row, "cache_misses")),
        feature_provenance=_feature_provenance(row, step),
        metadata={"source_id": source_id, "raw_state_fields": dict(row)},
    )


def _action(row: dict[str, Any], default_component: str | None = None) -> ActionRecord:
    component = str(_first(row, "component", "action", "phase", "pipeline", default=default_component or "unknown"))
    model = _first(row, "model", "selected_model")
    return ActionRecord(
        component=component,
        model=model,
        role=_first(row, "role", "model_role"),
        verifier=_first(row, "verifier", "validator", "verifier_type"),
        operation=_first(row, "operation", "transition", "repair_operation"),
        retry_kind=_first(row, "retry_kind"),
        repair_kind=_first(row, "repair_kind"),
        changes_model_input=bool(_to_bool(_first(row, "changes_model_input"), False)),
        produces_new_model_output=bool(_to_bool(_first(row, "produces_new_model_output"), bool(model))),
        prompt_fingerprint=_first(row, "prompt_fingerprint", "prompt_hash"),
        context_fingerprint=_first(row, "context_fingerprint", "context_hash"),
        selected_by=_first(row, "selected_by", "router"),
        selection_reason=_first(row, "selection_reason", "routing_reason"),
        metadata={"raw_action_fields": dict(row)},
    )


def _outcome(row: dict[str, Any]) -> OutcomeRecord:
    after_success = _to_bool(_first(row, "after_success", "success"), None)
    deterministic = _first(row, "after_deterministic_result", "deterministic_result")
    if deterministic is None and after_success is not None:
        deterministic = "PASS" if after_success else "FAIL"
    validators = _first(row, "verifier_results", "validator_results", default=[])
    validator_rows = [item for item in validators if isinstance(item, dict)] if isinstance(validators, list) else []
    distinct_results = {str(item.get("result")) for item in validator_rows if item.get("result") is not None}
    return OutcomeRecord(
        deterministic_result=deterministic,
        semantic_result=_first(row, "after_semantic_result", "semantic_result"),
        hidden_gold_result=_first(row, "hidden_gold_result", "gold_result"),
        success=after_success,
        catastrophic=_to_bool(_first(row, "catastrophic", "after_catastrophic"), None),
        blocked=_to_bool(_first(row, "after_blocked", "blocked"), None),
        failure_signature=_first(row, "after_failure_signature", "failure_signature"),
        failure_class=_first(row, "after_failure_class", "failure_class", "fault", "error_class"),
        physical_calls_delta=_to_int(_first(row, "physical_calls_delta"), 0) or 0,
        logical_calls_delta=_to_int(_first(row, "logical_calls_delta")),
        tokens_delta=_to_int(_first(row, "tokens_delta", "total_tokens")),
        prompt_tokens_delta=_to_int(_first(row, "prompt_tokens_delta", "prompt_tokens")),
        completion_tokens_delta=_to_int(_first(row, "completion_tokens_delta", "completion_tokens")),
        elapsed_ms_delta=_to_float(_first(row, "elapsed_ms_delta", "elapsed_ms", "latency_ms")),
        cache_hit=_to_bool(_first(row, "cache_hit"), None),
        validator_count=len(validator_rows) if validator_rows else None,
        validator_disagreements=max(0, len(distinct_results) - 1) if validator_rows else None,
        metadata={"raw_outcome_fields": dict(row)},
    )


def _transition(source_id: str, row: dict[str, Any], default_component: str | None, record_type: str) -> TransitionRecord:
    state = _state(source_id, row)
    step = _to_int(_first(row, "step", "transition_index", "attempt"))
    return TransitionRecord(
        transition_id=str(_first(row, "transition_id", "event_id", "call_identity", default=f"{source_id}:{record_type}:{_canonical_hash(row)[:16]}")),
        source_id=source_id,
        state_before=state,
        action=_action(row, default_component),
        state_after=_outcome(row),
        observed=True,
        transition_index=step,
        event_timestamp=_first(row, "timestamp", "created_at", "event_timestamp"),
        source_record_type=record_type,
        raw_record_hash=_canonical_hash(row),
        provenance={
            "source_id": source_id,
            "record_type": record_type,
            "raw_record_hash": _canonical_hash(row),
        },
        anomalies=_tuple_strings(_first(row, "anomalies")),
        metadata={"raw_record": dict(row)},
    )


def normalize_test2_event(source_id: str, row: dict[str, Any]) -> TransitionRecord:
    return _transition(source_id, row, "event", "events.jsonl")


def normalize_test2_trial(source_id: str, row: dict[str, Any]) -> TransitionRecord:
    return _transition(source_id, row, "trial", "trials")


def normalize_test2_tier_a_record(source_id: str, row: dict[str, Any]) -> TransitionRecord:
    payload = dict(row)
    payload.setdefault("component", _first(row, "phase", "role", default="tier_a_model_call"))
    payload.setdefault("produces_new_model_output", True)
    return _transition(source_id, payload, "tier_a_model_call", "model_calls.jsonl")


def normalize_test1_record(source_id: str, row: dict[str, Any]) -> TransitionRecord:
    return _transition(source_id, row, "test1", "test1")


def _read_jsonl(path: Path, on_error: Callable[[dict[str, Any]], None]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            raw = line.rstrip("\n")
            if not raw.strip():
                continue
            try:
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise ValueError("JSONL row is not an object")
                rows.append(value)
            except (json.JSONDecodeError, ValueError) as exc:
                on_error({"line": line_no, "error": str(exc), "raw": raw})
    return rows


def _read_csv(path: Path, on_error: Callable[[dict[str, Any]], None]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            for row_no, row in enumerate(csv.DictReader(handle), start=2):
                rows.append(dict(row))
    except (csv.Error, UnicodeDecodeError, OSError) as exc:
        on_error({"line": None, "error": str(exc), "raw": None})
    return rows


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pick_existing(root: Path, candidates: tuple[str, ...]) -> Path | None:
    return next((root / rel for rel in candidates if (root / rel).is_file()), None)


def normalize_bundle(source_id: str, source_class: str, bundle: str | Path) -> NormalizationResult:
    root = Path(bundle)
    result = NormalizationResult()
    if not root.exists() or not root.is_dir():
        result.errors.append({"source_id": source_id, "record_type": "bundle", "line": None, "error": "bundle missing", "raw": None})
        return result

    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        result.source_file_inventory.append({
            "source_id": source_id,
            "path": rel,
            "bytes": path.stat().st_size,
            "sha256": _file_sha(path),
            "suffix": path.suffix.lower(),
        })

    seen_paths: set[Path] = set()
    specs: list[tuple[Path | None, str, Callable[[str, dict[str, Any]], TransitionRecord]]] = [
        (_pick_existing(root, ("events.jsonl", "raw/every-event.jsonl")), "events.jsonl", normalize_test2_event if source_class != "test1" else normalize_test1_record),
        (_pick_existing(root, ("trials.csv", "trials.jsonl", "raw/every-trial.jsonl")), "trials", normalize_test2_trial if source_class != "test1" else normalize_test1_record),
    ]
    if source_class == "test2_tier_a":
        specs.append((_pick_existing(root, ("model_calls.jsonl", "raw/every-model-call.jsonl")), "model_calls.jsonl", normalize_test2_tier_a_record))

    for path, record_type, adapter in specs:
        if path is None:
            continue
        seen_paths.add(path.resolve())
        local_errors: list[dict[str, Any]] = []
        if path.suffix.lower() == ".csv":
            rows = _read_csv(path, local_errors.append)
        else:
            rows = _read_jsonl(path, local_errors.append)
        normalized = 0
        for index, row in enumerate(rows, start=1):
            try:
                result.transitions.append(adapter(source_id, row))
                normalized += 1
            except Exception as exc:  # normalization errors are evidence, never silently coerced
                local_errors.append({"line": index, "error": f"{type(exc).__name__}: {exc}", "raw": json.dumps(row, sort_keys=True, default=str)})
        for error in local_errors:
            result.errors.append({"source_id": source_id, "record_type": record_type, "path": path.relative_to(root).as_posix(), **error})
        result.coverage.append({
            "source_id": source_id,
            "record_type": record_type,
            "path": path.relative_to(root).as_posix(),
            "input_rows": len(rows) + sum(1 for e in local_errors if e.get("raw") is not None and str(e.get("raw", "")).startswith("{bad")),
            "normalized_rows": normalized,
            "dropped_rows": len(local_errors),
            "unknown_fields": [],
            "errors": [e.get("error") for e in local_errors],
        })

    # Preserve all remaining tabular evidence as comparison evidence rather than
    # fabricating transitions. This includes effect matrices, order rankings,
    # router data, thresholds, failures, costs, and future unknown CSV outputs.
    for path in sorted(root.rglob("*.csv")):
        if path.resolve() in seen_paths or path.name == "SHA256SUMS.csv":
            continue
        local_errors: list[dict[str, Any]] = []
        rows = _read_csv(path, local_errors.append)
        rel = path.relative_to(root).as_posix()
        for row in rows:
            result.comparisons.append({"source_id": source_id, "source_file": rel, "record_type": "comparison_csv", **row})
        for error in local_errors:
            result.errors.append({"source_id": source_id, "record_type": "comparison_csv", "path": rel, **error})
        result.coverage.append({
            "source_id": source_id,
            "record_type": "comparison_csv",
            "path": rel,
            "input_rows": len(rows),
            "normalized_rows": 0,
            "comparison_rows": len(rows),
            "dropped_rows": len(local_errors),
            "unknown_fields": sorted({key for row in rows for key in row}),
            "errors": [e.get("error") for e in local_errors],
        })

    # JSON metadata is retained verbatim. Unknown schemas remain metadata rather
    # than being discarded or guessed into a transition shape.
    for path in sorted(root.rglob("*.json")):
        rel = path.relative_to(root).as_posix()
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            result.metadata_records.append({"source_id": source_id, "source_file": rel, "value": value})
            result.coverage.append({
                "source_id": source_id,
                "record_type": "metadata_json",
                "path": rel,
                "input_rows": 1,
                "normalized_rows": 0,
                "metadata_rows": 1,
                "dropped_rows": 0,
                "unknown_fields": sorted(value.keys()) if isinstance(value, dict) else [],
                "errors": [],
            })
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            result.errors.append({"source_id": source_id, "record_type": "metadata_json", "path": rel, "line": None, "error": str(exc), "raw": None})

    return result
