from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import pytest

from inverted.harvest_d.hd_next2.campaign import _AttemptJournal, run_static_a0_campaign
from inverted.harvest_d.hd_next2.analysis import summarize_a0
from inverted.harvest_d.hd_next2.authorization import (
    authorize_stage_execution,
    prepare_stage_authorization,
)
from inverted.harvest_d.hd_next2.budget import CombinedActionBudget
from inverted.harvest_d.hd_next2.cases import OPERATING_REGIONS
from inverted.harvest_d.hd_next2.cases import generate_hd_next2_cases
from inverted.harvest_d.hd_next2.config import canonical_a0_planner_config
from inverted.harvest_d.models import OllamaChatAdapter
from inverted.harvest_d.hd_next2.artifacts import CALL_PROJECTIONS
from inverted.harvest_d.hd_next2.rendering import serialize_canonical_a0_request
from inverted.harvest_d.hd_next2.stages import build_canonical_a0_plan
from inverted.harvest_d.hd_next2.preregistration import build_stage_preregistration
from inverted.harvest_d.hd_next2.types import StageId


MODEL_IDS = canonical_a0_planner_config()["models"]
OWNER_SECRET = b"campaign-test-owner-secret-is-32-bytes"


class FakeOllamaOpener:
    def __init__(self, *, tags=None, version="0.12.3", response_mutators=None, transport_errors=None):
        self.calls = []
        self.chat_calls = {model_id: [] for model_id in MODEL_IDS.values()}
        self.tags = tags if tags is not None else [
            {"name": model_id, "digest": f"sha256:daemon-{key.lower()}"}
            for key, model_id in MODEL_IDS.items()
        ]
        self.version = version
        self.response_mutators = dict(response_mutators or {})
        self.transport_errors = dict(transport_errors or {})

    class Response:
        def __init__(self, payload): self.payload = payload
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self): return json.dumps(self.payload, allow_nan=True).encode("utf-8")

    def __call__(self, request, *, timeout):
        endpoint = request.full_url.rsplit("/", 2)[-2:]
        endpoint = "/" + "/".join(endpoint)
        self.calls.append(endpoint)
        if endpoint == "/api/version":
            return self.Response({"version": self.version})
        if endpoint == "/api/tags":
            return self.Response({"models": self.tags})
        if endpoint != "/api/chat":
            raise AssertionError(f"unexpected endpoint {endpoint}")
        payload = json.loads(request.data.decode("utf-8"))
        model_id = payload["model"]
        self.chat_calls[model_id].append(request.data)
        error = self.transport_errors.get(model_id)
        if error is not None:
            raise error
        answer = _answers_for(model_id)[request.data]
        text = json.dumps({"answer": answer}, separators=(",", ":"))
        response = {
            "model": model_id, "message": {"content": text},
            "prompt_eval_count": 10, "eval_count": 2, "total_duration": 9_000_000,
            "load_duration": 1_000_000, "prompt_eval_duration": 3_000_000,
            "eval_duration": 5_000_000, "done_reason": "stop",
        }
        mutator = self.response_mutators.get(model_id)
        if mutator is not None:
            mutator(response)
        return self.Response(response)


def _answers_for(model_id):
    answers = {}
    for case in generate_hd_next2_cases("development", seed=20260921, per_region=1):
        expected = case.oracle.expected["answer"]
        for treatment_kind in ("RAW", "HISTORICAL_SEED"):
            request = serialize_canonical_a0_request(case, model_id, treatment_kind)
            answers[request] = expected

    return answers


def FakeAdapter(model_id, *, opener=None, response_mutator=None, transport_error=None, base_url="http://127.0.0.1:11434"):
    if opener is None:
        opener = FakeOllamaOpener(
            response_mutators={model_id: response_mutator} if response_mutator else None,
            transport_errors={model_id: transport_error} if transport_error else None,
        )
    adapter = OllamaChatAdapter(model_id, opener=opener, base_url=base_url)
    adapter.model_digest = "sha256:forged-mutable-adapter-digest"
    adapter.runtime_identity = "forged-mutable-adapter-runtime"
    adapter.calls = opener.chat_calls[model_id]
    return adapter


