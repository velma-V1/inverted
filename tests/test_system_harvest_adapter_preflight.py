from inverted.system_harvest.adapters.preflight import PreflightObservation, evaluate_preflight
from inverted.system_harvest.adapters.registry import all_adapters


def _observation(adapter):
    descriptor = adapter.descriptor
    return PreflightObservation(
        adapter_id=descriptor.adapter_id,
        version="fixture-1.0",
        source_revision="fixture-commit",
        supported_modes=descriptor.execution_modes,
        captureable_artifact_ids=tuple(item.artifact_id for item in descriptor.native_artifacts),
        captureable_surface_ids=tuple(item.surface_id for item in descriptor.surfaces),
    )


def test_all_eleven_can_pass_preflight_when_declared_surfaces_are_available():
    for adapter in all_adapters():
        report = evaluate_preflight(adapter, _observation(adapter))
        assert report.ready is True, (adapter.descriptor.adapter_id, report.blockers)
        assert report.blockers == ()


def test_missing_required_native_artifact_blocks_preflight():
    adapter = all_adapters()[0]
    obs = _observation(adapter)
    required = next(item.artifact_id for item in adapter.descriptor.native_artifacts if item.required)
    bad = PreflightObservation(
        adapter_id=obs.adapter_id, version=obs.version, source_revision=obs.source_revision,
        supported_modes=obs.supported_modes,
        captureable_artifact_ids=tuple(x for x in obs.captureable_artifact_ids if x != required),
        captureable_surface_ids=obs.captureable_surface_ids,
    )
    report = evaluate_preflight(adapter, bad)
    assert report.ready is False
    assert any(required in blocker for blocker in report.blockers)


def test_preflight_requires_version_source_revision_and_supported_mode():
    adapter = all_adapters()[1]
    obs = _observation(adapter)
    bad = PreflightObservation(
        adapter_id=obs.adapter_id, version="", source_revision="",
        supported_modes=("unknown",), captureable_artifact_ids=obs.captureable_artifact_ids,
        captureable_surface_ids=obs.captureable_surface_ids,
    )
    report = evaluate_preflight(adapter, bad)
    assert report.ready is False
    assert any("version" in blocker for blocker in report.blockers)
    assert any("source revision" in blocker for blocker in report.blockers)
    assert any("execution mode" in blocker for blocker in report.blockers)


def test_missing_required_surface_blocks_preflight():
    adapter = all_adapters()[2]
    obs = _observation(adapter)
    required_surface = next(item.surface_id for item in adapter.descriptor.surfaces if item.required)
    bad = PreflightObservation(
        adapter_id=obs.adapter_id, version=obs.version, source_revision=obs.source_revision,
        supported_modes=obs.supported_modes, captureable_artifact_ids=obs.captureable_artifact_ids,
        captureable_surface_ids=tuple(x for x in obs.captureable_surface_ids if x != required_surface),
    )
    report = evaluate_preflight(adapter, bad)
    assert report.ready is False
    assert any(required_surface in blocker for blocker in report.blockers)
