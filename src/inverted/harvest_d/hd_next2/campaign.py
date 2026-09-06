"""Authorized executor for the frozen static HD-NEXT-2A-0 campaign."""

from __future__ import annotations

from dataclasses import asdict
from enum import Enum
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import time
from typing import Any, Mapping
from urllib.request import Request

from .artifacts import EvidenceWriter, derive_answer_evidence
from .authorization import validate_stage_authorization
from .budget import CombinedActionBudget
from .cases import generate_hd_next2_cases
from .config import canonical_a0_planner_config
from .rendering import render_hd_next1_historical_seed, serialize_canonical_a0_request
from .stages import build_canonical_a0_plan
from inverted.harvest_d.models import OllamaChatAdapter


_ATTEMPT_JOURNAL = "attempt_journal.jsonl"
_ATTEMPT_HEAD = "attempt_journal_head.json"
_ATTEMPT_HMAC_DOMAIN = b"INVERTED/HD-NEXT-2/A0/ATTEMPT-JOURNAL/v1\x00"
_ATTEMPT_HEAD_HMAC_DOMAIN = b"INVERTED/HD-NEXT-2/A0/ATTEMPT-JOURNAL-HEAD/v1\x00"
_ATTEMPT_GENESIS_HASH = "0" * 64
_ATTEMPT_FIELDS = {
    "event", "unit_id", "physical_call_id", "model_key", "model_id",
    "request_sha256", "seq", "previous_row_sha256", "attempt_hmac_sha256",
}
_ATTEMPT_HEAD_FIELDS = {"seq", "row_sha256", "head_hmac_sha256"}


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _read_frozen_schedule(path: Path) -> tuple[dict[str, Any], ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        rows = tuple(
            json.loads(
                line, object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_nonfinite,
            )
            for line in lines
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("frozen schedule is malformed") from exc
    if len(rows) != 192 or any(not isinstance(row, dict) for row in rows):
        raise ValueError("frozen schedule must contain exactly 192 JSON objects")
    return rows


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


class _AttemptJournal:
    def __init__(self, root: str | Path, secret: bytes):
        self.path = Path(root) / _ATTEMPT_JOURNAL
        self.head_path = Path(root) / _ATTEMPT_HEAD
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.secret = secret
        journal_exists = self.path.exists()
        head_exists = self.head_path.exists()
        if journal_exists != head_exists:
            raise ValueError("attempt journal or signed head is missing")
        if not journal_exists:
            self.path.touch(exist_ok=False)
            self._write_head(0, _ATTEMPT_GENESIS_HASH)

    @staticmethod
    def _encoded(row: Mapping[str, Any]) -> str:
        return json.dumps(
            dict(row), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )

    def _signature(self, row: Mapping[str, Any]) -> str:
        return hmac.new(
            self.secret,
            _ATTEMPT_HMAC_DOMAIN + self._encoded(row).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _head_signature(self, head: Mapping[str, Any]) -> str:
        return hmac.new(
            self.secret,
            _ATTEMPT_HEAD_HMAC_DOMAIN + self._encoded(head).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _write_head(self, seq: int, row_sha256: str) -> None:
        head = {"seq": seq, "row_sha256": row_sha256}
        head["head_hmac_sha256"] = self._head_signature(head)
        temporary = self.head_path.with_name(self.head_path.name + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            stream.write(self._encoded(head) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.head_path)

    def _read_head(self) -> dict[str, Any]:
        try:
            head = json.loads(
                self.head_path.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_nonfinite,
            )
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError("attempt journal signed head is malformed") from exc
        if not isinstance(head, dict) or set(head) != _ATTEMPT_HEAD_FIELDS:
            raise ValueError("attempt journal signed head exact schema mismatch")
        signature = head.get("head_hmac_sha256")
        unsigned = {key: value for key, value in head.items() if key != "head_hmac_sha256"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, self._head_signature(unsigned)):
            raise ValueError("attempt journal signed head authentication failed")
        if isinstance(head["seq"], bool) or not isinstance(head["seq"], int) or head["seq"] < 0:
            raise ValueError("attempt journal signed head sequence is invalid")
        if not isinstance(head["row_sha256"], str) or len(head["row_sha256"]) != 64:
            raise ValueError("attempt journal signed head hash is invalid")
        return head

    def append(self, event: str, unit: object, model_id: str, request_sha256: str) -> None:
        rows = self.read()
        previous_hash = (
            hashlib.sha256(self._encoded(rows[-1]).encode("utf-8")).hexdigest()
            if rows else _ATTEMPT_GENESIS_HASH
        )
        row = {
            "event": event,
            "unit_id": unit.unit_id,
            "physical_call_id": f"a0-call-{unit.unit_id}",
            "model_key": unit.model_key,
            "model_id": model_id,
            "request_sha256": request_sha256,
            "seq": len(rows) + 1,
            "previous_row_sha256": previous_hash,
        }
        row["attempt_hmac_sha256"] = self._signature(row)
        encoded = self._encoded(row)
        with self.path.open("a", encoding="utf-8", newline="") as stream:
            stream.write(encoded + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self._write_head(row["seq"], hashlib.sha256(encoded.encode("utf-8")).hexdigest())

    def read(self) -> tuple[dict[str, Any], ...]:
        head = self._read_head()
        try:
            rows = tuple(
                json.loads(
                    line, object_pairs_hook=_reject_duplicate_keys,
                    parse_constant=_reject_nonfinite,
                )
                for line in self.path.read_text(encoding="utf-8").splitlines()
                if line
            )
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError("attempt journal is malformed") from exc
        validated = []
        previous_hash = _ATTEMPT_GENESIS_HASH
        for expected_seq, row in enumerate(rows, start=1):
            if not isinstance(row, dict) or set(row) != _ATTEMPT_FIELDS:
                raise ValueError("attempt journal exact schema mismatch")
            signature = row.get("attempt_hmac_sha256")
            unsigned = {key: value for key, value in row.items() if key != "attempt_hmac_sha256"}
            if not isinstance(signature, str) or not hmac.compare_digest(signature, self._signature(unsigned)):
                raise ValueError("attempt journal authentication failed")
            if row["event"] not in {"STARTED", "COMMITTED", "AMBIGUOUS"}:
                raise ValueError("attempt journal event is invalid")
            if row["seq"] != expected_seq or isinstance(row["seq"], bool):
                raise ValueError("attempt journal sequence is invalid")
            if row["previous_row_sha256"] != previous_hash:
                raise ValueError("attempt journal previous-row hash is invalid")
            string_fields = _ATTEMPT_FIELDS - {"seq"}
            if any(not isinstance(row[field], str) or not row[field] for field in string_fields):
                raise ValueError("attempt journal fields must be non-empty strings")
            validated.append(row)
            previous_hash = hashlib.sha256(self._encoded(row).encode("utf-8")).hexdigest()
        if head["seq"] != len(validated) or head["row_sha256"] != previous_hash:
            raise ValueError("attempt journal signed head does not match journal tail")
        return tuple(validated)

    def reconcile(
        self, units: tuple[object, ...], model_ids: Mapping[str, str],
        cases_by_id: Mapping[str, object], committed: tuple[dict[str, Any], ...],
    ) -> None:
        by_unit = {unit.unit_id: unit for unit in units}
        evidence = {call["unit_id"]: call for call in committed}
        events: dict[str, list[str]] = {}
        for row in self.read():
            unit = by_unit.get(row["unit_id"])
            if unit is None:
                raise ValueError("attempt journal canonical binding mismatch")
            request = serialize_canonical_a0_request(
                cases_by_id[unit.case_id], model_ids[unit.model_key], unit.treatment_kind,
            )
            expected = {
                "physical_call_id": f"a0-call-{unit.unit_id}",
                "model_key": unit.model_key,
                "model_id": model_ids[unit.model_key],
                "request_sha256": hashlib.sha256(request).hexdigest(),
            }
            if any(row[key] != value for key, value in expected.items()):
                raise ValueError("attempt journal canonical binding mismatch")
            call = evidence.get(unit.unit_id)
            if call is not None and (
                call.get("physical_call_id") != expected["physical_call_id"]
                or call.get("model", {}).get("model_key") != expected["model_key"]
                or call.get("model", {}).get("model_id") != expected["model_id"]
                or call.get("request", {}).get("rendered_request_sha256")
                != expected["request_sha256"]
            ):
                raise ValueError("attempt has no exact matching signed call evidence")
            sequence = events.setdefault(unit.unit_id, [])
            if row["event"] in sequence:
                raise ValueError("attempt journal duplicate event")
            sequence.append(row["event"])
        for unit_id, sequence in events.items():
            if sequence[0] != "STARTED" or sequence not in (
                ["STARTED"], ["STARTED", "COMMITTED"], ["STARTED", "AMBIGUOUS"],
                ["STARTED", "AMBIGUOUS", "COMMITTED"],
            ):
                raise ValueError("attempt journal event sequence is invalid")
            has_evidence = unit_id in evidence
            if "COMMITTED" in sequence and not has_evidence:
                raise ValueError("COMMITTED attempt has no matching signed call evidence")
            if "COMMITTED" not in sequence:
                if has_evidence:
                    unit = by_unit[unit_id]
                    request = serialize_canonical_a0_request(
                        cases_by_id[unit.case_id], model_ids[unit.model_key], unit.treatment_kind,
                    )
                    self.append("COMMITTED", unit, model_ids[unit.model_key], hashlib.sha256(request).hexdigest())
                else:
                    raise ValueError(f"attempt {unit_id} is unsafe-to-retry")
        if set(evidence) - set(events):
            raise ValueError("signed call evidence has no matching attempt journal")


def _canonical_units_in_frozen_order(root: Path) -> tuple[object, ...]:
    rows = _read_frozen_schedule(root / "frozen_schedule.jsonl")
    canonical_units = build_canonical_a0_plan().units
    expected = tuple(_plain(asdict(unit)) for unit in canonical_units)
    if rows != expected:
        raise ValueError("frozen schedule is not the exact ordered canonical A0 schedule")
    by_payload = {
        json.dumps(payload, sort_keys=True, separators=(",", ":")): unit
        for payload, unit in zip(expected, canonical_units, strict=True)
    }
    return tuple(
        by_payload[json.dumps(row, sort_keys=True, separators=(",", ":"))]
        for row in rows
    )


def _ollama_runtime_provenance(
    adapters: Mapping[str, object], model_ids: Mapping[str, str], budget: CombinedActionBudget,
) -> tuple[dict[str, str], str]:
    base_urls = {adapter.base_url.rstrip("/") for adapter in adapters.values()}
    if len(base_urls) != 1:
        raise ValueError("all A0 Ollama adapters must share one normalized base_url")
    base_url = base_urls.pop()
    opener = next(iter(adapters.values()))._opener
    if any(adapter._opener is not opener for adapter in adapters.values()):
        raise ValueError("all A0 adapters must use one shared trusted Ollama opener")
    payloads = {}
    for endpoint in ("version", "tags"):
        budget.reserve("provenance_api_call")
        request = Request(base_url + f"/api/{endpoint}", method="GET")
        try:
            with opener(request, timeout=next(iter(adapters.values())).timeout) as response:
                payload = json.loads(
                    response.read().decode("utf-8"), object_pairs_hook=_reject_duplicate_keys,
                    parse_constant=_reject_nonfinite,
                )
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Ollama /api/{endpoint} preflight failed") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"Ollama /api/{endpoint} preflight response is malformed")
        payloads[endpoint] = payload

    version = payloads["version"].get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Ollama preflight version must be nonempty")
    models = payloads["tags"].get("models")
    if not isinstance(models, list):
        raise ValueError("Ollama preflight models are malformed")
    digests: dict[str, str] = {}
    for item in models:
        if not isinstance(item, dict):
            raise ValueError("Ollama preflight model tag is malformed")
        name = item.get("name")
        if name in model_ids.values():
            digest = item.get("digest")
            if name in digests:
                raise ValueError(f"Ollama preflight duplicate exact model tag: {name}")
            if not isinstance(digest, str) or not digest.strip():
                raise ValueError(f"Ollama preflight digest missing for exact model: {name}")
            digests[name] = digest
    missing = sorted(set(model_ids.values()) - set(digests))
    if missing:
        raise ValueError(f"Ollama preflight exact model tags missing: {missing}")
    return digests, f"ollama:{base_url}:version={version.strip()}"


def run_static_a0_campaign(
    *, preregistration_root: str | Path, authorization: Mapping[str, object],
    owner_secret: bytes, adapters: Mapping[str, object], evidence_root: str | Path,
    budget: CombinedActionBudget, stop_after: int | None = None,
) -> dict[str, object]:
    """Execute or resume only the authenticated frozen 192-unit A0 campaign."""
    root = Path(preregistration_root)
    validate_stage_authorization(root, authorization, owner_secret=owner_secret)
    units = _canonical_units_in_frozen_order(root)
    if stop_after is not None and (
        isinstance(stop_after, bool) or not isinstance(stop_after, int) or stop_after < 1
    ):
        raise ValueError("stop_after must be a positive operator/test call limit")

    model_ids = canonical_a0_planner_config()["models"]
    cases = generate_hd_next2_cases("development", seed=20260921, per_region=1)
    cases_by_id = {case.case_id: case for case in cases}
    writer = EvidenceWriter(evidence_root, journal_secret=owner_secret)
    writer.reconcile_projections()
    committed = writer.read_committed_calls()
    attempts = _AttemptJournal(evidence_root, owner_secret)
    attempts.reconcile(units, model_ids, cases_by_id, committed)
    if set(adapters) != set(model_ids):
        raise ValueError("adapters must match the exact frozen A0 model set")
    for model_key, model_id in model_ids.items():
        adapter = adapters[model_key]
        if type(adapter) is not OllamaChatAdapter:
            raise ValueError(f"{model_key} must use exact OllamaChatAdapter")
        if adapter.model_id != model_id:
            raise ValueError(f"adapter model identity mismatch for {model_key}")
    model_digests, runtime_identity = _ollama_runtime_provenance(adapters, model_ids, budget)
    for call in committed:
        model = call["model"]
        if (
            model["runtime_identity"] != runtime_identity
            or model["model_digest"] != model_digests.get(model["model_id"])
        ):
            raise ValueError("committed evidence provenance does not match current Ollama runtime")
    committed_units = {call["unit_id"] for call in committed}
    attempted = 0

    for unit in units:
        if unit.unit_id in committed_units:
            continue
        if stop_after is not None and attempted >= stop_after:
            break
        case = cases_by_id[unit.case_id]
        adapter = adapters[unit.model_key]
        request_bytes = serialize_canonical_a0_request(
            case, model_ids[unit.model_key], unit.treatment_kind,
        )
        request_payload = json.loads(request_bytes.decode("utf-8"))
        messages = request_payload["messages"]
        prompt = messages[-1]["content"]
        system = messages[0]["content"] if len(messages) == 2 else None
        request_serializer = getattr(adapter, "request_bytes", None)
        if not callable(request_serializer) or request_serializer(prompt, system) != request_bytes:
            raise ValueError("adapter request bytes do not match the canonical serializer")
        budget.reserve("model_call")
        attempted += 1
        request_sha256 = hashlib.sha256(request_bytes).hexdigest()
        attempts.append("STARTED", unit, model_ids[unit.model_key], request_sha256)
        try:
            started = time.perf_counter()
            response = adapter.complete_request_bytes(request_bytes)
            elapsed = max(0.0, time.perf_counter() - started)
            if response.model != model_ids[unit.model_key]:
                raise ValueError("adapter response model identity mismatch")
            expected = case.oracle.expected.get("answer") if isinstance(case.oracle.expected, dict) else case.oracle.expected
            normalized, verification = derive_answer_evidence(response.text, expected)
            raw = dict(response.raw)
            total = float(raw.get("total_duration", response.latency_ms * 1_000_000)) / 1_000_000_000
            load = float(raw.get("load_duration", 0)) / 1_000_000_000
            prompt_eval = float(raw.get("prompt_eval_duration", 0)) / 1_000_000_000
            evaluation = float(raw.get("eval_duration", 0)) / 1_000_000_000
            if not all(math.isfinite(value) and value >= 0 for value in (total, load, prompt_eval, evaluation)):
                raise ValueError("adapter telemetry durations must be finite and nonnegative")
            if total == 0 and response.latency_ms:
                total = float(response.latency_ms) / 1000.0
            layers = []
            if unit.treatment_kind == "HISTORICAL_SEED":
                seed_system, seed_user, seed_metadata = render_hd_next1_historical_seed(case)
                rendered = json.dumps(
                    {"system": seed_system, "user": seed_user, "metadata": seed_metadata},
                    sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                ).encode("utf-8")
                layers.append({
                    "layer_index": 0, "ingredient_id": "HD_NEXT_1_HISTORICAL_SEED",
                    "formulation_id": unit.treatment_spec.representation,
                    "dose_id": unit.treatment_spec.amount, "rendered_bytes": rendered,
                    "sha256": hashlib.sha256(rendered).hexdigest(),
                })
            schedule = {
                field: getattr(unit, field) for field in (
                    "case_id", "partition", "operating_region", "model_key",
                    "treatment_kind", "treatment_spec_id", "treatment_spec_sha256",
                    "replicate", "execution_position", "model_role", "eligible_for_recipe",
                    "model_block", "selection_reason", "max_attempts", "retry_of_unit_id",
                )
            }
            schedule.update(admissible_unexplored_neighbors=[], protected_exploration=False)
            writer.write_call({
                "unit_id": unit.unit_id, "physical_call_id": f"a0-call-{unit.unit_id}",
                "model": {
                    "model_key": unit.model_key, "model_id": model_ids[unit.model_key],
                    "model_digest": model_digests[model_ids[unit.model_key]],
                    "runtime_identity": runtime_identity,
                },
                "request": {
                    "rendered_request_bytes": request_bytes,
                    "rendered_request_sha256": request_sha256,
                },
                "response": {"raw_response": response.text}, "rendered_layers": layers,
                "normalized": normalized,
                "verification": verification,
                "schedule": schedule,
                "telemetry": {
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "total_duration": total or elapsed, "load_duration": load,
                    "prompt_eval_duration": prompt_eval, "eval_duration": evaluation,
                    "done_reason": str(raw.get("done_reason", "completed")),
                },
            })
            attempts.append("COMMITTED", unit, model_ids[unit.model_key], request_sha256)
        except BaseException:
            attempts.append("AMBIGUOUS", unit, model_ids[unit.model_key], request_sha256)
            raise

    all_calls = writer.read_committed_calls()
    by_unit = {call["unit_id"]: call for call in all_calls}
    analysis_rows = []
    for unit in units:
        call = by_unit.get(unit.unit_id)
        if call is None:
            continue
        row = dict(vars(unit))
        row.update(
            correct=call["normalized"]["correctness"],
            normalized_answer=call["normalized"]["normalized_answer"],
            runtime_seconds=call["telemetry"]["total_duration"],
            load_seconds=call["telemetry"]["load_duration"],
            prompt_eval_seconds=call["telemetry"]["prompt_eval_duration"],
            eval_seconds=call["telemetry"]["eval_duration"],
        )
        analysis_rows.append(row)
    return {
        "status": "COMPLETED" if len(all_calls) == 192 else "STOPPED",
        "physical_model_calls": attempted, "analysis_rows": analysis_rows,
        "cases_by_id": cases_by_id,
    }