def FakeAdapters(*, opener=None, base_urls=None):
    opener = opener or FakeOllamaOpener()
    base_urls = base_urls or {}
    return {
        key: FakeAdapter(model_id, opener=opener, base_url=base_urls.get(key, "http://127.0.0.1:11434"))
        for key, model_id in MODEL_IDS.items()
    }


def _real_package(tmp_path, monkeypatch):
    # Product source cleanliness is covered by preregistration tests and cannot
    # pass until these intended changes are committed. Keep every package and
    # authorization operation real; bypass only that independent git-state gate.
    monkeypatch.setattr(
        "inverted.harvest_d.hd_next2.preregistration._assert_recorded_commit_source",
        lambda commit: None,
    )
    root = tmp_path / "preregistered"
    build_stage_preregistration(
        Path.cwd(), root, canonical_a0_planner_config(),
        StageId.A0, build_canonical_a0_plan(),
    )
    prepared = prepare_stage_authorization(root)
    authorization = authorize_stage_execution(
        prepared, owner_approved=True, owner_secret=OWNER_SECRET,
    )
    return root, authorization


def _run(tmp_path, monkeypatch, *, stop_after=None, adapters=None, budget=None):
    package, authorization = _real_package(tmp_path, monkeypatch)
    adapters = adapters or FakeAdapters()
    budget = budget or CombinedActionBudget()
    result = run_static_a0_campaign(
        preregistration_root=package,
        authorization=authorization, owner_secret=OWNER_SECRET,
        adapters=adapters, evidence_root=tmp_path / "evidence", budget=budget,
        stop_after=stop_after,
    )
    return result, adapters, budget


def _remove_unit_rows(path, unit_id):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows if row.get("unit_id") != unit_id
        ),
        encoding="utf-8",
    )


def test_fake_static_a0_campaign_executes_exact_frozen_schedule_and_reconciles(tmp_path, monkeypatch):
    plan = build_canonical_a0_plan()
    frozen_before = tuple(plan.units)
    package, authorization = _real_package(tmp_path, monkeypatch)
    schedule = package / "frozen_schedule.jsonl"
    frozen_bytes = schedule.read_bytes()
    opener = FakeOllamaOpener()
    adapters = FakeAdapters(opener=opener)
    budget = CombinedActionBudget()
    result = run_static_a0_campaign(
        preregistration_root=package, authorization=authorization,
        owner_secret=OWNER_SECRET, adapters=adapters,
        evidence_root=tmp_path / "evidence", budget=budget,
    )
    assert result["status"] == "COMPLETED"
    assert result["physical_model_calls"] == 192
    assert budget.model_used == 192 and budget.non_model_used == 2 and budget.total_used == 194
    assert Counter(opener.calls) == {"/api/version": 1, "/api/tags": 1, "/api/chat": 192}
    assert {key: len(adapter.calls) for key, adapter in adapters.items()} == {
        "SMALL_A": 64, "QWEN": 64, "DEVSTRAL_24B": 64,
    }
    journals = [json.loads(line) for line in (tmp_path / "evidence" / "call_journal.jsonl").read_text().splitlines()]
    assert len(journals) == 192
    assert {row["model"]["runtime_identity"] for row in journals} == {
        "ollama:http://127.0.0.1:11434:version=0.12.3"
    }
    assert {
        (row["model"]["model_id"], row["model"]["model_digest"])
        for row in journals
    } == {
        (model_id, f"sha256:daemon-{key.lower()}") for key, model_id in MODEL_IDS.items()
    }
    frozen_rows = [json.loads(line) for line in frozen_bytes.decode("utf-8").splitlines()]
    assert [row["unit_id"] for row in journals] == [row["unit_id"] for row in frozen_rows]
    assert all(row["verification"] == {
        "oracle_result": row["verification"]["oracle_result"],
        "verifier_result": "PASS",
        "failure_taxonomy": [],
    } for row in journals)
    assert Counter(row["schedule"]["treatment_kind"] for row in journals) == {"RAW": 96, "HISTORICAL_SEED": 96}
    coverage = defaultdict(set)
    for row in journals:
        coverage[(row["model"]["model_key"], row["schedule"]["treatment_kind"])].add(row["schedule"]["operating_region"])
        assert bytes.fromhex(row["request"]["rendered_request_bytes_hex"]) == serialize_canonical_a0_request(
            result["cases_by_id"][row["schedule"]["case_id"]], row["model"]["model_id"],
            row["schedule"]["treatment_kind"],
        )
    assert all(regions == set(OPERATING_REGIONS) for regions in coverage.values())
    assert len(coverage) == 6
    assert len({row["unit_id"] for row in journals}) == len({row["physical_call_id"] for row in journals}) == 192
    assert tuple(build_canonical_a0_plan().units) == frozen_before
    assert len(result["analysis_rows"]) == 192
    assert schedule.read_bytes() == frozen_bytes
    summarize_a0(result["analysis_rows"])
    expected_projection_counts = {
        "raw_model_requests": 192, "raw_model_responses": 192, "rendered_layers": 96,
        "normalized_model_calls": 192, "runtime_telemetry": 192,
        "physical_call_ledger": 192, "scheduler_ledger": 192,
    }
    for ledger, expected in expected_projection_counts.items():
        assert len((tmp_path / "evidence" / f"{ledger}.jsonl").read_text().splitlines()) == expected


