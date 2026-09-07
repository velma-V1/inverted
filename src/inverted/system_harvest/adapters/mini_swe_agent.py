from .helpers import artifact, launch, make_adapter, surface


ADAPTER = make_adapter(
    system_id="mini-SWE-agent", adapter_id="mini_swe_agent", execution_modes=("trajectory", "batch"),
    native_artifacts=(
        artifact("mini_swe.trajectory", "native/mini-swe-agent/*.traj.json", "json"),
        artifact("mini_swe.config", "native/mini-swe-agent/config.json", "json"),
        artifact("mini_swe.stderr", "native/mini-swe-agent/stderr.log", "text", required=False),
    ),
    native_surfaces=(
        surface("mini_swe.trajectory", ("MODEL_IO", "SYSTEM_EVENTS", "TOOL_IO", "CONTEXT_MEMORY", "STATE_TRANSITIONS", "FAILURE_RECOVERY", "DECISION_ALTERNATIVES", "VERIFICATION_RESULTS", "RUNTIME_TELEMETRY"),
                ("mini_swe.trajectory", "mini_swe.stderr"), description="Full v2 trajectory history including messages, configuration, metadata, cost and API-call statistics."),
        surface("mini_swe.config", ("CONTEXT_MEMORY", "SOURCE_PROVENANCE"), ("mini_swe.config",), phase="DISCOVER",
                description="Frozen agent/model/environment configuration."),
    ),
    discovery_hints=("mini --help", "inspect mini-SWE-agent version", "freeze trajectory format/config/output path before run"),
    source_refs=("https://mini-swe-agent.com/latest/reference/run/mini/", "https://mini-swe-agent.com/latest/usage/output_files/"),
    launch_specs=(launch("trajectory", "mini", "-t", "{task}", "-o", "{run_dir}/native/mini-swe-agent/trajectory.traj.json", output_format="trajectory"),),
)
