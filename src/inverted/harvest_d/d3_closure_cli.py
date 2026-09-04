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


def _ollama_preflight(config: Mapping[str, Any]) -> None:
    base_url = str(config["ollama_base_url"]).rstrip("/")
    request = Request(base_url + "/api/tags", method="GET")
    try:
        with urlopen(request, timeout=10.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise ClosurePreflightError("Ollama preflight failed before inference") from exc
    available = {
        str(row.get("name") or row.get("model") or "")
        for row in payload.get("models", [])
        if isinstance(row, dict)
    }
    missing = sorted({str(v) for v in config["models"].values()} - available)
    if missing:
        raise ClosurePreflightError(f"required Ollama models are not installed: {missing}")


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
            policy_id = str(config["d4_policy"]["policy_id"])
            if policy_id == "PENDING_D4":
                raise ClosurePreflightError(
                    "D4 Qwen call policy is not frozen; no D3-Closure model calls were started"
                )
            _ollama_preflight(config)
            campaign = D3ClosureCampaign(output, config=config, adapters=_build_adapters(config))
            result = campaign.run(max_calls=args.max_calls)
        master = json.loads(
            (output / "00-HARVEST-D-D3-CLOSURE-V2-MASTER-INDEX.json").read_text(encoding="utf-8")
        )
        print(json.dumps(master, sort_keys=True))
        return 0 if result.final_state not in {"HARD_STOP"} else 2
    except (ClosureConfigError, ClosurePreflightError, ValueError) as exc:
        print(f"D3-CLOSURE HARNESS ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