def test_stop_then_resume_skips_authoritative_units_without_mutating_schedule(tmp_path, monkeypatch):
    plan_before = tuple(build_canonical_a0_plan().units)
    first, adapters, first_budget = _run(tmp_path, monkeypatch, stop_after=37)
    assert first["status"] == "STOPPED" and first["physical_model_calls"] == 37
    assert first_budget.model_used == 37 and first_budget.non_model_used == 2

    package = tmp_path / "preregistered"
    authorization = authorize_stage_execution(
        prepare_stage_authorization(package), owner_approved=True,
        owner_secret=OWNER_SECRET,
    )
    second_budget = CombinedActionBudget()
    second = run_static_a0_campaign(
        preregistration_root=package, authorization=authorization,
        owner_secret=OWNER_SECRET, adapters=adapters,
        evidence_root=tmp_path / "evidence", budget=second_budget,
    )
    assert second["status"] == "COMPLETED" and second["physical_model_calls"] == 155
    assert second_budget.model_used == 155 and second_budget.non_model_used == 2
    assert tuple(build_canonical_a0_plan().units) == plan_before
    assert {row["unit_id"] for row in second["analysis_rows"]} == {unit.unit_id for unit in plan_before}
    assert len(second["analysis_rows"]) == 192
    assert sum(len(adapter.calls) for adapter in adapters.values()) == 192


def test_resume_rejects_coordinated_middle_call_and_attempt_row_removal_before_adapter_access(tmp_path, monkeypatch):
    first, _, _ = _run(tmp_path, monkeypatch, stop_after=3)
    assert first["physical_model_calls"] == 3
    evidence = tmp_path / "evidence"
    calls = [json.loads(line) for line in (evidence / "call_journal.jsonl").read_text().splitlines()]
    removed_unit = calls[1]["unit_id"]
    _remove_unit_rows(evidence / "call_journal.jsonl", removed_unit)
    for projection in CALL_PROJECTIONS:
        _remove_unit_rows(evidence / f"{projection}.jsonl", removed_unit)
    _remove_unit_rows(evidence / "attempt_journal.jsonl", removed_unit)

    package = tmp_path / "preregistered"
    authorization = authorize_stage_execution(
        prepare_stage_authorization(package), owner_approved=True, owner_secret=OWNER_SECRET,
    )
    opener = FakeOllamaOpener()
    with pytest.raises(ValueError, match="attempt journal"):
        run_static_a0_campaign(
            preregistration_root=package, authorization=authorization,
            owner_secret=OWNER_SECRET, adapters=FakeAdapters(opener=opener),
            evidence_root=evidence, budget=CombinedActionBudget(),
        )
    assert opener.calls == []


