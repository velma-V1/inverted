from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping
from urllib.error import URLError
from urllib.request import Request, urlopen

from .d3_closure_campaign import D3ClosureCampaign
from .models import OllamaChatAdapter


class ClosureConfigError(ValueError):
    pass


class ClosurePreflightError(RuntimeError):
    pass


_D3_V1_SEEDS = {20260903, 20260913, 20261003}


def load_closure_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ClosureConfigError(f"unable to load D3-Closure config: {config_path}") from exc
    if not isinstance(raw, dict):
        raise ClosureConfigError("D3-Closure config root must be an object")
    required = {
        "schema_version",
        "protocol",
        "max_calls",
        "sealed_reserve",
        "ollama_base_url",
        "models",
        "generation_options",
        "seeds",
        "cases_per_family",
        "d4_policy",
        "blind_retries_allowed",
    }
    missing = sorted(required - set(raw))
    if missing:
        raise ClosureConfigError(f"D3-Closure config missing required keys: {missing}")
    if int(raw["schema_version"]) != 1:
        raise ClosureConfigError("unsupported D3-Closure config schema version")
    if str(raw["protocol"]) != "D3-CLOSURE-v2":
        raise ClosureConfigError("D3-Closure protocol identity must remain D3-CLOSURE-v2")
    if int(raw["max_calls"]) != 200:
        raise ClosureConfigError("D3-Closure max_calls must remain exactly 200")
    if int(raw["sealed_reserve"]) != 48:
        raise ClosureConfigError("D3-Closure sealed reserve must remain exactly 48")
    if bool(raw["blind_retries_allowed"]):
        raise ClosureConfigError("blind retries are forbidden in D3-Closure")

    models = raw["models"]
    if not isinstance(models, dict) or not models.get("SMALL_A") or not models.get("QWEN"):
        raise ClosureConfigError("D3-Closure requires SMALL_A and QWEN identities")
    generation = raw["generation_options"]
    if not isinstance(generation, dict):
        raise ClosureConfigError("generation_options must be an object")
    if float(generation.get("temperature", -1)) != 0.0:
        raise ClosureConfigError("D3-Closure temperature must remain 0")
    if int(generation.get("seed", -1)) != 20260902:
        raise ClosureConfigError("D3-Closure generation seed must remain 20260902")
    if int(generation.get("num_ctx", -1)) != 4096:
        raise ClosureConfigError("D3-Closure base context window must remain 4096")

    seeds = raw["seeds"]
    counts = raw["cases_per_family"]
    if not isinstance(seeds, dict) or not isinstance(counts, dict):
        raise ClosureConfigError("seeds and cases_per_family must be objects")
    seed_values: list[int] = []
    for key in ("development", "fresh", "sealed"):
        if key not in seeds or key not in counts:
            raise ClosureConfigError(f"missing closure {key} seed/count")
        seed_values.append(int(seeds[key]))
        if int(counts[key]) < 1:
            raise ClosureConfigError(f"closure {key} case count must be positive")
    if len(set(seed_values)) != 3:
        raise ClosureConfigError("closure partition seeds must be distinct")
    if set(seed_values) & _D3_V1_SEEDS:
        raise ClosureConfigError("closure seeds must not reuse D3-v1 partition seeds")

    d4_policy = raw["d4_policy"]
    if not isinstance(d4_policy, dict) or not d4_policy.get("policy_id"):
        raise ClosureConfigError("d4_policy must declare policy_id")
    if not isinstance(d4_policy.get("chat_options", {}), dict):
        raise ClosureConfigError("d4_policy chat_options must be an object")
    return raw


