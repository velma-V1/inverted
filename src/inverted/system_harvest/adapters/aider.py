from .helpers import artifact, launch, make_adapter, surface


ADAPTER = make_adapter(
    system_id="Aider", adapter_id="aider", execution_modes=("message", "history", "repo_map"),
    native_artifacts=(
        artifact("aider.llm_history", "native/aider/llm.history", "text"),
        artifact("aider.chat_history", "native/aider/chat.history.md", "markdown"),
        artifact("aider.input_history", "native/aider/input.history", "text"),
        artifact("aider.repo_map", "native/aider/repo-map.txt", "text", required=False),
        artifact("aider.diff", "native/aider/diff.patch", "patch"),
        artifact("aider.config", "native/aider/config.json", "json"),
    ),
    native_surfaces=(
        surface("aider.llm_chat", ("MODEL_IO", "SYSTEM_EVENTS", "CONTEXT_MEMORY", "FAILURE_RECOVERY", "DECISION_ALTERNATIVES"),
                ("aider.llm_history", "aider.chat_history", "aider.input_history"), description="LLM, chat and input histories preserved independently."),
        surface("aider.repo_context", ("CONTEXT_MEMORY", "SOURCE_PROVENANCE"), ("aider.repo_map", "aider.config"), phase="CHECKPOINT",
                description="Repository map/context budget/configuration used to select code context."),
        surface("aider.edits", ("TOOL_IO", "STATE_TRANSITIONS", "VERIFICATION_RESULTS"), ("aider.diff",),
                description="Exact repository diff plus edit/lint/test outcomes referenced from chat history."),
    ),
    discovery_hints=("aider --version", "aider --help", "freeze aider config/model metadata and history paths", "capture repo-map token policy"),
    source_refs=("https://github.com/Aider-AI/aider/blob/main/aider/website/docs/config/aider_conf.md", "https://github.com/Aider-AI/aider/blob/main/aider/website/docs/repomap.md"),
    launch_specs=(launch("message", "aider", "--message", "{task}", "--llm-history-file", "{run_dir}/native/aider/llm.history", "--chat-history-file", "{run_dir}/native/aider/chat.history.md", output_format="text"),),
)