def test_resume_rejects_attempt_journal_suffix_truncation_with_unchanged_head(tmp_path, monkeypatch):
    first, _, _ = _run(tmp_path, monkeypatch, stop_after=3)
    assert first["physical_model_calls"] == 3
    journal = tmp_path / "evidence" / "attempt_journal.jsonl"
    rows = journal.read_text(encoding="utf-8").splitlines(keepends=True)
    journal.write_text("".join(rows[:-1]), encoding="utf-8")

    package = tmp_path / "preregistered"
    authorization = authorize_stage_execution(
        prepare_stage_authorization(package), owner_approved=True, owner_secret=OWNER_SECRET,
    )
    opener = FakeOllamaOpener()
    with pytest.raises(ValueError, match="attempt journal"):
        run_static_a0_campaign(
            preregistration_root=package, authorization=authorization,
            owner_secret=OWNER_SECRET, adapters=FakeAdapters(opener=opener),
            evidence_root=tmp_path / "evidence", budget=CombinedActionBudget(),
        )
    assert opener.calls == []


@pytest.mark.parametrize(
    ("opener", "message"),
    [
        (FakeOllamaOpener(version=""), "version"),
        (FakeOllamaOpener(tags=[]), "model"),
        (FakeOllamaOpener(tags=[
            {"name": model_id, "digest": f"sha256:daemon-{key.lower()}"}
            for key, model_id in MODEL_IDS.items() if key != "QWEN"
        ]), "model"),
        (FakeOllamaOpener(tags=[
            {"name": model_id, "digest": "" if key == "QWEN" else f"sha256:daemon-{key.lower()}"}
            for key, model_id in MODEL_IDS.items()
        ]), "digest"),
    ],
)
def test_ollama_preflight_identity_failures_precede_model_budget_and_chat(
    tmp_path, monkeypatch, opener, message,
):
    package, authorization = _real_package(tmp_path, monkeypatch)
    budget = CombinedActionBudget()
    with pytest.raises(ValueError, match=message):
        run_static_a0_campaign(
            preregistration_root=package, authorization=authorization,
            owner_secret=OWNER_SECRET, adapters=FakeAdapters(opener=opener),
            evidence_root=tmp_path / "evidence", budget=budget,
        )
    assert budget.model_used == 0
    assert "/api/chat" not in opener.calls


def test_ollama_preflight_requires_one_normalized_base_url_before_http(tmp_path, monkeypatch):
    package, authorization = _real_package(tmp_path, monkeypatch)
    opener = FakeOllamaOpener()
    adapters = FakeAdapters(opener=opener, base_urls={"QWEN": "http://other.test:11434/"})
    budget = CombinedActionBudget()
    with pytest.raises(ValueError, match="base_url"):
        run_static_a0_campaign(
            preregistration_root=package, authorization=authorization,
            owner_secret=OWNER_SECRET, adapters=adapters,
            evidence_root=tmp_path / "evidence", budget=budget,
        )
    assert budget.total_used == 0
    assert opener.calls == []


def test_ollama_preflight_requires_one_shared_trusted_opener_before_any_action(tmp_path, monkeypatch):
    package, authorization = _real_package(tmp_path, monkeypatch)
    openers = [FakeOllamaOpener() for _ in MODEL_IDS]
    adapters = {
        key: OllamaChatAdapter(model_id, opener=opener)
        for (key, model_id), opener in zip(MODEL_IDS.items(), openers, strict=True)
    }
    budget = CombinedActionBudget()

    with pytest.raises(ValueError, match="shared trusted Ollama opener"):
        run_static_a0_campaign(
            preregistration_root=package, authorization=authorization,
            owner_secret=OWNER_SECRET, adapters=adapters,
            evidence_root=tmp_path / "evidence", budget=budget,
        )

    assert budget.total_used == 0
    assert all(opener.calls == [] for opener in openers)


def test_authorization_failure_precedes_adapter_access_and_writes_no_evidence(tmp_path, monkeypatch):
    class ExplodingAdapters(dict):
        def __iter__(self): raise AssertionError("adapter accessed")
        def items(self): raise AssertionError("adapter accessed")
        def __getitem__(self, key): raise AssertionError("adapter accessed")

    package, authorization = _real_package(tmp_path, monkeypatch)
    authorization = {**authorization, "owner_approved": False}
    with pytest.raises(ValueError, match="not approved"):
        run_static_a0_campaign(
            preregistration_root=package, authorization=authorization,
            owner_secret=OWNER_SECRET, adapters=ExplodingAdapters(),
            evidence_root=tmp_path / "evidence", budget=CombinedActionBudget(),
        )
    assert not (tmp_path / "evidence" / "call_journal.jsonl").exists()


