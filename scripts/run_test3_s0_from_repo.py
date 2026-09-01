from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from inverted.test3_repo_evidence import (
    materialize_repo_empirical_sources,
    repo_s0_source_specs,
    verify_repo_evidence,
)


def _run(args: list[str], *, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reproduce Test-3 S0 from committed empirical evidence.")
    parser.add_argument("--work-dir", default="test3-s0-repo-run")
    parser.add_argument("--keep-existing", action="store_true")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    evidence_root = repo / "evidence"
    work = repo / args.work_dir

    errors = verify_repo_evidence(evidence_root, verify_hashes=True)
    if errors:
        print("REPO_EVIDENCE_INVALID", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 3

    if work.exists() and not args.keep_existing:
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    sources_root = work / "sources"
    rehydrated_root = work / "rehydrated-empirical-sources"
    manifest = work / "source-manifest.json"
    output = work / "scientific-s0"
    generated_model_free = sources_root / "test2-model-free"

    try:
        empirical_paths, normalization_report = materialize_repo_empirical_sources(
            evidence_root,
            rehydrated_root,
        )
    except ValueError as exc:
        print(f"REPO_EVIDENCE_REHYDRATION_FAILED: {exc}", file=sys.stderr)
        return 3

    (work / "repo-evidence-normalization.json").write_text(
        json.dumps(normalization_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    _run(
        [
            sys.executable,
            "-m",
            "inverted.test2_cli",
            "model-free",
            "--config",
            "configs/test2-model-free.yaml",
            "--output-dir",
            str(sources_root),
            "--run-id",
            "test2-model-free",
        ],
        cwd=repo,
    )

    specs = repo_s0_source_specs(
        evidence_root,
        generated_model_free,
        empirical_paths=empirical_paths,
    )
    manifest_args = [
        sys.executable,
        "-m",
        "inverted.test3_s0_cli",
        "build-manifest",
        "--output",
        str(manifest),
    ]
    for source_id, source_class, path in specs:
        manifest_args.extend(["--source", source_id, source_class, str(path)])
    _run(manifest_args, cwd=repo)

    _run(
        [
            sys.executable,
            "-m",
            "inverted.test3_s0_cli",
            "run",
            "--config",
            "configs/test3-s0.yaml",
            "--manifest",
            str(manifest),
            "--output-dir",
            str(output),
        ],
        cwd=repo,
    )

    verdict = json.loads((output / "verdict.json").read_text(encoding="utf-8-sig"))
    prereg = json.loads(
        (output / "candidate_section1_preregistration.json").read_text(encoding="utf-8-sig")
    )

    failures: list[str] = []
    if verdict.get("verdict") != "DISCOVERY_COMPLETE_MODEL_FREE":
        failures.append(f"unexpected S0 verdict: {verdict.get('verdict')}")
    if verdict.get("physical_model_calls") != 0:
        failures.append("S0 physical_model_calls must equal 0")
    if verdict.get("attempted_model_calls") != 0:
        failures.append("S0 attempted_model_calls must equal 0")
    if prereg.get("arm_freeze_ready") is not True:
        failures.append(f"S1 arm freeze not ready: {prereg.get('arm_freeze_blocker')}")
    if prereg.get("exact_budget") != 80:
        failures.append(f"S1 exact budget must equal 80 physical calls, got {prereg.get('exact_budget')}")
    if prereg.get("tier_a_inference_authorized") is not False:
        failures.append("S0 must not authorize Tier-A inference")
    arms = prereg.get("arms") or []
    if len(arms) != 4:
        failures.append(f"S1 must freeze exactly 4 arms, got {len(arms)}")
    if any("oracle_auditor" in str(arm.get("order") or "") for arm in arms if isinstance(arm, dict)):
        failures.append("oracle_auditor leaked into S1 production arms")
    if len(prereg.get("selected_fixed_orders") or []) < 2:
        failures.append("S1 requires at least two selected fixed orders")

    summary = {
        "repo_evidence_verified": True,
        "repo_evidence_verification_policy": normalization_report["verification_policy"],
        "repo_evidence_exact_files": normalization_report["exact_files"],
        "repo_evidence_git_newline_rehydrated_files": normalization_report[
            "git_newline_rehydrated_files"
        ],
        "repo_evidence_unverified_files": normalization_report["unverified_files"],
        "s0_verdict": verdict.get("verdict"),
        "physical_model_calls": verdict.get("physical_model_calls"),
        "attempted_model_calls": verdict.get("attempted_model_calls"),
        "arm_freeze_ready": prereg.get("arm_freeze_ready"),
        "exact_budget": prereg.get("exact_budget"),
        "arm_count": len(arms),
        "selected_fixed_orders": prereg.get("selected_fixed_orders") or [],
        "tier_a_inference_authorized": prereg.get("tier_a_inference_authorized"),
        "failures": failures,
    }
    (work / "repo-replay-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if failures:
        print(json.dumps(summary, indent=2, sort_keys=True), file=sys.stderr)
        return 4

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
