from .helpers import artifact, launch, make_adapter, surface


ADAPTER = make_adapter(
    system_id="Pi", adapter_id="pi", execution_modes=("rpc", "json", "session"),
    native_artifacts=(
        artifact("pi.rpc_jsonl", "native/pi/rpc.jsonl", "jsonl"),
        artifact("pi.json_events", "native/pi/events.jsonl", "jsonl", required=False),
        artifact("pi.session_jsonl", "native/pi/sessions/*.jsonl", "jsonl"),
        artifact("pi.stderr", "native/pi/stderr.log", "text"),
    ),
    native_surfaces=(
        surface("pi.rpc_events", ("MODEL_IO", "SYSTEM_EVENTS", "TOOL_IO", "CONTEXT_MEMORY", "FAILURE_RECOVERY", "DECISION_ALTERNATIVES", "VERIFICATION_RESULTS"),
                ("pi.rpc_jsonl", "pi.json_events", "pi.stderr"), description="RPC/JSON event stream including prompt, tool, state, compact, abort and follow-up activity."),
        surface("pi.session_state", ("CONTEXT_MEMORY", "STATE_TRANSITIONS"), ("pi.session_jsonl",), phase="CHECKPOINT",
                description="Native JSONL session persistence for exact continuation analysis."),
    ),
    discovery_hints=("pi --version", "pi --help", "pi --mode rpc --help", "discover Pi session directory and project trust state"),
    source_refs=("https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/rpc.md", "https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/security.md"),
    launch_specs=(
        launch("rpc", "pi", "--mode", "rpc", output_format="jsonl"),
        launch("json", "pi", "--mode", "json", "-p", "{task}", output_format="jsonl"),
    ),
)
