from .helpers import artifact, launch, make_adapter, surface


ADAPTER = make_adapter(
    system_id="SWE-agent", adapter_id="swe_agent", execution_modes=("trajectory", "replay", "batch"),
    native_artifacts=(
        artifact("swe.trajectory", "native/swe-agent/trajectories/*.traj", "json"),
        artifact("swe.config", "native/swe-agent/config/**", "tree"),
        artifact("swe.logs", "native/swe-agent/logs/**", "tree"),
        artifact("swe.results", "native/swe-agent/results.json", "json", required=False),
    ),
    native_surfaces=(
        surface("swe.trajectory", ("MODEL_IO", "SYSTEM_EVENTS", "TOOL_IO", "CONTEXT_MEMORY", "STATE_TRANSITIONS", "FAILURE_RECOVERY", "DECISION_ALTERNATIVES", "VERIFICATION_RESULTS"),
                ("swe.trajectory", "swe.logs"), description="Full thought/action/observation/response/state trajectory plus logs."),
        surface("swe.config", ("CONTEXT_MEMORY", "SOURCE_PROVENANCE"), ("swe.config",), phase="DISCOVER",
                description="Prompts, tools, model behavior and I/O configuration used for the trajectory."),
        surface("swe.results", ("VERIFICATION_RESULTS",), ("swe.results",), phase="EXPORT", required=False,
                description="Benchmark/evaluation result when available."),
    ),
    discovery_hints=("sweagent --version", "sweagent --help", "freeze YAML config and trajectory output directory"),
    source_refs=("https://swe-agent.com/latest/usage/trajectories/", "https://swe-agent.com/latest/usage/cli/"),
    launch_specs=(launch("trajectory", "sweagent", "run", "--config", "{config}", "--env.repo.path={workspace}", "--problem_statement.text={task}", output_format="trajectory"),),
)
