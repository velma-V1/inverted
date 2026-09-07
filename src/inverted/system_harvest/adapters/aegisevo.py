from .base import EvidenceOrigin
from .helpers import artifact, launch, make_adapter, surface


ADAPTER = make_adapter(
    system_id="AegisEvo", adapter_id="aegisevo",
    execution_modes=("deterministic_fixture", "live_harness", "control_plane", "evaluator"),
    native_artifacts=(
        artifact("aegisevo.evidence", "native/aegisevo/evidence/*.json", "json"),
        artifact("aegisevo.lineage", "native/aegisevo/lineage.json", "json"),
        artifact("aegisevo.telemetry", "native/aegisevo/telemetry.jsonl", "jsonl"),
        artifact("aegisevo.model_gateway_jsonl", "native/aegisevo/model-gateway.jsonl", "jsonl"),
        artifact("aegisevo.persistence", "native/aegisevo/postgres-export/**", "tree", required=False),
        artifact("aegisevo.outbox", "native/aegisevo/outbox.jsonl", "jsonl", required=False),
    ),
    native_surfaces=(
        surface("aegisevo.live_model_gateway", ("MODEL_IO", "SYSTEM_EVENTS", "RUNTIME_TELEMETRY"),
                ("aegisevo.model_gateway_jsonl",), origin=EvidenceOrigin.INSTRUMENTED,
                description="Lossless provider-neutral live-model gateway request/response/event capture when the bounded live harness is exercised."),
        surface("aegisevo.evolution", ("SYSTEM_EVENTS", "CONTEXT_MEMORY", "STATE_TRANSITIONS", "FAILURE_RECOVERY", "VERIFICATION_RESULTS", "DECISION_ALTERNATIVES"),
                ("aegisevo.evidence", "aegisevo.lineage", "aegisevo.outbox"), description="Candidate genomes, lineage DAG, evaluations, statistical gates, promotion/canary/rollback transitions and immutable facts."),
        surface("aegisevo.worker", ("TOOL_IO", "RUNTIME_TELEMETRY"), ("aegisevo.telemetry", "aegisevo.persistence"),
                description="Fenced worker/evaluator activity, target-adapter observations, budget and telemetry evidence."),
    ),
    discovery_hints=(
        "freeze AegisEvo commit/version",
        "capture canonical deterministic report and contracts",
        "discover and instrument provider-neutral live-model gateway on the frozen commit",
        "export lineage/archive/outbox/control-plane facts",
        "record target-pack, gateway, evaluator and contract versions",
    ),
    source_refs=("https://github.com/ETOLucy/AegisEvo",),
    launch_specs=(
        launch(
            "deterministic_fixture", "cargo", "run", "-p", "aegisevo-cli", "--", "demo",
            "--seed", "17", "--output", "{run_dir}/native/aegisevo/evidence/demo.json",
            output_format="json",
        ),
    ),
)
