from .helpers import artifact, launch, make_adapter, surface


ADAPTER = make_adapter(
    system_id="Prime Agent", adapter_id="prime_agent", execution_modes=("rpc", "acp", "session"),
    native_artifacts=(
        artifact("prime.rpc_jsonl", "native/prime/rpc.jsonl", "jsonl"),
        artifact("prime.acp_jsonl", "native/prime/acp.jsonl", "jsonl", required=False),
        artifact("prime.session", "native/prime/session/**", "tree"),
        artifact("prime.stderr", "native/prime/stderr.log", "text"),
    ),
    native_surfaces=(
        surface("prime.rpc_events", ("MODEL_IO", "SYSTEM_EVENTS", "TOOL_IO", "CONTEXT_MEMORY", "FAILURE_RECOVERY", "DECISION_ALTERNATIVES", "VERIFICATION_RESULTS"),
                ("prime.rpc_jsonl", "prime.stderr"), description="Strict LF-delimited RPC commands, responses and streamed agent events."),
        surface("prime.session_state", ("CONTEXT_MEMORY", "STATE_TRANSITIONS"), ("prime.session",), phase="CHECKPOINT",
                description="Durable Prime Agent session state and resume artifacts."),
    ),
    discovery_hints=("prime-agent --version", "prime-agent --help", "prime-agent --mode rpc --help", "discover session directory"),
    source_refs=("https://github.com/PrimeIntellect-ai/prime-agent/blob/main/packages/coding-agent/docs/rpc.md", "https://github.com/PrimeIntellect-ai/prime-agent/blob/main/packages/coding-agent/docs/acp.md"),
    launch_specs=(
        launch("rpc", "prime-agent", "--mode", "rpc", "--session-dir", "{run_dir}/native/prime/session", output_format="jsonl"),
        launch("acp", "prime-agent", "--mode", "acp", output_format="jsonl"),
    ),
)
