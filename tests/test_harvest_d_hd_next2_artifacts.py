import hashlib
import json

import pytest

from inverted.harvest_d.hd_next2.artifacts import CALL_PROJECTIONS, EvidenceWriter
from inverted.harvest_d.hd_next2.cases import generate_hd_next2_cases
from inverted.harvest_d.hd_next2.rendering import render_hd_next1_historical_seed
from inverted.harvest_d.hd_next2.stages import build_canonical_a0_plan


REQUIRED = {
    "raw_model_requests.jsonl", "raw_model_responses.jsonl", "rendered_layers.jsonl",
    "normalized_model_calls.jsonl", "runtime_telemetry.jsonl", "physical_call_ledger.jsonl",
    "campaign_journal.jsonl", "scheduler_ledger.jsonl", "coverage_events.jsonl",
    "action_budget_state.jsonl", "call_journal.jsonl",
}


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _canonical_historical_seed_bytes(case_id):
    cases = generate_hd_next2_cases("development", seed=20260921, per_region=1)
    case = next(item for item in cases if item.case_id == case_id)
    system, user, metadata = render_hd_next1_historical_seed(case)
    payload = {"system": system, "user": user, "metadata": metadata}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _complete_call(*, treatment_kind="HISTORICAL_SEED", physical_call_id="pc-1"):
    unit = next(item for item in build_canonical_a0_plan().units if item.treatment_kind == treatment_kind)
    request_bytes = b'{"messages":[{"role":"user","content":"exact"}]}'
    support = _canonical_historical_seed_bytes(unit.case_id)
    schedule = {
        key: getattr(unit, key) for key in (
            "case_id", "partition", "operating_region", "model_key", "treatment_kind",
            "treatment_spec_id", "treatment_spec_sha256", "replicate", "execution_position",
            "model_role", "eligible_for_recipe", "model_block", "selection_reason",
            "max_attempts", "retry_of_unit_id",
        )
    }
    schedule.update(admissible_unexplored_neighbors=[], protected_exploration=False)
    return {
        "unit_id": unit.unit_id,
        "physical_call_id": physical_call_id,
        "model": {
            "model_key": unit.model_key, "model_id": "qwen-test-id",
            "model_digest": "sha256:model-digest", "runtime_identity": "ollama-test-runtime",
        },
        "request": {
            "rendered_request_bytes": request_bytes,
            "rendered_request_sha256": hashlib.sha256(request_bytes).hexdigest(),
        },
        "response": {"raw_response": "raw provider response"},
        "rendered_layers": ([] if treatment_kind == "RAW" else [{
            "layer_index": 0, "ingredient_id": "HD_NEXT_1_HISTORICAL_SEED",
            "formulation_id": "ADMISSIBLE_ACTION_MATRIX", "dose_id": "MINIMUM",
            "rendered_bytes": support, "sha256": hashlib.sha256(support).hexdigest(),
        }]),
        "normalized": {
            "candidate": {"answer": "A"}, "normalized_answer": "A", "correctness": True,
        },
        "verification": {
            "oracle_result": "A", "verifier_result": "PASS", "failure_taxonomy": [],
        },
        "schedule": schedule,
        "telemetry": {
            "input_tokens": 12, "output_tokens": 3, "total_duration": 44,
            "load_duration": 11, "prompt_eval_duration": 22, "eval_duration": 33,
            "done_reason": "stop",
        },
    }


def test_writer_creates_required_ledgers_and_manual_append_is_strict_and_append_only(tmp_path):
    writer = EvidenceWriter(tmp_path)
    assert {p.name for p in tmp_path.iterdir()} == REQUIRED
    writer.append("campaign_journal", {"event": "first"})
    EvidenceWriter(tmp_path).append("campaign_journal", {"event": "second"})
    assert _rows(tmp_path / "campaign_journal.jsonl") == [{"event": "first"}, {"event": "second"}]
    before = (tmp_path / "campaign_journal.jsonl").read_bytes()
    for malformed in ({"value": float("nan")}, {"value": float("inf")}, {"value": object()}):
        with pytest.raises((TypeError, ValueError)):
            writer.append("campaign_journal", malformed)
        assert (tmp_path / "campaign_journal.jsonl").read_bytes() == before


def test_generic_append_cannot_bypass_authoritative_call_journal(tmp_path):
    writer = EvidenceWriter(tmp_path)
    with pytest.raises(ValueError, match="write_call"):
        writer.append("physical_call_ledger", {"unit_id": "u", "physical_call_id": "p"})