def test_adapter_exception_propagates_after_one_reservation_without_retry(tmp_path, monkeypatch):
    package, authorization = _real_package(tmp_path, monkeypatch)
    opener = FakeOllamaOpener(transport_errors={MODEL_IDS["SMALL_A"]: RuntimeError("adapter exploded")})
    adapters = FakeAdapters(opener=opener)
    budget = CombinedActionBudget()
    with pytest.raises(RuntimeError, match="adapter exploded"):
        run_static_a0_campaign(
            preregistration_root=package,
            authorization=authorization, owner_secret=OWNER_SECRET,
            adapters=adapters, evidence_root=tmp_path / "evidence", budget=budget,
        )
    assert budget.model_used == 1
    assert not (tmp_path / "evidence" / "call_journal.jsonl").read_text()

    resumed = FakeAdapters()
    with pytest.raises(ValueError, match="unsafe-to-retry"):
        run_static_a0_campaign(
            preregistration_root=package,
            authorization=authorization, owner_secret=OWNER_SECRET,
            adapters=resumed, evidence_root=tmp_path / "evidence",
            budget=CombinedActionBudget(),
        )
    assert sum(len(adapter.calls) for adapter in resumed.values()) == 0


def test_invalid_telemetry_after_transport_is_never_auto_retried(tmp_path, monkeypatch):
    package, authorization = _real_package(tmp_path, monkeypatch)
    def invalid(payload):
        payload["total_duration"] = float("nan")
    opener = FakeOllamaOpener(response_mutators={MODEL_IDS["SMALL_A"]: invalid})
    adapters = FakeAdapters(opener=opener)
    with pytest.raises(ValueError, match="non-finite"):
        run_static_a0_campaign(
            preregistration_root=package, authorization=authorization,
            owner_secret=OWNER_SECRET, adapters=adapters,
            evidence_root=tmp_path / "evidence", budget=CombinedActionBudget(),
        )
    assert sum(len(adapter.calls) for adapter in adapters.values()) == 1

    resumed = {key: FakeAdapter(value) for key, value in MODEL_IDS.items()}
    with pytest.raises(ValueError, match="unsafe-to-retry"):
        run_static_a0_campaign(
            preregistration_root=package, authorization=authorization,
            owner_secret=OWNER_SECRET, adapters=resumed,
            evidence_root=tmp_path / "evidence", budget=CombinedActionBudget(),
        )
    assert sum(len(adapter.calls) for adapter in resumed.values()) == 0


def test_missing_response_model_is_ambiguous_and_never_auto_retried(tmp_path, monkeypatch):
    package, authorization = _real_package(tmp_path, monkeypatch)

    def remove_model(payload):
        payload.pop("model")

    opener = FakeOllamaOpener(response_mutators={MODEL_IDS["SMALL_A"]: remove_model})
    adapters = FakeAdapters(opener=opener)
    budget = CombinedActionBudget()
    with pytest.raises(ValueError, match="model"):
        run_static_a0_campaign(
            preregistration_root=package, authorization=authorization,
            owner_secret=OWNER_SECRET, adapters=adapters,
            evidence_root=tmp_path / "evidence", budget=budget,
        )

    assert budget.model_used == 1
    assert sum(len(calls) for calls in opener.chat_calls.values()) == 1
    assert not (tmp_path / "evidence" / "call_journal.jsonl").read_text()
    attempts = _AttemptJournal(tmp_path / "evidence", OWNER_SECRET).read()
    assert [row["event"] for row in attempts] == ["STARTED", "AMBIGUOUS"]

    resumed_opener = FakeOllamaOpener()
    with pytest.raises(ValueError, match="unsafe-to-retry"):
        run_static_a0_campaign(
            preregistration_root=package, authorization=authorization,
            owner_secret=OWNER_SECRET, adapters=FakeAdapters(opener=resumed_opener),
            evidence_root=tmp_path / "evidence", budget=CombinedActionBudget(),
        )
    assert sum(len(calls) for calls in resumed_opener.chat_calls.values()) == 0


