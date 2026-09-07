from .helpers import artifact, launch, make_adapter, surface


ADAPTER = make_adapter(
    system_id="Claude Code / Agent SDK", adapter_id="claude_code",
    execution_modes=("stream_json", "hooks", "session"),
    native_artifacts=(
        artifact("claude.hook_jsonl", "native/claude/hooks.jsonl", "jsonl"),
        artifact("claude.transcript", "native/claude/transcript*.jsonl", "jsonl"),
        artifact("claude.session", "native/claude/session/**", "tree"),
        artifact("claude.stream_json", "native/claude/stream.jsonl", "jsonl"),
    ),
    native_surfaces=(
        surface("claude.stream_events", ("MODEL_IO", "SYSTEM_EVENTS", "TOOL_IO", "FAILURE_RECOVERY", "DECISION_ALTERNATIVES"),
                ("claude.stream_json",), description="Verbose stream-json including partial messages and retry/system events."),
        surface("claude.hooks", ("TOOL_IO", "VERIFICATION_RESULTS", "FAILURE_RECOVERY", "STATE_TRANSITIONS"),
                ("claude.hook_jsonl",), description="Lifecycle hook stdin payloads, decisions and subagent events."),
        surface("claude.transcript_context", ("CONTEXT_MEMORY", "SYSTEM_EVENTS"),
                ("claude.transcript", "claude.session"), phase="CHECKPOINT", description="Main/subagent transcripts and session metadata."),
    ),
    discovery_hints=("claude --version", "claude --help", "discover transcript_path from SessionStart hook"),
    source_refs=("https://code.claude.com/docs/en/headless", "https://code.claude.com/docs/en/hooks"),
    launch_specs=(launch("stream_json", "claude", "-p", "{task}", "--output-format", "stream-json", "--verbose", "--include-partial-messages", output_format="jsonl"),),
)
