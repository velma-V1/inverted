from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from inverted.artifacts import ArtifactWriter, collect_provenance
from inverted.cli import _build_models, _experiment_config, _sanitized_models, load_config
from inverted.runner import build_trial_plan, run_experiment
from inverted.statistics import aggregate_trials
from inverted.validation import VALIDATION_SCOPE, run_known_answer_suite
from inverted.verdict import decide_verdict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate GitHub instrument-validation evidence.")
    parser.add_argument("--config", default="configs/validation-stress.yaml")
    parser.add_argument("--output-dir", default="validation-output")
    args = parser.parse_args(argv)

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)

    known = run_known_answer_suite(output / "known-answer")
    if not known["all_passed"]:
        print(json.dumps(known, sort_keys=True, indent=2))
        return 2

    raw = load_config(args.config)
    config = _experiment_config(raw)
    scope = config.metadata.get("evidence_scope")
    if scope != VALIDATION_SCOPE:
        raise ValueError("validation stress config is missing the required evidence-scope label")
    models = _build_models(raw, capture_content=False)
    planned_units = len(build_trial_plan(config, models))

    result = run_experiment(config, models, run_id="github-validation-stress")
    summary = aggregate_trials(result.trials, config.bootstrap_samples, config.bootstrap_seed)
    verdict = decide_verdict(summary, config)

    provenance = collect_provenance()
    provenance.update({
        "validation_scope": VALIDATION_SCOPE,
        "config_path": str(Path(args.config).resolve()),
        "models": _sanitized_models(raw),
        "planned_trial_units": planned_units,
        "run_started_at": result.started_at,
        "run_ended_at": result.ended_at,
    })

    stress_dir = output / "stress"
    paths = ArtifactWriter(stress_dir).write_all(
        result,
        summary,
        verdict,
        provenance,
        include_raw_rows=False,
    )
    report_text = Path(paths["report"]).read_text(encoding="utf-8")

    stress_passed = (
        verdict["verdict"] == "NON-DECISIVE"
        and len(result.trials) == planned_units
        and VALIDATION_SCOPE in report_text
    )

    manifest = {
        "evidence_scope": VALIDATION_SCOPE,
        "all_passed": bool(known["all_passed"] and stress_passed),
        "known_answer": known,
        "stress": {
            "passed": stress_passed,
            "expected_verdict": "NON-DECISIVE",
            "observed_verdict": verdict["verdict"],
            "planned_trial_units": planned_units,
            "observed_trial_units": len(result.trials),
            "independent_task_clusters": summary.get("primary", {}).get("independent_task_clusters"),
            "artifacts": paths,
        },
    }
    manifest_path = output / "validation-manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True, indent=2))
    return 0 if manifest["all_passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
