from inverted.system_harvest.adapters.registry import ADAPTER_IDS, adapter_by_id, all_adapters
from inverted.system_harvest.drivers.base import DriverFamily, ResumeCapability
from inverted.system_harvest.drivers.registry import (
    all_drivers,
    driver_by_adapter_id,
    validate_driver_registry,
)


def test_driver_registry_matches_frozen_adapter_registry_exactly():
    drivers = all_drivers()
    assert tuple(driver.descriptor.adapter_id for driver in drivers) == ADAPTER_IDS
    assert len(drivers) == 11
    report = validate_driver_registry(all_adapters(), drivers)
    assert report.valid
    assert report.blockers == ()


def test_every_driver_declares_real_adapter_mode_resume_and_artifact_watchers():
    for driver in all_drivers():
        descriptor = driver.descriptor
        adapter = adapter_by_id(descriptor.adapter_id)
        assert descriptor.task_mode_id in adapter.descriptor.execution_modes
        assert isinstance(descriptor.family, DriverFamily)
        assert isinstance(descriptor.resume_capability, ResumeCapability)
        assert descriptor.artifact_watch_patterns
        assert set(descriptor.artifact_watch_patterns) == {
            (item.artifact_id, item.pattern) for item in adapter.descriptor.native_artifacts
        }
        assert driver.declared_launch_spec(adapter).mode_id == descriptor.task_mode_id


def test_driver_families_cover_all_six_execution_shapes():
    families = {driver.descriptor.family for driver in all_drivers()}
    assert families == set(DriverFamily)


def test_aegisevo_preserves_deterministic_and_instrumented_live_distinction():
    descriptor = driver_by_adapter_id("aegisevo").descriptor
    assert descriptor.task_mode_id == "deterministic_fixture"
    assert descriptor.live_mode_id == "live_harness"
    assert descriptor.live_requires_instrumentation


def test_no_driver_declares_generic_shell_fallback():
    for driver in all_drivers():
        descriptor = driver.descriptor
        assert descriptor.shell_fallback is False
        assert descriptor.adapter_id in ADAPTER_IDS
