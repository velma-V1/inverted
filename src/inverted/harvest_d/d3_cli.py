from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping
from urllib.error import URLError
from urllib.request import Request, urlopen

from .d3_campaign import D3Campaign, HardStop
from .d3_cases import generate_d3_cases
from .d3_outputs import finalize_d3_package
from .d3_planner import D3ExperimentPlanner
from .d3_scheduler import D3Scheduler
from .models import OllamaChatAdapter


class D3ConfigError(ValueError):
    pass


class D3PreflightError(RuntimeError):
    pass


def _stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def load_d3_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise D3ConfigError(f"unable to load D3 config: {config_path}") from exc
    if not isinstance(raw, dict):
        raise D3ConfigError("D3 config root must be an object")

    required = {
        "schema_version",
        "max_calls",
        "ollama_base_url",
        "models",
        "generation_options",
        "seeds",
        "cases_per_family",
        "scheduler",
        "sealed_reserve",
        "normal_ci_model_free",
        "blind_retries_allowed",
    }
    missing = sorted(required - set(raw))
    if missing:
        raise D3ConfigError(f"D3 config missing required keys: {missing}")
    if int(raw["schema_version"]) != 1:
        raise D3ConfigError("unsupported D3 config schema version")
    if not 0 <= int(raw["max_calls"]) <= 1000:
        raise D3ConfigError("D3 max_calls must be in [0,1000]")
    if int(raw["sealed_reserve"]) != 100:
        raise D3ConfigError("D3 sealed reserve must remain exactly 100 calls")
    if bool(raw["blind_retries_allowed"]):
        raise D3ConfigError("blind retries are forbidden in D3")

    models = raw["models"]
    if not isinstance(models, dict) or not models.get("SMALL_A") or not models.get("QWEN"):
        raise D3ConfigError("D3 requires SMALL_A and QWEN model identities")
    generation = raw["generation_options"]
    if not isinstance(generation, dict):
        raise D3ConfigError("generation_options must be an object")
    if float(generation.get("temperature", -1)) != 0.0:
        raise D3ConfigError("D3 generation temperature must remain 0")
    if int(generation.get("seed", -1)) != 20260902:
        raise D3ConfigError("D3 generation seed changed from the frozen value")
    if int(generation.get("num_ctx", -1)) != 4096:
        raise D3ConfigError("D3 context window changed from the frozen value")

    seeds = raw["seeds"]
    counts = raw["cases_per_family"]
    if not isinstance(seeds, dict) or not isinstance(counts, dict):
        raise D3ConfigError("D3 seeds and cases_per_family must be objects")
    for partition in ("development", "fresh", "sealed"):
        if partition not in seeds or partition not in counts:
            raise D3ConfigError(f"D3 missing {partition} seed/count")
        if int(counts[partition]) < 1:
            raise D3ConfigError(f"D3 {partition} case count must be positive")
    if len({int(seeds[p]) for p in ("development", "fresh", "sealed")}) != 3:
        raise D3ConfigError("development/fresh/sealed seeds must be distinct")
    if int(counts["sealed"]) * 11 * len(models) * 2 > 100:
        raise D3ConfigError("sealed case plan would exceed protected 100-call reserve")

    scheduler = raw["scheduler"]
    if not isinstance(scheduler, dict):
        raise D3ConfigError("scheduler must be an object")
    fraction = float(scheduler.get("protected_random_stream_fraction", -1.0))
    if not 0.0 <= fraction <= 1.0:
        raise D3ConfigError("protected random stream fraction must be in [0,1]")
    return raw


def build_planner(config: Mapping[str, Any]) -> D3ExperimentPlanner:
    seeds = config["seeds"]
    counts = config["cases_per_family"]
    models = tuple(str(key) for key in config["models"].keys())
    return D3ExperimentPlanner(
        development_cases=generate_d3_cases(
            partition="development",
            seed=int(seeds["development"]),
            per_family=int(counts["development"]),
        ),
        fresh_cases=generate_d3_cases(
            partition="fresh",
            seed=int(seeds["fresh"]),
            per_family=int(counts["fresh"]),
        ),
        sealed_cases=generate_d3_cases(
            partition="sealed",
            seed=int(seeds["sealed"]),
            per_family=int(counts["sealed"]),
        ),
        model_keys=models,
    )


