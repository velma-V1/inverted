from .helpers import artifact, launch, make_adapter, surface


ADAPTER = make_adapter(
    system_id="OpenHands", adapter_id="openhands", execution_modes=("headless_json", "sdk_eventstream", "server_api", "conversation_state"),
    native_artifacts=(
        artifact("openhands.events", "native/openhands/events.jsonl", "jsonl"),
        artifact("openhands.state", "native/openhands/state.json", "json"),
        artifact("openhands.runtime", "native/openhands/runtime.jsonl", "jsonl"),
        artifact("openhands.activity", "native/openhands/activity.*", "json_or_csv", required=False),
    ),
    native_surfaces=(
        surface("openhands.eventstream", ("MODEL_IO", "SYSTEM_EVENTS", "TOOL_IO", "FAILURE_RECOVERY", "DECISION_ALTERNATIVES", "VERIFICATION_RESULTS", "STATE_TRANSITIONS"),
                ("openhands.events",), description="Headless JSONL/EventStream history including action, observation, message, error, confirmation and condensation events."),
        surface("openhands.state", ("CONTEXT_MEMORY", "STATE_TRANSITIONS", "SYSTEM_EVENTS"), ("openhands.state",), phase="CHECKPOINT",
                description="Conversation/agent state dump, status, confirmation policy, activated skills and persistence metadata."),
        surface("openhands.runtime", ("TOOL_IO", "PROCESS_IO", "FILESYSTEM_DIFFS", "RUNTIME_TELEMETRY"), ("openhands.runtime", "openhands.activity"),
                description="Runtime action execution/observation evidence and exported activity records."),
    ),
    discovery_hints=("openhands --version", "openhands --help", "freeze CLI/SDK version", "enumerate conversation event schema", "capture conversation state and runtime identity"),
    source_refs=("https://docs.openhands.dev/openhands/usage/cli/headless", "https://github.com/OpenHands/OpenHands-CLI"),
    launch_specs=(launch("headless_json", "openhands", "--headless", "--json", "-t", "{task}", output_format="jsonl"),),
)