def test_missing_committed_marker_is_repaired_idempotently_from_signed_evidence(tmp_path):
    units = tuple(build_canonical_a0_plan().units)
    unit = units[0]
    cases = generate_hd_next2_cases("development", seed=20260921, per_region=1)
    cases_by_id = {case.case_id: case for case in cases}
    request = serialize_canonical_a0_request(
        cases_by_id[unit.case_id], MODEL_IDS[unit.model_key], unit.treatment_kind,
    )
    request_sha256 = hashlib.sha256(request).hexdigest()
    journal = _AttemptJournal(tmp_path, OWNER_SECRET)
    journal.append("STARTED", unit, MODEL_IDS[unit.model_key], request_sha256)
    journal.append("AMBIGUOUS", unit, MODEL_IDS[unit.model_key], request_sha256)
    committed = ({
        "unit_id": unit.unit_id,
        "physical_call_id": f"a0-call-{unit.unit_id}",
        "model": {"model_key": unit.model_key, "model_id": MODEL_IDS[unit.model_key]},
        "request": {"rendered_request_sha256": request_sha256},
    },)

    journal.reconcile(units, MODEL_IDS, cases_by_id, committed)
    journal.reconcile(units, MODEL_IDS, cases_by_id, committed)

    assert [row["event"] for row in journal.read()] == ["STARTED", "AMBIGUOUS", "COMMITTED"]


def test_committed_attempt_requires_exact_matching_signed_call_evidence(tmp_path):
    units = tuple(build_canonical_a0_plan().units)
    unit = units[0]
    cases = generate_hd_next2_cases("development", seed=20260921, per_region=1)
    cases_by_id = {case.case_id: case for case in cases}
    request = serialize_canonical_a0_request(
        cases_by_id[unit.case_id], MODEL_IDS[unit.model_key], unit.treatment_kind,
    )
    request_sha256 = hashlib.sha256(request).hexdigest()
    journal = _AttemptJournal(tmp_path, OWNER_SECRET)
    journal.append("STARTED", unit, MODEL_IDS[unit.model_key], request_sha256)
    journal.append("COMMITTED", unit, MODEL_IDS[unit.model_key], request_sha256)
    mismatched = ({
        "unit_id": unit.unit_id,
        "physical_call_id": "wrong",
        "model": {"model_key": unit.model_key, "model_id": MODEL_IDS[unit.model_key]},
        "request": {"rendered_request_sha256": request_sha256},
    },)

    with pytest.raises(ValueError, match="matching signed call evidence"):
        journal.reconcile(units, MODEL_IDS, cases_by_id, mismatched)


def test_existing_attempt_journal_without_signed_head_fails_closed(tmp_path):
    (tmp_path / "attempt_journal.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="signed head is missing"):
        _AttemptJournal(tmp_path, OWNER_SECRET)


@pytest.mark.parametrize("mutation", ["reorder", "duplicate_seq", "bad_previous_hash", "bad_hmac"])
def test_attempt_journal_rejects_chain_and_authentication_corruption(tmp_path, mutation):
    units = tuple(build_canonical_a0_plan().units)
    cases = generate_hd_next2_cases("development", seed=20260921, per_region=1)
    cases_by_id = {case.case_id: case for case in cases}
    journal = _AttemptJournal(tmp_path, OWNER_SECRET)
    for unit in units[:2]:
        request = serialize_canonical_a0_request(
            cases_by_id[unit.case_id], MODEL_IDS[unit.model_key], unit.treatment_kind,
        )
        journal.append("STARTED", unit, MODEL_IDS[unit.model_key], hashlib.sha256(request).hexdigest())
    rows = [json.loads(line) for line in journal.path.read_text(encoding="utf-8").splitlines()]
    if mutation == "reorder":
        rows.reverse()
    elif mutation == "duplicate_seq":
        rows[1]["seq"] = rows[0]["seq"]
    elif mutation == "bad_previous_hash":
        rows[1]["previous_row_sha256"] = "f" * 64
    else:
        rows[1]["attempt_hmac_sha256"] = "f" * 64
    journal.path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="attempt journal"):
        journal.read()