def load_frozen_d4_policy(
    path: str | Path,
    *,
    expected_model: str,
    expected_digest: str | None = None,
) -> dict[str, Any]:
    policy_path = Path(path)
    try:
        raw = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load frozen D4 policy: {policy_path}") from exc
    if not isinstance(raw, dict) or str(raw.get("state")) != "FROZEN":
        raise ValueError("D4 policy is not frozen; closure inference is not authorized")
    if str(raw.get("model_id")) != str(expected_model):
        raise ValueError("D4 policy model identity does not match closure Qwen model")
    if expected_digest is not None and str(raw.get("model_digest") or "") != str(expected_digest):
        raise ValueError("D4 policy model digest does not match the installed Qwen model digest")
    policy_id = str(raw.get("policy_id") or "")
    if policy_id not in {"DEFAULT", "THINK_OFF"}:
        raise ValueError("D4 frozen policy has an unsupported policy_id")
    chat_options = raw.get("chat_options", {})
    if not isinstance(chat_options, dict):
        raise ValueError("D4 frozen policy chat_options must be an object")
    if policy_id == "DEFAULT" and chat_options:
        raise ValueError("DEFAULT D4 policy may not silently add chat options")
    if policy_id == "THINK_OFF" and dict(chat_options) != {"think": False}:
        raise ValueError("THINK_OFF D4 policy must be exactly think=false")
    return raw


def _ollama_preflight(config: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    base_url = str(config["ollama_base_url"]).rstrip("/")
    request = Request(base_url + "/api/tags", method="GET")
    try:
        with urlopen(request, timeout=10.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise ClosurePreflightError("Ollama preflight failed before inference") from exc
    rows = {
        str(row.get("name") or row.get("model") or ""): row
        for row in payload.get("models", [])
        if isinstance(row, dict)
    }
    required = {str(value) for value in config["models"].values()}
    missing = sorted(required - set(rows))
    if missing:
        raise ClosurePreflightError(f"required Ollama models are not installed: {missing}")
    digests: dict[str, str] = {}
    for model_id in sorted(required):
        digest = str(rows[model_id].get("digest") or "")
        if not digest:
            raise ClosurePreflightError(f"required Ollama model digest is unavailable: {model_id}")
        digests[model_id] = digest
    return {"model_digests": digests}


def _build_adapters(config: Mapping[str, Any]) -> dict[str, OllamaChatAdapter]:
    base_url = str(config["ollama_base_url"])
    generation_options = dict(config["generation_options"])
    d4_policy = dict(config["d4_policy"])
    return {
        "SMALL_A": OllamaChatAdapter(
            str(config["models"]["SMALL_A"]),
            base_url=base_url,
            generation_options=generation_options,
        ),
        "QWEN": OllamaChatAdapter(
            str(config["models"]["QWEN"]),
            base_url=base_url,
            generation_options=generation_options,
            chat_options=dict(d4_policy.get("chat_options", {})),
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Harvest D D3-Closure v2")
    parser.add_argument("--config", default="configs/harvest-d-d3-closure-v2.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-free", action="store_true")
    parser.add_argument("--max-calls", type=int, default=None)
    parser.add_argument("--d4-policy-file", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = load_closure_config(args.config)
        output = Path(args.output)
        if args.model_free:
            campaign = D3ClosureCampaign(output, config=config)
            result = campaign.run_model_free()
        else:
            config = dict(config)
            policy_id = str(config["d4_policy"]["policy_id"])
            if not args.d4_policy_file and policy_id == "PENDING_D4":
                raise ClosurePreflightError(
                    "D4 Qwen call policy is not frozen; no D3-Closure model calls were started"
                )
            preflight = _ollama_preflight(config)
            model_digests = dict(preflight["model_digests"])
            config["runtime_model_digests"] = model_digests
            if args.d4_policy_file:
                qwen_model = str(config["models"]["QWEN"])
                frozen = load_frozen_d4_policy(
                    args.d4_policy_file,
                    expected_model=qwen_model,
                    expected_digest=model_digests[qwen_model],
                )
                config["d4_policy"] = {
                    "policy_id": frozen["policy_id"],
                    "chat_options": dict(frozen.get("chat_options", {})),
                    "model_digest": str(frozen["model_digest"]),
                    "source": str(Path(args.d4_policy_file)),
                }
            campaign = D3ClosureCampaign(output, config=config, adapters=_build_adapters(config))
            result = campaign.run(max_calls=args.max_calls)
        master = json.loads(
            (output / "00-HARVEST-D-D3-CLOSURE-V2-MASTER-INDEX.json").read_text(encoding="utf-8")
        )
        print(json.dumps(master, sort_keys=True))
        success_states = {"MODEL_FREE_COMPLETE"} if args.model_free else {"COMPLETE"}
        return 0 if result.final_state in success_states else 2
    except (ClosureConfigError, ClosurePreflightError, ValueError) as exc:
        print(f"D3-CLOSURE HARNESS ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