def test_complete_call_preserves_full_a0_reanalysis_provenance(tmp_path):
    call = _complete_call()
    EvidenceWriter(tmp_path).write_call(call)
    journal = _rows(tmp_path / "call_journal.jsonl")[0]
    for key in ("model", "request", "response", "rendered_layers", "normalized", "verification", "schedule", "telemetry"):
        assert journal[key]
    assert journal["request"]["rendered_request_bytes_hex"] == call["request"]["rendered_request_bytes"].hex()
    assert journal["normalized"]["normalized_answer"] == "A"
    assert journal["normalized"]["correctness"] is True
    assert journal["verification"]["verifier_result"] == "PASS"
    assert journal["schedule"]["treatment_spec_sha256"] == call["schedule"]["treatment_spec_sha256"]


@pytest.mark.parametrize("provenance_class", ["model", "request", "response", "rendered_layers", "normalized", "verification", "schedule", "telemetry"])
def test_writer_rejects_missing_required_provenance_class_before_first_write(tmp_path, provenance_class):
    writer = EvidenceWriter(tmp_path)
    call = _complete_call()
    call.pop(provenance_class)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises((TypeError, ValueError), match=provenance_class):
        writer.write_call(call)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize(
    ("section", "field", "bad"),
    [
        ("model", "model_digest", 1), ("request", "rendered_request_bytes", "text"),
        ("response", "raw_response", None), ("normalized", "correctness", "true"),
        ("verification", "failure_taxonomy", "NONE"), ("schedule", "replicate", "1"),
        ("schedule", "replicate", True), ("verification", "oracle_result", None),
        ("telemetry", "input_tokens", 1.5),
    ],
)
def test_writer_rejects_malformed_provenance_types_before_first_write(tmp_path, section, field, bad):
    writer = EvidenceWriter(tmp_path)
    call = _complete_call()
    call[section][field] = bad
    with pytest.raises((TypeError, ValueError), match=field):
        writer.write_call(call)
    assert not (tmp_path / "call_journal.jsonl").read_bytes()


def test_writer_rejects_schedule_values_not_matching_canonical_a0_unit(tmp_path):
    writer = EvidenceWriter(tmp_path)
    call = _complete_call()
    call["schedule"]["case_id"] = "forged-case"
    with pytest.raises(ValueError, match="canonical A0 schedule"):
        writer.write_call(call)
    assert not (tmp_path / "call_journal.jsonl").read_bytes()


def test_raw_accepts_zero_support_layers_but_preserves_exact_request_bytes(tmp_path):
    call = _complete_call(treatment_kind="RAW")
    EvidenceWriter(tmp_path).write_call(call)
    journal = _rows(tmp_path / "call_journal.jsonl")[0]
    assert journal["rendered_layers"] == []
    assert journal["request"]["rendered_request_sha256"] == hashlib.sha256(call["request"]["rendered_request_bytes"]).hexdigest()


def test_non_raw_rejects_empty_support_layers(tmp_path):
    writer = EvidenceWriter(tmp_path)
    call = _complete_call()
    call["rendered_layers"] = []
    with pytest.raises(ValueError, match="HISTORICAL_SEED"):
        writer.write_call(call)
    assert not (tmp_path / "call_journal.jsonl").read_bytes()


def test_reconcile_repairs_injected_secondary_failure_without_reexecution(tmp_path, monkeypatch):
    writer = EvidenceWriter(tmp_path)
    call = _complete_call()
    original = writer._append_encoded
    failed = False

    def fail_once(ledger, encoded):
        nonlocal failed
        if ledger == "runtime_telemetry" and not failed:
            failed = True
            raise OSError("injected secondary failure")
        original(ledger, encoded)

    monkeypatch.setattr(writer, "_append_encoded", fail_once)
    with pytest.raises(OSError, match="injected"):
        writer.write_call(call)
    assert len(_rows(tmp_path / "call_journal.jsonl")) == 1
    monkeypatch.setattr(writer, "_append_encoded", original)
    repaired = writer.reconcile_projections()
    assert repaired > 0
    assert len(_rows(tmp_path / "runtime_telemetry.jsonl")) == 1
    assert len(_rows(tmp_path / "physical_call_ledger.jsonl")) == 1
    assert len(_rows(tmp_path / "call_journal.jsonl")) == 1


def test_reconcile_is_idempotent_and_does_not_duplicate_correct_rows(tmp_path):
    writer = EvidenceWriter(tmp_path)
    writer.write_call(_complete_call())
    before = {name: (tmp_path / name).read_bytes() for name in REQUIRED if name.endswith(".jsonl")}
    assert writer.reconcile_projections() == 0
    after = {name: (tmp_path / name).read_bytes() for name in REQUIRED if name.endswith(".jsonl")}
    assert after == before


