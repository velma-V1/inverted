from __future__ import annotations

import httpx

from inverted.test2_metadata import enrich_test2_evidence
from inverted.test2_provenance import collect_ollama_provenance


def _evidence():
    trials = []
    for model in ("m1", "m2"):
        trials += [
            {"phase":"formalization","role":"formalizer","task_id":"f","evaluation_id":"F","family":"state","complexity":1,"representation":"natural","model":model,"success":model=="m1"},
            {"phase":"execution","role":"executor","task_id":"e","evaluation_id":"E","family":"policy","complexity":4,"model":model,"success":model=="m2"},
            {"phase":"auditing","role":"auditor","task_id":"ag","evaluation_id":"AG","family":"state","complexity":2,"fault":"none","model":model,"success":True,"gold_accept":True,"accept":True},
            {"phase":"auditing","role":"auditor","task_id":"ab","evaluation_id":"AB","family":"policy","complexity":4,"fault":"wrong_value","model":model,"success":model=="m1","gold_accept":False,"accept":False if model=="m1" else True},
            {"phase":"repair_factorial","role":"repairer","task_id":"r","evaluation_id":"R1","family":"policy","complexity":4,"fault":"wrong_value","model":model,"feedback_style":"raw","strategy":"regenerate","success":False,"preservation_rate":0.5,"new_failures_introduced":1},
            {"phase":"repair_factorial","role":"repairer","task_id":"r","evaluation_id":"R2","family":"policy","complexity":4,"fault":"wrong_value","model":model,"feedback_style":"structured","strategy":"targeted","success":True,"preservation_rate":1.0,"new_failures_introduced":0},
        ]
    for task_id, seq in {"h1":[False,True,True,True,True],"h2":[True,True,False,True,True]}.items():
        for pipeline, success in zip(("S0_BEST_SINGLE_ALL_ROLES","S1_SPECIALIZE_FORMALIZER","S2_SPECIALIZE_FORMALIZER_EXECUTOR","S3_SPECIALIZE_FORMALIZER_EXECUTOR_REPAIR","S4_FULL_SPECIALIZATION"), seq):
            trials.append({"phase":"progressive_holdout","role":"pipeline","task_id":task_id,"evaluation_id":f"{task_id}-{pipeline}","pipeline":pipeline,"model":"layered","success":success})
    calls = [
        {"call_identity":"c1","model":"m1","role":"formalizer","phase":"formalization","task_id":"f","cache_hit":False,"latency_s":1.2,"input_tokens":10,"output_tokens":5,"total_tokens":15,"load_duration_s":0.4,"prompt_eval_duration_s":0.2,"eval_duration_s":0.5},
        {"call_identity":"c2","model":"m2","role":"executor","phase":"execution","task_id":"e","cache_hit":False,"latency_s":0.8,"input_tokens":12,"output_tokens":4,"total_tokens":16,"load_duration_s":0.1,"prompt_eval_duration_s":0.2,"eval_duration_s":0.4},
    ]
    return {
        "master_index":{"mode":"local","run_id":"x","physical_model_calls":2,"hard_call_limit":480},
        "raw":{"trials":trials,"model_calls":calls,"prompts":[{"call_identity":"c1","serialized":"safe"},{"call_identity":"c2","serialized":"safe2"}],"responses":[{"call_identity":"c1","text":"{}"},{"call_identity":"c2","text":"{}"}],"candidates":[],"events":[],"validator_results":[{"stage":"final_deterministic_authority","deterministic_success":True,"hidden_gold_success":True}],"repairs":[]},
        "effects":{},"order":{},"models":{},"thresholds":{},
        "provenance":{"config":{"local":{"models":["m1","m2"]}},"environment":{},"git":{},"models":{}},
    }


def test_enrichment_derives_high_value_metadata_and_confidence_intervals_without_inference():
    evidence = _evidence()
    enrich_test2_evidence(evidence)
    assert evidence["models"]["auditor_confusion"]
    assert evidence["models"]["balanced_role_scores"]
    assert evidence["models"]["layered_capability_family"]
    assert evidence["models"]["model_efficiency"]
    assert evidence["effects"]["repair_factorial_summary"]
    assert evidence["effects"]["progressive_model_compounding"]
    assert evidence["effects"]["system_decision_confusion"]
    assert evidence["diagnostics"]["contamination_audit"]["forbidden_prompt_marker_hits"] == []
    assert evidence["diagnostics"]["call_lineage"]
    assert evidence["diagnostics"]["matrix_coverage"]
    assert all("ci95_low" in row and "ci95_high" in row for row in evidence["models"]["layered_capability_family"])


def test_contamination_audit_detects_hidden_label_leak_and_hashes_prompt_response():
    evidence = _evidence()
    evidence["raw"]["prompts"][0]["serialized"] = '{"hidden_gold_success":true}'
    enrich_test2_evidence(evidence)
    assert evidence["diagnostics"]["contamination_audit"]["forbidden_prompt_marker_hits"]
    lineage = evidence["diagnostics"]["call_lineage"]
    assert all(len(row["prompt_sha256"]) == 64 and len(row["response_sha256"]) == 64 for row in lineage)


def test_ollama_provenance_uses_only_zero_inference_endpoints():
    seen = []
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version":"1.2.3"})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models":[{"name":"m1","digest":"abc","size":123,"details":{"quantization_level":"Q8_0"}}]})
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models":[]})
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"details":{"family":"qwen"},"model_info":{"x":1},"capabilities":["completion"]})
        raise AssertionError(request.url.path)
    transport = httpx.MockTransport(handler)
    result = collect_ollama_provenance("http://test", ["m1"], transport=transport)
    assert result["server_version"] == "1.2.3"
    assert result["models"]["m1"]["tag_digest"] == "abc"
    assert all(path != "/api/chat" and path != "/api/generate" for _, path in seen)
