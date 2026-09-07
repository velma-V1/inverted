from .helpers import artifact, launch, make_adapter, surface


ADAPTER = make_adapter(
    system_id="oh-my-cli", adapter_id="oh_my_cli", execution_modes=("json", "resume", "evidence_export"),
    native_artifacts=(
        artifact("ohmy.session_jsonl", "native/oh-my-cli/sessions/*.jsonl", "jsonl"),
        artifact("ohmy.event_jsonl", "native/oh-my-cli/events.jsonl", "jsonl"),
        artifact("ohmy.evidence_archive", "native/oh-my-cli/evidence/**", "tree"),
        artifact("ohmy.checkpoints", "native/oh-my-cli/checkpoints/**", "tree", required=False),
        artifact("ohmy.scorecard", "native/oh-my-cli/*scorecard*.json", "json", required=False),
    ),
    native_surfaces=(
        surface("ohmy.events", ("MODEL_IO", "SYSTEM_EVENTS", "TOOL_IO", "CONTEXT_MEMORY", "FAILURE_RECOVERY", "VERIFICATION_RESULTS", "DECISION_ALTERNATIVES"),
                ("ohmy.event_jsonl", "ohmy.session_jsonl"), description="Versioned event stream plus durable resumable JSONL session."),
        surface("ohmy.governance", ("SYSTEM_EVENTS", "TOOL_IO", "VERIFICATION_RESULTS", "FAILURE_RECOVERY", "DECISION_ALTERNATIVES"),
                ("ohmy.evidence_archive", "ohmy.scorecard"), description="Policy, approval, provider/tool/MCP gates, summaries and evidence exports."),
        surface("ohmy.checkpoints", ("CONTEXT_MEMORY", "STATE_TRANSITIONS"), ("ohmy.checkpoints",), phase="CHECKPOINT", required=False,
                description="Native checkpoint/recovery artifacts when emitted."),
    ),
    discovery_hints=("oh-my-cli --version", "oh-my-cli --help", "oh-my-cli --browse-sessions", "discover session/evidence export locations"),
    source_refs=("https://github.com/qwen-code-dev-bot/oh-my-cli",),
    launch_specs=(launch("json", "oh-my-cli", "-p", "{task}", "--output", "json", output_format="json"),),
)
