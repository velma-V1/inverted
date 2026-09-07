from inverted.system_harvest.adapters.aider import ADAPTER as AIDER
from inverted.system_harvest.adapters.mini_swe_agent import ADAPTER as MINI_SWE
from inverted.system_harvest.adapters.swe_agent import ADAPTER as SWE


def _ids(adapter):
    return {item.artifact_id for item in adapter.descriptor.native_artifacts}


def test_swe_agent_preserves_full_trajectory_config_and_logs():
    assert {"swe.trajectory", "swe.config", "swe.logs"}.issubset(_ids(SWE))
    assert "trajectory" in SWE.descriptor.execution_modes


def test_mini_swe_agent_preserves_v2_trajectory_history_config_and_model_stats():
    assert {"mini_swe.trajectory", "mini_swe.config"}.issubset(_ids(MINI_SWE))
    channels = set(MINI_SWE.descriptor.declared_channels)
    assert {"MODEL_IO", "TOOL_IO", "RUNTIME_TELEMETRY"}.issubset(channels)


def test_aider_preserves_llm_chat_input_histories_repo_map_and_diffs():
    assert {
        "aider.llm_history", "aider.chat_history", "aider.input_history",
        "aider.repo_map", "aider.diff",
    }.issubset(_ids(AIDER))


def test_current_mini_swe_launch_uses_task_and_explicit_trajectory_output_flags():
    spec = MINI_SWE.descriptor.launch_specs[0]
    assert spec.argv[:2] == ("mini", "-t")
    assert "-p" not in spec.argv
    assert "-o" in spec.argv
    assert "{run_dir}/native/mini-swe-agent/trajectory.traj.json" in spec.argv


def test_current_swe_launch_pins_local_workspace_and_problem_text():
    spec = SWE.descriptor.launch_specs[0]
    assert "--env.repo.path={workspace}" in spec.argv
    assert "--problem_statement.text={task}" in spec.argv
