"""Append-only, recoverable evidence artifacts for the static A0 campaign."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
from numbers import Real
from pathlib import Path
from typing import Any, Mapping

from .cases import generate_hd_next2_cases
from .config import canonical_a0_planner_config
from .rendering import render_hd_next1_historical_seed, serialize_canonical_a0_request
from .stages import build_canonical_a0_plan


LEDGERS = (
    "raw_model_requests", "raw_model_responses", "rendered_layers",
    "normalized_model_calls", "runtime_telemetry", "physical_call_ledger",
    "campaign_journal", "scheduler_ledger", "coverage_events", "action_budget_state",
)
CALL_JOURNAL = "call_journal"
JOIN_KEYS = frozenset({"unit_id", "physical_call_id"})
MANUAL_LEDGERS = frozenset({"campaign_journal", "coverage_events", "action_budget_state"})
CALL_PROJECTIONS = (
    "raw_model_requests", "raw_model_responses", "rendered_layers",
    "normalized_model_calls", "runtime_telemetry", "physical_call_ledger",
    "scheduler_ledger",
)
SCHEDULE_FIELDS = (
    "case_id", "partition", "operating_region", "model_key", "treatment_kind",
    "treatment_spec_id", "treatment_spec_sha256", "replicate", "execution_position",
    "model_role", "eligible_for_recipe", "model_block", "selection_reason",
    "max_attempts", "retry_of_unit_id",
)
_CANONICAL_UNITS = {unit.unit_id: unit for unit in build_canonical_a0_plan().units}
_CANONICAL_CASES = {
    case.case_id: case
    for case in generate_hd_next2_cases("development", seed=20260921, per_region=1)
}
_HISTORICAL_SEED_INGREDIENT = "HD_NEXT_1_HISTORICAL_SEED"
_CANONICAL_MODEL_IDS = canonical_a0_planner_config()["models"]
_CALL_JOURNAL_HMAC_DOMAIN = b"INVERTED/HD-NEXT-2/A0/CALL-JOURNAL/v1\x00"


def _reject_json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _historical_seed_bytes(case: object) -> bytes:
    system, user, metadata = render_hd_next1_historical_seed(case)
    payload = {"system": system, "user": user, "metadata": metadata}
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def _normalized_answer(value: object) -> object:
    if isinstance(value, str):
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized.startswith("queue_") and len(normalized) > len("queue_"):
            normalized = normalized[len("queue_"):]
        return normalized
    return value


def derive_answer_evidence(raw_response: str, expected: object) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        candidate = json.loads(
            raw_response, object_pairs_hook=_reject_json_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return (
            {"candidate": {"unparsed": raw_response}, "normalized_answer": "UNPARSEABLE", "correctness": False},
            {"oracle_result": str(expected), "verifier_result": "FAIL", "failure_taxonomy": ["ANSWER_JSON_INVALID"]},
        )
    if not isinstance(candidate, dict) or set(candidate) != {"answer"}:
        stored = candidate if isinstance(candidate, dict) else {"value": candidate}
        answer = candidate.get("answer", "UNPARSEABLE") if isinstance(candidate, dict) else "UNPARSEABLE"
        return (
            {"candidate": stored, "normalized_answer": str(_normalized_answer(answer)), "correctness": False},
            {"oracle_result": str(expected), "verifier_result": "FAIL", "failure_taxonomy": ["ANSWER_ONLY_SCHEMA_INVALID"]},
        )
    answer = candidate["answer"]
    correct = _normalized_answer(answer) == _normalized_answer(expected)
    return (
        {"candidate": candidate, "normalized_answer": str(_normalized_answer(answer)), "correctness": correct},
        {
            "oracle_result": str(expected),
            "verifier_result": "PASS" if correct else "FAIL",
            "failure_taxonomy": [] if correct else ["ANSWER_INCORRECT"],
        },
    )


class EvidenceWriter:
    """Commit complete calls once and deterministically maintain their projections."""

    def __init__(self, root: str | Path, *, journal_secret: bytes | None = None):
        self.root = Path(root)
        if journal_secret is not None and not isinstance(journal_secret, bytes):
            raise TypeError("journal_secret must be bytes")
        self.journal_secret = journal_secret
        self.root.mkdir(parents=True, exist_ok=True)
        for ledger in (*LEDGERS, CALL_JOURNAL):
            (self.root / f"{ledger}.jsonl").touch(exist_ok=True)

    @staticmethod
    def _encoded(row: Mapping[str, Any], *, context: str = "call evidence") -> str:
        try:
            return json.dumps(
                dict(row), sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise TypeError(f"{context} must be strict JSON serializable") from exc

    def _append_encoded(self, ledger: str, encoded: str) -> None:
        with (self.root / f"{ledger}.jsonl").open("a", encoding="utf-8", newline="") as stream:
            stream.write(encoded + "\n")

    def _authenticate(self, row: Mapping[str, Any]) -> dict[str, Any]:
        unsigned = dict(row)
        signature = unsigned.pop("journal_hmac_sha256", None)
        if self.journal_secret is None:
            if signature is not None:
                raise ValueError("signed call journal requires journal_secret")
            return unsigned
        if not isinstance(signature, str):
            raise ValueError("authoritative call journal authentication is missing")
        expected = hmac.new(
            self.journal_secret,
            _CALL_JOURNAL_HMAC_DOMAIN + self._encoded(unsigned).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("authoritative call journal authentication failed")
        return unsigned

    def _signed(self, row: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(row)
        if self.journal_secret is not None:
            result["journal_hmac_sha256"] = hmac.new(
                self.journal_secret,
                _CALL_JOURNAL_HMAC_DOMAIN + self._encoded(result).encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
        return result

    def append(self, ledger: str, row: Mapping[str, Any]) -> None:
        if ledger not in LEDGERS:
            raise ValueError(f"unknown evidence ledger: {ledger}")
        if ledger not in MANUAL_LEDGERS:
            raise ValueError(f"{ledger} is call-derived; use write_call")
        if not isinstance(row, Mapping):
            raise TypeError("manual evidence row must be a mapping")
        self._append_encoded(ledger, self._encoded(row, context="manual evidence"))

    @staticmethod
    def _mapping(call: Mapping[str, Any], key: str) -> dict[str, Any]:
        value = call.get(key)
        if not isinstance(value, Mapping) or not value:
            raise ValueError(f"{key} must be a non-empty mapping")
        if JOIN_KEYS & set(value):
            raise ValueError(f"{key} cannot override reserved join keys")
        return dict(value)

    @staticmethod
    def _exact_schema(row: Mapping[str, Any], required: set[str], optional: set[str], context: str) -> None:
        keys = set(row)
        missing = required - keys
        extra = keys - (required | optional)
        if missing:
            raise ValueError(f"{context} exact schema missing: {', '.join(sorted(missing))}")
        if extra:
            raise ValueError(f"{context} does not match exact schema; unsupported: {', '.join(sorted(extra))}")

    @staticmethod
    def _required_string(row: Mapping[str, Any], field: str, context: str) -> str:
        value = row.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{context}.{field} must be a non-empty string")
        return value

    @staticmethod
    def _required_integer(row: Mapping[str, Any], field: str, context: str) -> int:
        value = row.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{context}.{field} must be a non-negative integer")
        return value

    def _prepare_call(self, call: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(call, Mapping):
            raise TypeError("call must be a mapping")
        self._exact_schema(
            call,
            {"unit_id", "physical_call_id", "model", "request", "response", "rendered_layers", "normalized", "verification", "schedule", "telemetry"},
            {"status"},
            "call",
        )
        unit_id = self._required_string(call, "unit_id", "call")
        physical_call_id = self._required_string(call, "physical_call_id", "call")
        unit = _CANONICAL_UNITS.get(unit_id)
        if unit is None:
            raise ValueError("unit_id is not in the canonical A0 schedule")

        model = self._mapping(call, "model")
        self._exact_schema(model, {"model_key", "model_id", "model_digest", "runtime_identity"}, set(), "model")
        for field in ("model_key", "model_id", "model_digest", "runtime_identity"):
            self._required_string(model, field, "model")
        if model["model_key"] != unit.model_key:
            raise ValueError("model.model_key does not match canonical A0 schedule")
        if model["model_id"] != _CANONICAL_MODEL_IDS[unit.model_key]:
            raise ValueError("model.model_id does not match canonical A0 model identity")

        request = self._mapping(call, "request")
        self._exact_schema(request, {"rendered_request_bytes", "rendered_request_sha256"}, set(), "request")
        request_bytes = request.pop("rendered_request_bytes", None)
        if not isinstance(request_bytes, bytes):
            raise TypeError("request.rendered_request_bytes must be exact bytes")
        request_hash = self._required_string(request, "rendered_request_sha256", "request")
        if request_hash != hashlib.sha256(request_bytes).hexdigest():
            raise ValueError("request.rendered_request_sha256 mismatch")
        case = _CANONICAL_CASES.get(unit.case_id)
        if case is None or request_bytes != serialize_canonical_a0_request(
            case, _CANONICAL_MODEL_IDS[unit.model_key], unit.treatment_kind,
        ):
            raise ValueError("request bytes do not match canonical A0 request")
        request["rendered_request_bytes_hex"] = request_bytes.hex()

        response = self._mapping(call, "response")
        self._exact_schema(response, {"raw_response"}, set(), "response")
        self._required_string(response, "raw_response", "response")

        case = _CANONICAL_CASES.get(unit.case_id)
        expected_answer = (
            case.oracle.expected.get("answer")
            if case is not None and isinstance(case.oracle.expected, dict)
            else case.oracle.expected if case is not None else None
        )

        normalized = self._mapping(call, "normalized")
        self._exact_schema(normalized, {"candidate", "normalized_answer", "correctness"}, set(), "normalized")
        if "candidate" not in normalized or normalized["candidate"] is None:
            raise ValueError("normalized.candidate is required")
        self._required_string(normalized, "normalized_answer", "normalized")
        if not isinstance(normalized.get("correctness"), bool):
            raise ValueError("normalized.correctness must be boolean")

        verification = self._mapping(call, "verification")
        self._exact_schema(verification, {"oracle_result", "verifier_result", "failure_taxonomy"}, set(), "verification")
        self._required_string(verification, "oracle_result", "verification")
        self._required_string(verification, "verifier_result", "verification")
        taxonomy = verification.get("failure_taxonomy")
        if not isinstance(taxonomy, list) or any(not isinstance(item, str) for item in taxonomy):
            raise ValueError("verification.failure_taxonomy must be a list of strings")
        derived_normalized, derived_verification = derive_answer_evidence(
            response["raw_response"], expected_answer,
        )
        if normalized != derived_normalized or verification != derived_verification:
            raise ValueError("supplied fields do not match derived answer evidence")

        schedule = self._mapping(call, "schedule")
        self._exact_schema(
            schedule,
            set(SCHEDULE_FIELDS) | {"admissible_unexplored_neighbors", "protected_exploration"},
            set(),
            "schedule",
        )
        for field in SCHEDULE_FIELDS:
            expected = getattr(unit, field)
            if field not in schedule or type(schedule[field]) is not type(expected) or schedule[field] != expected:
                raise ValueError(f"schedule.{field} does not match canonical A0 schedule")
        neighbors = schedule.get("admissible_unexplored_neighbors")
        if not isinstance(neighbors, list) or any(not isinstance(item, str) for item in neighbors):
            raise ValueError("schedule.admissible_unexplored_neighbors must be a list of strings")
        if not isinstance(schedule.get("protected_exploration"), bool):
            raise ValueError("schedule.protected_exploration must be boolean")

        telemetry = self._mapping(call, "telemetry")
        self._exact_schema(
            telemetry,
            {"input_tokens", "output_tokens", "total_duration", "load_duration", "prompt_eval_duration", "eval_duration"},
            {"completion_reason", "done_reason"},
            "telemetry",
        )
        for field in ("input_tokens", "output_tokens"):
            self._required_integer(telemetry, field, "telemetry")
        for field in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration"):
            value = telemetry.get(field)
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value < 0:
                raise ValueError(f"telemetry.{field} must be a non-negative finite number")
        if not any(isinstance(telemetry.get(field), str) and telemetry[field] for field in ("completion_reason", "done_reason")):
            raise ValueError("telemetry completion reason is required")

        layers = call.get("rendered_layers")
        if not isinstance(layers, (list, tuple)):
            raise ValueError("rendered_layers must be a sequence")
        if unit.treatment_kind == "RAW" and layers:
            raise ValueError("RAW must have zero rendered support layers")
        if unit.treatment_kind == "HISTORICAL_SEED" and len(layers) != 1:
            raise ValueError("HISTORICAL_SEED requires exactly one canonical historical seed layer")
        prepared_layers = []
        for expected_index, layer in enumerate(layers):
            if not isinstance(layer, Mapping) or JOIN_KEYS & set(layer):
                raise ValueError("rendered_layers entry is malformed")
            row = dict(layer)
            self._exact_schema(
                row,
                {"layer_index", "ingredient_id", "formulation_id", "dose_id", "rendered_bytes", "sha256"},
                set(),
                "rendered_layers",
            )
            if row.get("layer_index") != expected_index:
                raise ValueError("rendered_layers.layer_index must be contiguous from zero")
            for field in ("ingredient_id", "formulation_id", "dose_id"):
                self._required_string(row, field, "rendered_layers")
            rendered = row.pop("rendered_bytes", None)
            if not isinstance(rendered, bytes):
                raise TypeError("rendered_layers.rendered_bytes must be exact bytes")
            if row.get("sha256") != hashlib.sha256(rendered).hexdigest():
                raise ValueError("rendered_layers.sha256 mismatch")
            if unit.treatment_kind == "HISTORICAL_SEED":
                case = _CANONICAL_CASES.get(unit.case_id)
                expected = {
                    "ingredient_id": _HISTORICAL_SEED_INGREDIENT,
                    "formulation_id": unit.treatment_spec.representation,
                    "dose_id": unit.treatment_spec.amount,
                }
                if case is None or any(row.get(key) != value for key, value in expected.items()):
                    raise ValueError("rendered layer does not match canonical historical seed")
                if rendered != _historical_seed_bytes(case):
                    raise ValueError("rendered layer does not match canonical historical seed")
            row["rendered_bytes_hex"] = rendered.hex()
            prepared_layers.append(row)

        status = call.get("status", "COMPLETED")
        if status != "COMPLETED":
            raise ValueError("write_call records only complete A0 calls")
        journal = {
            "unit_id": unit_id, "physical_call_id": physical_call_id, "status": status,
            "model": model, "request": request, "response": response,
            "rendered_layers": prepared_layers, "normalized": normalized,
            "verification": verification, "schedule": schedule, "telemetry": telemetry,
        }
        self._encoded(journal)
        return journal

    @staticmethod
    def _projection_rows(journal: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
        join = {key: journal[key] for key in JOIN_KEYS}
        return {
            "raw_model_requests": [{**join, **journal["model"], **journal["request"]}],
            "raw_model_responses": [{**join, **journal["response"]}],
            "rendered_layers": [{**join, **layer} for layer in journal["rendered_layers"]],
            "normalized_model_calls": [{**join, **journal["normalized"], **journal["verification"]}],
            "runtime_telemetry": [{**join, **journal["telemetry"]}],
            "physical_call_ledger": [{**join, "status": journal["status"]}],
            "scheduler_ledger": [{**join, **journal["schedule"]}],
        }

    @staticmethod
    def _row_key(ledger: str, row: Mapping[str, Any]) -> tuple[Any, ...]:
        base = (row.get("unit_id"), row.get("physical_call_id"))
        return base + ((row.get("layer_index"),) if ledger == "rendered_layers" else ())

    def _read_rows(self, ledger: str) -> list[dict[str, Any]]:
        def reject_constant(value: str) -> None:
            raise ValueError(f"non-finite JSON constant: {value}")

        try:
            values = [
                json.loads(
                    line, parse_constant=reject_constant, object_pairs_hook=_reject_json_pairs,
                )
                for line in (self.root / f"{ledger}.jsonl").read_text(encoding="utf-8").splitlines()
                if line
            ]
        except (OSError, ValueError) as exc:
            raise ValueError(f"{ledger} is malformed") from exc
        if any(not isinstance(value, dict) for value in values):
            raise ValueError(f"{ledger} must contain JSON objects")
        return values

    @staticmethod
    def _call_from_journal(journal: Mapping[str, Any]) -> dict[str, Any]:
        try:
            request = dict(journal["request"])
            request_hex = request.pop("rendered_request_bytes_hex")
            if not isinstance(request_hex, str):
                raise ValueError("request bytes hex is malformed")
            request["rendered_request_bytes"] = bytes.fromhex(request_hex)
            layers = []
            for item in journal["rendered_layers"]:
                layer = dict(item)
                layer_hex = layer.pop("rendered_bytes_hex")
                if not isinstance(layer_hex, str):
                    raise ValueError("layer bytes hex is malformed")
                layer["rendered_bytes"] = bytes.fromhex(layer_hex)
                layers.append(layer)
            return {
                "unit_id": journal["unit_id"],
                "physical_call_id": journal["physical_call_id"],
                "status": journal["status"],
                "model": dict(journal["model"]),
                "request": request,
                "response": dict(journal["response"]),
                "rendered_layers": layers,
                "normalized": dict(journal["normalized"]),
                "verification": dict(journal["verification"]),
                "schedule": dict(journal["schedule"]),
                "telemetry": dict(journal["telemetry"]),
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("authoritative call journal is malformed") from exc

    def _validated_journals(self) -> list[dict[str, Any]]:
        rows = self._read_rows(CALL_JOURNAL)
        seen_units: set[str] = set()
        seen_calls: set[str] = set()
        validated: list[dict[str, Any]] = []
        for row in rows:
            unit_id = row.get("unit_id")
            physical_call_id = row.get("physical_call_id")
            if unit_id in seen_units or physical_call_id in seen_calls:
                raise ValueError("duplicate authoritative call journal identity")
            try:
                unsigned = self._authenticate(row)
                prepared = self._prepare_call(self._call_from_journal(unsigned))
            except (TypeError, ValueError) as exc:
                if "authentication" in str(exc):
                    raise
                raise ValueError("authoritative call journal is malformed") from exc
            if prepared != unsigned:
                raise ValueError("authoritative call journal is malformed")
            seen_units.add(unit_id)
            seen_calls.add(physical_call_id)
            validated.append(prepared)
        return validated

    def _assert_new_identity(self, journal: Mapping[str, Any]) -> None:
        for row in self._validated_journals():
            if row.get("unit_id") == journal["unit_id"] or row.get("physical_call_id") == journal["physical_call_id"]:
                raise ValueError("unit_id or physical_call_id is already committed")

    def write_call(self, call: Mapping[str, Any]) -> None:
        """Commit one prevalidated A0 call, then project it to secondary ledgers."""
        journal = self._prepare_call(call)
        self._assert_new_identity(journal)
        self._append_encoded(CALL_JOURNAL, self._encoded(self._signed(journal)))
        self.reconcile_projections()

    def read_committed_calls(self) -> tuple[dict[str, Any], ...]:
        """Return only fully validated authoritative committed A0 calls."""
        return tuple(self._call_from_journal(row) for row in self._validated_journals())

    def reconcile_projections(self) -> int:
        """Idempotently repair missing projections and reject anything not journal-derived."""
        journals = self._validated_journals()
        expected: dict[str, dict[tuple[Any, ...], dict[str, Any]]] = {
            ledger: {} for ledger in CALL_PROJECTIONS
        }
        for journal in journals:
            for ledger, rows in self._projection_rows(journal).items():
                for row in rows:
                    key = self._row_key(ledger, row)
                    if key in expected[ledger]:
                        raise ValueError(f"{ledger} has duplicate authoritative projection identity")
                    expected[ledger][key] = row

        repairs: list[tuple[str, str]] = []
        for ledger in CALL_PROJECTIONS:
            rows = self._read_rows(ledger)
            actual = {self._row_key(ledger, row): row for row in rows}
            if len(actual) != len(rows):
                raise ValueError(f"{ledger} contains duplicate projection identities")
            for key, row in actual.items():
                desired = expected[ledger].get(key)
                if desired is None:
                    raise ValueError(f"{ledger} contains orphan projection identity")
                if row != desired:
                    raise ValueError(f"{ledger} conflicts with authoritative call journal")
            for key, desired in expected[ledger].items():
                if key not in actual:
                    repairs.append((ledger, self._encoded(desired)))
        for ledger, encoded in repairs:
            self._append_encoded(ledger, encoded)
        return len(repairs)