def _git_provenance() -> dict[str, Any]:
    def run(*args: str) -> str | None:
        try:
            completed = subprocess.run(
                ["git", *args],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return completed.stdout.strip() or None

    status = run("status", "--porcelain")
    return {
        "commit": run("rev-parse", "HEAD"),
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(status) if status is not None else None,
        "dirty_status_hash": _stable_hash(status) if status else None,
    }


def _build_adapters(config: Mapping[str, Any]) -> dict[str, OllamaChatAdapter]:
    base_url = str(config["ollama_base_url"])
    options = dict(config["generation_options"])
    return {
        str(key): OllamaChatAdapter(
            str(model_id),
            base_url=base_url,
            generation_options=options,
        )
        for key, model_id in config["models"].items()
    }


def _ollama_preflight(config: Mapping[str, Any]) -> dict[str, Any]:
    base_url = str(config["ollama_base_url"]).rstrip("/")
    request = Request(base_url + "/api/tags", method="GET")
    try:
        with urlopen(request, timeout=10.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise D3PreflightError("Ollama preflight failed before inference") from exc
    models = payload.get("models", []) if isinstance(payload, dict) else []
    available: set[str] = set()
    digests: dict[str, str | None] = {}
    for row in models:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("model") or "")
        if name:
            available.add(name)
            digests[name] = str(row.get("digest")) if row.get("digest") is not None else None
    required = {str(value) for value in config["models"].values()}
    missing = sorted(required - available)
    if missing:
        raise D3PreflightError(f"required Ollama models are not installed: {missing}")
    return {
        "endpoint": base_url,
        "required_models": sorted(required),
        "model_digests": {name: digests.get(name) for name in sorted(required)},
        "single_preflight_request": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Harvest D D3 automated tomography")
    parser.add_argument("--config", default="configs/harvest-d-d3.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-free", action="store_true")
    parser.add_argument("--max-calls", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = load_d3_config(args.config)
        if args.max_calls is not None:
            if not 0 <= int(args.max_calls) <= int(config["max_calls"]):
                raise D3ConfigError("--max-calls exceeds configured D3 ceiling")
            config = dict(config)
            config["max_calls"] = int(args.max_calls)

        output = Path(args.output)
        planner = build_planner(config)
        adapters = _build_adapters(config)
        scheduler = D3Scheduler.default(
            random_stream_fraction=float(config["scheduler"]["protected_random_stream_fraction"]),
            seed=int(config["scheduler"]["seed"]),
        )
        provenance = {
            "mode": "MODEL_FREE" if args.model_free else "REAL_LOCAL",
            "config_hash": _stable_hash(config),
            "models": {key: adapter.model_id for key, adapter in sorted(adapters.items())},
            "generation_options": dict(config["generation_options"]),
            "git": _git_provenance(),
        }
        if not args.model_free:
            provenance["ollama"] = _ollama_preflight(config)

        campaign = D3Campaign.production(
            output,
            adapters=adapters,
            planner=planner,
            max_calls=int(config["max_calls"]),
            scheduler=scheduler,
            provenance=provenance,
        )
        if args.model_free:
            result = campaign.run_model_free_simulation()
        else:
            result = campaign.run()

        master = finalize_d3_package(
            output,
            planner=planner,
            config=config,
            model_free=bool(args.model_free),
            campaign_result=asdict(result),
        )
        print(json.dumps(master, sort_keys=True))
        return 0 if result.final_state != "HARD_STOP" else 2
    except (D3ConfigError, D3PreflightError, HardStop, ValueError) as exc:
        print(f"D3 HARNESS ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
