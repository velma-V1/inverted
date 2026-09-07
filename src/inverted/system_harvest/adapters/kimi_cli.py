from .helpers import artifact, launch, make_adapter, surface


ADAPTER = make_adapter(
    system_id="Kimi CLI", adapter_id="kimi_cli", execution_modes=("stream_json", "hooks", "session", "wire"),
    native_artifacts=(
        artifact("kimi.hook_jsonl", "native/kimi/hooks.jsonl", "jsonl"),
        artifact("kimi.session", "native/kimi/session/**", "tree"),
        artifact("kimi.stream_json", "native/kimi/stream.jsonl", "jsonl"),
        artifact("kimi.stderr", "native/kimi/stderr.log", "text"),
        artifact("kimi.info", "native/kimi/info.json", "json"),
    ),
    native_surfaces=(
        surface("kimi.stream_events", ("MODEL_IO", "SYSTEM_EVENTS", "TOOL_IO", "CONTEXT_MEMORY", "FAILURE_RECOVERY", "DECISION_ALTERNATIVES"),
                ("kimi.stream_json", "kimi.stderr"), description="Print-mode stream-json messages/tool calls plus stderr progress and resume notices."),
        surface("kimi.hooks", ("SYSTEM_EVENTS", "TOOL_IO", "VERIFICATION_RESULTS", "FAILURE_RECOVERY", "STATE_TRANSITIONS"),
                ("kimi.hook_jsonl",), description="Lifecycle hooks including tool, stop, notification and context-compaction events."),
        surface("kimi.session_state", ("CONTEXT_MEMORY", "STATE_TRANSITIONS"), ("kimi.session", "kimi.info"), phase="CHECKPOINT",
                description="Session persistence, approval state, CLI/protocol version and context lifecycle."),
    ),
    discovery_hints=("kimi info --json", "kimi --help", "discover session storage", "enumerate configured hooks/MCP/agent specs"),
    source_refs=("https://github.com/MoonshotAI/kimi-cli/blob/main/docs/en/reference/kimi-command.md", "https://github.com/MoonshotAI/kimi-cli/blob/main/docs/en/customization/hooks.md"),
    launch_specs=(launch("stream_json", "kimi", "--print", "--prompt", "{task}", "--output-format", "stream-json", output_format="jsonl"),),
)
