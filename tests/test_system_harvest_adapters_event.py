from inverted.system_harvest.adapters.aegisevo import ADAPTER as AEGISEVO
from inverted.system_harvest.adapters.base import EvidenceOrigin
from inverted.system_harvest.adapters.claude_code import ADAPTER as CLAUDE
from inverted.system_harvest.adapters.openhands import ADAPTER as OPENHANDS


def _ids(adapter):
    return {item.artifact_id for item in adapter.descriptor.native_artifacts}


def test_claude_code_preserves_hooks_transcript_and_session_metadata():
    assert {"claude.hook_jsonl", "claude.transcript", "claude.session"}.issubset(_ids(CLAUDE))
    assert any("hook" in surface.surface_id for surface in CLAUDE.descriptor.surfaces)


def test_openhands_preserves_eventstream_state_runtime_and_has_headless_json_launch():
    assert {"openhands.events", "openhands.state", "openhands.runtime"}.issubset(_ids(OPENHANDS))
    channels = set(OPENHANDS.descriptor.declared_channels)
    assert {"SYSTEM_EVENTS", "TOOL_IO", "STATE_TRANSITIONS"}.issubset(channels)
    spec = OPENHANDS.descriptor.launch_specs[0]
    assert spec.argv == ("openhands", "--headless", "--json", "-t", "{task}")
    assert spec.output_format == "jsonl"


def test_aegisevo_preserves_deterministic_demo_and_live_gateway_model_io():
    assert {"aegisevo.evidence", "aegisevo.lineage", "aegisevo.telemetry", "aegisevo.model_gateway_jsonl"}.issubset(_ids(AEGISEVO))
    model_surfaces = [s for s in AEGISEVO.descriptor.surfaces if "MODEL_IO" in s.evidence_channels]
    assert any(s.origin is EvidenceOrigin.INSTRUMENTED for s in model_surfaces)
    spec = AEGISEVO.descriptor.launch_specs[0]
    assert spec.argv[:6] == ("cargo", "run", "-p", "aegisevo-cli", "--", "demo")
    assert "--seed" in spec.argv and "17" in spec.argv
    assert "--output" in spec.argv
