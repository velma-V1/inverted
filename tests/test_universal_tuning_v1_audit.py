import hashlib
import json

from inverted.universal_tuning.v1_audit import audit_v1_run


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def test_v1_audit_separates_semantic_and_contract_without_mutation(tmp_path):
    source = tmp_path / "observations.jsonl"
    rows = [
        {
            "trial_id": "r1", "family": "CLASSIFICATION_ROUTING",
            "case_id": "routing-validation", "stage": "validation",
            "profile": {"thinking_budget": 0, "temperature": 0.7},
            "response_text": '{"1":"UI","2":"AUTHORITY","3":"DEPENDENCY"}',
        },
        {
            "trial_id": "r2", "family": "SYSTEM_GOVERNANCE",
            "case_id": "governance-validation", "stage": "validation",
            "profile": {"thinking_budget": 0, "temperature": 0.7},
            "response_text": '{"answer":["REJECT","VERIFY_FIRST","PROCEED"]}',
        },
    ]
    write_rows(source, rows)
    before = source.read_bytes()
    result = audit_v1_run(tmp_path)
    assert source.read_bytes() == before
    assert result["source_sha256"] == hashlib.sha256(before).hexdigest()
    derived = [json.loads(line) for line in (tmp_path / "v1-derived-audit.jsonl").read_text().splitlines()]
    assert derived[0]["semantic_pass"] is True and derived[0]["contract_pass"] is False
    assert derived[1]["semantic_pass"] is True and derived[1]["contract_pass"] is True


def test_v1_audit_recovers_synthesis_semantics_and_partial_code(tmp_path):
    source = tmp_path / "observations.jsonl"
    rows = [
        {
            "trial_id": "s1", "family": "SYNTHESIS_WRITING",
            "case_id": "synthesis-validation", "stage": "validation",
            "profile": {"thinking_budget": 0, "temperature": 0.7},
            "response_text": json.dumps({"answer": [
                "Noor owns Wednesday with a limit of eight people.",
                "Dana owns a seven minute maintenance window at 04:15 UTC.",
                "Lee is the contact for Thursday delivery at bay 6.",
            ]}),
        },
        {
            "trial_id": "c1", "family": "CODING_GENERATION",
            "case_id": "coding-validation", "stage": "validation",
            "profile": {"thinking_budget": 256, "temperature": 0.6},
            "response_text": json.dumps({"answer": [
                "max(values, default=0)",
                "all(v > 0 for v in values)",
                "list(reversed(values))",
            ]}),
        },
    ]
    write_rows(source, rows)
    result = audit_v1_run(tmp_path)
    derived = [json.loads(line) for line in (tmp_path / "v1-derived-audit.jsonl").read_text().splitlines()]
    assert derived[0]["semantic_pass"] is True
    assert derived[0]["semantic_quality"] == 1.0
    assert derived[1]["semantic_pass"] is False
    assert derived[1]["semantic_quality"] == 2 / 3
    assert result["observation_count"] == 2
    summary = json.loads((tmp_path / "v1-derived-summary.json").read_text())
    assert summary["source_sha256"] == result["source_sha256"]
    assert summary["evaluator_sha256"]