def test_noncanonical_adapter_request_is_rejected_before_reservation_or_call(tmp_path, monkeypatch):
    package, authorization = _real_package(tmp_path, monkeypatch)
    adapters = FakeAdapters()
    adapters["SMALL_A"].generation_options["seed"] = 1
    budget = CombinedActionBudget()
    with pytest.raises(ValueError, match="canonical serializer"):
        run_static_a0_campaign(
            preregistration_root=package,
            authorization=authorization, owner_secret=OWNER_SECRET,
            adapters=adapters, evidence_root=tmp_path / "evidence", budget=budget,
        )
    assert budget.model_used == 0
    assert sum(len(adapter.calls) for adapter in adapters.values()) == 0


def test_campaign_rejects_ollama_adapter_subclass_before_reservation(tmp_path, monkeypatch):
    class Subclass(OllamaChatAdapter):
        pass

    package, authorization = _real_package(tmp_path, monkeypatch)
    adapters = {key: FakeAdapter(value) for key, value in MODEL_IDS.items()}
    adapters["SMALL_A"] = Subclass(MODEL_IDS["SMALL_A"], opener=lambda *args, **kwargs: None)
    budget = CombinedActionBudget()
    with pytest.raises(ValueError, match="exact OllamaChatAdapter"):
        run_static_a0_campaign(
            preregistration_root=package, authorization=authorization,
            owner_secret=OWNER_SECRET, adapters=adapters,
            evidence_root=tmp_path / "evidence", budget=budget,
        )
    assert budget.model_used == 0


@pytest.mark.parametrize("replacement", [
    b'{"unit_id":"fake"}\n',
    b'{"unit_id":"x","unit_id":"y"}\n',
    b'{"execution_position":NaN}\n',
    b'[]\n',
])
def test_tampered_or_noncanonical_frozen_schedule_is_rejected_before_adapters(
    tmp_path, monkeypatch, replacement,
):
    package, authorization = _real_package(tmp_path, monkeypatch)
    (package / "frozen_schedule.jsonl").write_bytes(replacement)

    class ExplodingAdapters(dict):
        def __iter__(self): raise AssertionError("adapter accessed")
        def items(self): raise AssertionError("adapter accessed")
        def __getitem__(self, key): raise AssertionError("adapter accessed")

    with pytest.raises(ValueError, match="integrity"):
        run_static_a0_campaign(
            preregistration_root=package, authorization=authorization,
            owner_secret=OWNER_SECRET, adapters=ExplodingAdapters(),
            evidence_root=tmp_path / "evidence", budget=CombinedActionBudget(),
        )
    assert not (tmp_path / "evidence" / "call_journal.jsonl").exists()


@pytest.mark.parametrize("drift", ["version", "digest"])
def test_resume_rejects_ollama_provenance_drift_before_model_call(tmp_path, monkeypatch, drift):
    first, _, _ = _run(tmp_path, monkeypatch, stop_after=3)
    assert first["physical_model_calls"] == 3
    package = tmp_path / "preregistered"
    authorization = authorize_stage_execution(
        prepare_stage_authorization(package), owner_approved=True, owner_secret=OWNER_SECRET,
    )
    if drift == "version":
        opener = FakeOllamaOpener(version="0.12.4")
    else:
        rows = [json.loads(line) for line in (tmp_path / "evidence" / "call_journal.jsonl").read_text().splitlines()]
        changed_model = rows[0]["model"]["model_id"]
        tags = [
            {"name": model_id, "digest": ("sha256:changed" if model_id == changed_model else f"sha256:daemon-{key.lower()}")}
            for key, model_id in MODEL_IDS.items()
        ]
        opener = FakeOllamaOpener(tags=tags)
    budget = CombinedActionBudget()
    with pytest.raises(ValueError, match="provenance"):
        run_static_a0_campaign(
            preregistration_root=package, authorization=authorization,
            owner_secret=OWNER_SECRET, adapters=FakeAdapters(opener=opener),
            evidence_root=tmp_path / "evidence", budget=budget, stop_after=1,
        )
    assert budget.model_used == 0
    assert budget.non_model_used == 2
    assert "/api/chat" not in opener.calls
