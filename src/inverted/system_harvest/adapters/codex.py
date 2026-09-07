from .helpers import artifact, launch, make_adapter, surface


ADAPTER = make_adapter(
    system_id="Codex", adapter_id="codex", execution_modes=("exec_jsonl", "session"),
    native_artifacts=(
        artifact("codex.exec_jsonl", "native/codex/exec.jsonl", "jsonl"),
        artifact("codex.session", "native/codex/session/**", "tree"),
        artifact("codex.stderr", "native/codex/stderr.log", "text"),
    ),
    native_surfaces=(
        surface("codex.events", ("MODEL_IO", "SYSTEM_EVENTS", "TOOL_IO", "FAILURE_RECOVERY", "VERIFICATION_RESULTS", "DECISION_ALTERNATIVES"),
                ("codex.exec_jsonl", "codex.stderr"), description="Lossless codex exec --json event stream and diagnostics."),
        surface("codex.context_session", ("CONTEXT_MEMORY",), ("codex.session",), phase="CHECKPOINT",
                description="Persisted Codex session/rollout artifacts and context lineage."),
    ),
    discovery_hints=("codex --version", "codex exec --help", "discover CODEX_HOME and persisted session paths"),
    source_refs=("https://github.com/openai/codex", "https://github.com/openai/codex/issues/35415"),
    launch_specs=(launch("exec_jsonl", "codex", "exec", "--json", "-C", "{workspace}", "-", output_format="jsonl"),),
)
