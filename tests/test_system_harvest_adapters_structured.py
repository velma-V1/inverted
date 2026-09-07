from inverted.system_harvest.adapters.base import EvidenceOrigin
from inverted.system_harvest.adapters.codex import ADAPTER as CODEX
from inverted.system_harvest.adapters.kimi_cli import ADAPTER as KIMI
from inverted.system_harvest.adapters.oh_my_cli import ADAPTER as OH_MY
from inverted.system_harvest.adapters.pi import ADAPTER as PI
from inverted.system_harvest.adapters.prime_agent import ADAPTER as PRIME


def _artifact_ids(adapter):
    return {item.artifact_id for item in adapter.descriptor.native_artifacts}


def test_codex_preserves_jsonl_and_session_surfaces():
    assert {"codex.exec_jsonl", "codex.session"}.issubset(_artifact_ids(CODEX))
    assert "exec_jsonl" in CODEX.descriptor.execution_modes
    assert any(surface.origin is EvidenceOrigin.NATIVE for surface in CODEX.descriptor.surfaces)


def test_prime_and_pi_preserve_rpc_jsonl_and_session_state():
    assert {"prime.rpc_jsonl", "prime.session"}.issubset(_artifact_ids(PRIME))
    assert {"rpc", "acp"}.issubset(PRIME.descriptor.execution_modes)
    assert {"pi.rpc_jsonl", "pi.session_jsonl"}.issubset(_artifact_ids(PI))
    assert {"rpc", "json"}.issubset(PI.descriptor.execution_modes)


def test_oh_my_cli_preserves_durable_session_event_and_evidence_exports():
    ids = _artifact_ids(OH_MY)
    assert {"ohmy.session_jsonl", "ohmy.event_jsonl", "ohmy.evidence_archive"}.issubset(ids)
    assert {"json", "resume"}.issubset(OH_MY.descriptor.execution_modes)


def test_kimi_preserves_hook_lifecycle_and_session_artifacts():
    ids = _artifact_ids(KIMI)
    assert {"kimi.hook_jsonl", "kimi.session"}.issubset(ids)
    assert any("hook" in surface.surface_id for surface in KIMI.descriptor.surfaces)


def test_structured_adapters_preserve_fixture_payloads_losslessly():
    payload = {"type": "tool_event", "tool": {"name": "read", "args": {"path": "x"}}, "seq": 9}
    for adapter in (CODEX, PRIME, PI, OH_MY, KIMI):
        record = adapter.ingest_native_record(payload, source_path="fixture.jsonl", ordinal=9)
        assert record.payload == payload
        assert record.origin is EvidenceOrigin.NATIVE


def test_current_oh_my_cli_headless_launch_uses_confirmed_prompt_and_json_output_flags():
    spec = OH_MY.descriptor.launch_specs[0]
    assert spec.argv == ("oh-my-cli", "-p", "{task}", "--output", "json")
