from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping
from urllib.error import URLError
from urllib.request import Request, urlopen

from .d4_qwen_campaign import D4QwenCampaign
from .models import OllamaChatAdapter


class D4ConfigError(ValueError):
    pass


class D4PreflightError(RuntimeError):
    pass


def load_d4_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise D4ConfigError(f"unable to load D4 config: {config_path}") from exc
    if not isinstance(raw, dict):
        raise D4ConfigError("D4 config root must be an object")
    required = {
        "schema_version",
        "protocol",
        "max_calls",
        "model",
        "ollama_base_url",
        "generation_options",
        "case_seed",
        "cases_per_family",
        "policies",
        "blind_retries_allowed",
    }
    missing = sorted(required - set(raw))
    if missing:
        raise D4ConfigError(f"D4 config missing required keys: {missing}")
    if int(raw["schema_version"]) != 1 or str(raw["protocol"]) != "D4-QWEN-POLICY-v1":
        raise D4ConfigError("unsupported D4 protocol/config version")
    if int(raw["max_calls"]) != 48:
        raise D4ConfigError("D4 max_calls must remain exactly 48")
    if bool(raw["blind_retries_allowed"]):
        raise D4ConfigError("blind retries are forbidden in D4")
    generation = raw["generation_options"]
    if not isinstance(generation, dict):
        raise D4ConfigError("D4 generation_options must be an object")
    if float(generation.get("temperature", -1)) != 0.0:
        raise D4ConfigError("D4 temperature must remain 0")
    if int(generation.get("seed", -1)) != 20260902:
        raise D4ConfigError("D4 generation seed must remain 20260902")
    if int(generation.get("num_ctx", -1)) != 4096:
        raise D4ConfigError("D4 context must remain 4096 for the matched policy test")
    if int(raw["cases_per_family"]) < 3:
        raise D4ConfigError("D4 requires enough cases to form 24 balanced matched pairs")
    policies = raw["policies"]
    if not isinstance(policies, dict) or set(policies) != {"DEFAULT", "THINK_OFF"}:
        raise D4ConfigError("D4 policies must be exactly DEFAULT and THINK_OFF")
    if dict(policies["DEFAULT"].get("chat_options", {})) != {}:
        raise D4ConfigError("D4 DEFAULT policy must preserve current runtime behavior")
    if dict(policies["THINK_OFF"].get("chat_options", {})) != {"think": False}:
        raise D4ConfigError("D4 THINK_OFF policy must use top-level think=false")
    return raw


def _ollama_preflight(config: Mapping[str, Any]) -> None:
    base_url = str(config["ollama_base_url"]).rstrip("/")
    request = Request(base_url + "/api/tags", method="GET")
    try:
        with urlopen(request, timeout=10.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise D4PreflightError("Ollama preflight failed before D4 inference") from exc
    available = {
        str(row.get("name") or row.get("model") or "")
        for row in payload.get("models", [])
        if isinstance(row, dict)
    }
    if str(config["model"]) not in available:
        raise D4PreflightError(f"required Qwen model is not installed: {config['model']}")


def _build_adapters(config: Mapping[str, Any]) -> dict[str, OllamaChatAdapter]:
    return {
        policy_id: OllamaChatAdapter(
            str(config["model"]),
            base_url=str(config["ollama_base_url"]),
            generation_options=dict(config["generation_options"]),
            chat_options=dict(policy["chat_options"]),
        )
        for policy_id, policy in config["policies"].items()
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Harvest D D4 Qwen call-policy gate")
    parser.add_argument("--config", default="configs/harvest-d-d4-qwen-policy.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-free", action="store_true")
    parser.add_argument("--max-calls", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = load_d4_config(args.config)
        output = Path(args.output)
        if args.model_free:
            campaign = D4QwenCampaign(output, config=config)
            result = campaign.run_model_free()
        else:
            _ollama_preflight(config)
            campaign = D4QwenCampaign(output, config=config, adapters=_build_adapters(config))
            result = campaign.run(max_calls=args.max_calls)
        master = json.loads(
            (output / "00-HARVEST-D-D4-QWEN-POLICY-MASTER-INDEX.json").read_text(encoding="utf-8")
        )
        print(json.dumps(master, sort_keys=True))
        return 0 if result.final_state in {"MODEL_FREE_COMPLETE", "COMPLETE"} else 2
    except (D4ConfigError, D4PreflightError, ValueError) as exc:
        print(f"D4 HARNESS ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