def test_writer_rejects_reused_unit_or_physical_call_identity(tmp_path):
    writer = EvidenceWriter(tmp_path)
    writer.write_call(_complete_call())
    duplicate_physical = _complete_call(treatment_kind="RAW", physical_call_id="pc-1")
    duplicate_unit = _complete_call(physical_call_id="pc-2")
    for call in (duplicate_physical, duplicate_unit):
        with pytest.raises(ValueError, match="already committed"):
            writer.write_call(call)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("ingredient_id", "OBJECTIVE"),
        ("formulation_id", "RAW_PROSE"),
        ("dose_id", "FULL"),
        ("rendered_bytes", b"forged historical support"),
    ],
)
def test_historical_seed_support_is_bound_to_canonical_renderer(tmp_path, field, bad):
    writer = EvidenceWriter(tmp_path)
    call = _complete_call()
    layer = call["rendered_layers"][0]
    layer[field] = bad
    if field == "rendered_bytes":
        layer["sha256"] = hashlib.sha256(bad).hexdigest()
    with pytest.raises(ValueError, match="canonical historical seed"):
        writer.write_call(call)
    assert not (tmp_path / "call_journal.jsonl").read_bytes()


def test_reconcile_revalidates_parseable_journal_before_reprojection(tmp_path):
    writer = EvidenceWriter(tmp_path)
    writer.write_call(_complete_call())
    journal = _rows(tmp_path / "call_journal.jsonl")[0]
    journal["schedule"]["case_id"] = "forged-case"

    (tmp_path / "call_journal.jsonl").write_text(
        json.dumps(journal, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    for ledger in CALL_PROJECTIONS:
        (tmp_path / f"{ledger}.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="authoritative call journal"):
        writer.reconcile_projections()


def test_reconcile_rejects_duplicate_authoritative_journal_identity(tmp_path):
    writer = EvidenceWriter(tmp_path)
    writer.write_call(_complete_call())
    line = (tmp_path / "call_journal.jsonl").read_text(encoding="utf-8")
    (tmp_path / "call_journal.jsonl").write_text(line + line, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate authoritative"):
        writer.reconcile_projections()


def test_reconcile_rejects_orphan_projection_rows(tmp_path):
    writer = EvidenceWriter(tmp_path)
    writer.write_call(_complete_call())
    with (tmp_path / "physical_call_ledger.jsonl").open("a", encoding="utf-8") as stream:
        stream.write('{"physical_call_id":"orphan-p","status":"COMPLETED","unit_id":"orphan-u"}\n')
    with pytest.raises(ValueError, match="orphan"):
        writer.reconcile_projections()


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_reconcile_rejects_nonfinite_json_constants_on_read(tmp_path, constant):
    writer = EvidenceWriter(tmp_path)
    writer.write_call(_complete_call())
    with (tmp_path / "runtime_telemetry.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(
            '{"physical_call_id":"orphan-p","unit_id":"orphan-u","value":' + constant + '}\n'
        )
    with pytest.raises(ValueError, match="runtime_telemetry is malformed"):
        writer.reconcile_projections()



@pytest.mark.parametrize(
    "section",
    ["model", "request", "response", "normalized", "verification", "schedule", "telemetry"],
)
def test_writer_rejects_unsigned_extra_fields_in_evidence_sections(tmp_path, section):
    writer = EvidenceWriter(tmp_path)
    call = _complete_call()
    call[section]["unsigned_extra"] = "smuggled"
    with pytest.raises(ValueError, match="exact schema"):
        writer.write_call(call)
    assert not (tmp_path / "call_journal.jsonl").read_bytes()


def test_writer_rejects_unsigned_extra_top_level_and_layer_fields(tmp_path):
    writer = EvidenceWriter(tmp_path)
    top = _complete_call()
    top["unsigned_extra"] = True
    with pytest.raises(ValueError, match="exact schema"):
        writer.write_call(top)
    layer = _complete_call()
    layer["rendered_layers"][0]["unsigned_extra"] = True
    with pytest.raises(ValueError, match="exact schema"):
        writer.write_call(layer)
    assert not (tmp_path / "call_journal.jsonl").read_bytes()



def test_reconcile_rejects_duplicate_key_in_authoritative_journal(tmp_path):
    writer = EvidenceWriter(tmp_path)
    writer.write_call(_complete_call())
    path = tmp_path / "call_journal.jsonl"
    line = path.read_text(encoding="utf-8").strip()
    unit_id = json.loads(line)["unit_id"]
    path.write_text(line[:-1] + ',"unit_id":' + json.dumps(unit_id) + '}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="malformed|duplicate"):
        writer.reconcile_projections()


def test_reconcile_rejects_duplicate_key_in_projection_jsonl(tmp_path):
    writer = EvidenceWriter(tmp_path)
    writer.write_call(_complete_call())
    path = tmp_path / "runtime_telemetry.jsonl"
    line = path.read_text(encoding="utf-8").strip()
    tokens = json.loads(line)["input_tokens"]
    path.write_text(line[:-1] + ',"input_tokens":' + json.dumps(tokens) + '}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="malformed|duplicate"):
        writer.reconcile_projections()
