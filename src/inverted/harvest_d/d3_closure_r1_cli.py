from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping
from urllib.error import URLError
from urllib.request import Request, urlopen

from .d3_closure_cli import _build_adapters, load_closure_config, load_frozen_d4_policy
from .d3_closure_r1 import R1CalibrationCampaign, R1_MAX_CALLS, build_r1_model_free_package, validate_r1_stage_authorization


def _load_json(path: str | Path, label: str) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load {label}: {path}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a JSON object")
    return raw


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _runtime_identity(config: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    base_url = str(config["ollama_base_url"]).rstrip("/")
    try:
        with urlopen(Request(base_url + "/api/tags", method="GET"), timeout=10.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise RuntimeError("R1 Ollama runtime-identity preflight failed before inference") from exc
    installed = {
        str(row.get("name") or row.get("model") or ""): row
        for row in payload.get("models", []) if isinstance(row, dict)
    }
    result: dict[str, dict[str, Any]] = {}
    for key, model_id_raw in config["models"].items():
        model_id = str(model_id_raw)
        row = installed.get(model_id)
        if row is None:
            raise RuntimeError(f"R1 required Ollama model is not installed: {model_id}")
        digest = str(row.get("digest") or "")
        if not digest:
            raise RuntimeError(f"R1 required Ollama model digest is unavailable: {model_id}")
        size_bytes = int(row.get("size") or 0)
        result[str(key)] = {
            "model_id": model_id,
            "model_digest": digest,
            "installed_size_bytes": size_bytes,
            "installed_size_gib": size_bytes / (1024 ** 3) if size_bytes else None,
            "thinking": False,
            "offload_observed": False,
        }
    return result


def _validate_fresh_r0(path: str | Path) -> dict[str, Any]:
    raw = _load_json(path, "fresh R0 readiness report")
    if str(raw.get("final_state")) != "R0_MODEL_FREE_COMPLETE" or raw.get("r0_ready") is not True:
        raise ValueError("fresh R0 readiness is not complete")
    if int(raw.get("physical_model_calls", -1)) != 0:
        raise ValueError("R0 readiness is contaminated by physical model calls")
    if raw.get("physical_execution_authorized") is not False:
        raise ValueError("R0 must not authorize broad Closure physical execution")
    if raw.get("evidence_tier_integrity") is not True:
        raise ValueError("R0 historical/fresh evidence-tier integrity is not green")
    if int(raw.get("uncovered_mandatory_obligations", -1)) != 0:
        raise ValueError("R0 has uncovered mandatory model-free obligations")
    return raw


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Harvest D D3-Closure R1 calibration")
    parser.add_argument("--config", default="configs/harvest-d-d3-closure-v2.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-free", action="store_true")
    parser.add_argument("--stage-authorization", default="configs/harvest-d-d3-closure-v2-r1-authorization.json")
    parser.add_argument("--r0-readiness-file", default=None)
    parser.add_argument("--d4-policy-file", default=None)
    parser.add_argument("--max-calls", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = load_closure_config(args.config)
        if args.model_free:
            summary = build_r1_model_free_package(args.output, config)
            print(json.dumps(summary, sort_keys=True))
            return 0

        authorization = _load_json(args.stage_authorization, "R1 stage authorization")
        validate_r1_stage_authorization(authorization)
        limit = R1_MAX_CALLS if args.max_calls is None else int(args.max_calls)
        if not 0 <= limit <= R1_MAX_CALLS:
            raise ValueError("R1 --max-calls must remain between 0 and 24")
        if not args.r0_readiness_file:
            raise ValueError("real R1 requires a fresh R0 readiness report")
        _validate_fresh_r0(args.r0_readiness_file)
        if not args.d4_policy_file:
            raise ValueError("real R1 requires the frozen D4 policy")

        identity = _runtime_identity(config)
        qwen_identity = identity["QWEN"]
        policy = load_frozen_d4_policy(
            args.d4_policy_file,
            expected_model=str(config["models"]["QWEN"]),
            expected_digest=str(qwen_identity["model_digest"]),
        )
        config = dict(config)
        config["d4_policy"] = {"policy_id": policy["policy_id"], "chat_options": dict(policy.get("chat_options", {}))}
        identity["QWEN"]["thinking"] = policy["policy_id"] != "THINK_OFF"

        root = Path(args.output)
        root.mkdir(parents=True, exist_ok=True)
        readiness = {
            "protocol": "D3-CLOSURE-v2", "stage": "R1_CALIBRATION", "state": "R1_READY_FOR_PHYSICAL",
            "physical_model_calls": 0, "max_physical_calls": R1_MAX_CALLS,
            "legacy_closure_path_allowed": False, "runtime_identity_verified": True,
            "d4_policy_verified": True, "fresh_r0_verified": True,
            "fresh_r0_sha256": _sha256(args.r0_readiness_file),
            "stage_authorization_sha256": _sha256(args.stage_authorization),
            "ready_for_physical_r1": True, "ready_for_test5": False,
        }
        (root / "closure_r1_readiness.json").write_text(json.dumps(readiness, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        campaign = R1CalibrationCampaign(root, config=config, adapters=_build_adapters(config), runtime_identity=identity)
        result = campaign.run(max_calls=limit)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["final_state"] in {"R1_CALIBRATION_COMPLETE", "R1_CALIBRATION_PARTIAL"} else 2
    except Exception as exc:
        print(f"R1 calibration failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
