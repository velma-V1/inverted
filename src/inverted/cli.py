from __future__ import annotations

import argparse
from dataclasses import fields
import json
import os
from pathlib import Path
import re
from typing import Any

import yaml

from .artifacts import ArtifactWriter, collect_provenance
from .checkpoint import CheckpointStore
from .models import ModelCallError, MockModelAdapter, OllamaAdapter, OpenAICompatibleAdapter
from .runner import ExperimentConfig, TrialPlan, run_experiment
from .statistics import aggregate_trials
from .verdict import decide_verdict

_ENV_RE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        match = _ENV_RE.match(value)
        if match:
            name = match.group(1)
            if name not in os.environ:
                raise ValueError(f"required environment variable {name} is not set")
            return os.environ[name]
        return value
    if isinstance(value, list):
        return [_expand_env(x) for x in value]
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    return value


def _validate_decisive(raw: dict[str, Any]) -> None:
    bench = raw.get("benchmark", {})
    if not bench.get("decisive", False):
        return
    models = raw.get("models") or []
    if any(m.get("provider") == "mock" for m in models):
        raise ValueError("decisive runs may not use mock models")
    if len(models) < 3:
        raise ValueError("decisive runs require at least three model configurations")
    identities = {(m.get("provider"), m.get("model")) for m in models}
    if len(identities) < 3:
        raise ValueError("decisive runs require three distinct model configurations")
    families = set(bench.get("families", []))
    if not {"state", "policy", "reconciliation"}.issubset(families):
        raise ValueError("decisive runs require all three task families")
    if len(set(bench.get("complexities", []))) < 4:
        raise ValueError("decisive runs require all four complexity levels")
    if len(set(bench.get("qualities", []))) < 5:
        raise ValueError("decisive runs require at least five executor-quality levels")
    if len(set(bench.get("seeds", []))) < 3:
        raise ValueError("decisive runs require at least three independent seeds")
    if int(bench.get("epochs", 0)) < 2:
        raise ValueError("decisive runs require at least two epochs")
    for spec in models:
        if spec.get("provider") == "ollama":
            required = {
                "context_limit": spec.get("context_limit"),
                "think": spec.get("think"),
                "format_json": spec.get("format_json"),
                "max_retries": spec.get("max_retries"),
            }
            if required["context_limit"] is None:
                raise ValueError("decisive Ollama runs require an explicit context_limit")
            if required["think"] is not False:
                raise ValueError("decisive Ollama runs require think: false to prevent reasoning-only empty responses")
            if required["format_json"] is not True:
                raise ValueError("decisive Ollama runs require format_json: true")
            if int(required["max_retries"] or 0) < 2:
                raise ValueError("decisive Ollama runs require at least two transport retries")


def load_config(path: str | Path) -> dict[str, Any]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    raw = _expand_env(raw)
    if not raw.get("models"):
        raise ValueError("configuration must define at least one model")
    _validate_decisive(raw)
    return raw


def _experiment_config(raw: dict[str, Any]) -> ExperimentConfig:
    bench = dict(raw.get("benchmark") or {})
    tuple_fields = {"families", "complexities", "qualities", "seeds", "arms"}
    for key in tuple_fields:
        if key in bench:
            bench[key] = tuple(bench[key])
    allowed = {f.name for f in fields(ExperimentConfig)}
    unknown = set(bench) - allowed
    if unknown:
        raise ValueError(f"unknown benchmark config fields: {sorted(unknown)}")
    return ExperimentConfig(**bench)


def _build_models(raw: dict[str, Any], capture_content: bool) -> list[Any]:
    out = []
    for spec in raw.get("models", []):
        provider = spec.get("provider")
        common = {"model": str(spec["model"]), "capture_content": capture_content}
        if provider == "mock":
            out.append(MockModelAdapter(
                **common,
                seed=int(spec.get("seed", 0)),
                executor_accuracy=float(spec.get("executor_accuracy", 1.0)),
                auditor_accuracy=float(spec.get("auditor_accuracy", 1.0)),
            ))
        elif provider == "ollama":
            out.append(OllamaAdapter(
                **common,
                base_url=str(spec.get("base_url", "http://127.0.0.1:11434")),
                timeout_s=float(spec.get("timeout_s", 180.0)),
                temperature=float(spec.get("temperature", 0.0)),
                max_tokens=int(spec.get("max_tokens", 1024)),
                max_retries=int(spec.get("max_retries", 0)),
                retry_backoff_s=float(spec.get("retry_backoff_s", 1.0)),
                think=spec.get("think"),
                format_json=bool(spec.get("format_json", False)),
                context_limit=int(spec["context_limit"]) if spec.get("context_limit") is not None else None,
            ))
        elif provider == "openai-compatible":
            api_key = None
            key_env = spec.get("api_key_env")
            if key_env:
                api_key = os.environ.get(str(key_env))
                if not api_key:
                    raise ValueError(f"API key environment variable {key_env} is not set")
            out.append(OpenAICompatibleAdapter(
                **common,
                base_url=str(spec["base_url"]), api_key=api_key,
                timeout_s=float(spec.get("timeout_s", 180.0)),
                temperature=float(spec.get("temperature", 0.0)),
                max_tokens=int(spec.get("max_tokens", 1024)),
                price_per_m_input=float(spec["price_per_m_input"]) if spec.get("price_per_m_input") is not None else None,
                price_per_m_output=float(spec["price_per_m_output"]) if spec.get("price_per_m_output") is not None else None,
            ))
        else:
            raise ValueError(f"unknown model provider: {provider}")
    return out


def _preflight_models(models: list[Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for model in models:
        provider = str(getattr(model, "provider", ""))
        if provider == "mock":
            continue
        if provider != "ollama":
            continue
        preflight = getattr(model, "preflight", None)
        if not callable(preflight):
            raise ValueError(f"Ollama adapter {getattr(model, 'model', 'unknown')} does not expose preflight")
        result = preflight()
        evidence.append(dict(result))
    return evidence


def _sanitized_models(raw: dict[str, Any]) -> list[dict[str, Any]]:
    safe = []
    for spec in raw.get("models", []):
        row = {k: v for k, v in spec.items() if k not in {"api_key", "token", "authorization"}}
        safe.append(row)
    return safe


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Benchmark direct-AI execution versus non-AI execution + AI auditing.")
    p.add_argument("--config", required=True, help="YAML configuration path")
    p.add_argument("--output-dir", default=None, help="Root directory for run artifacts")
    p.add_argument("--run-id", default=None, help="Optional deterministic run ID")
    p.add_argument("--checkpoint", default=None, help="Append-only JSONL checkpoint path")
    p.add_argument("--resume", action="store_true", help="Resume completed trial units from --checkpoint")
    p.add_argument("--progress", action="store_true", help="Print exact completed/total trial-unit progress")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.resume and not args.checkpoint:
        raise ValueError("--resume requires --checkpoint")

    raw = load_config(args.config)
    config = _experiment_config(raw)
    report_cfg = raw.get("report") or {}
    capture_content = bool(report_cfg.get("capture_content", True))
    include_raw_rows = bool(report_cfg.get("include_raw_rows", True))
    models = _build_models(raw, capture_content)
    checkpoint = CheckpointStore(args.checkpoint) if args.checkpoint else None

    preflight_evidence = _preflight_models(models)
    for item in preflight_evidence:
        print(
            f"PREFLIGHT OK model={item.get('model')} latency_s={float(item.get('latency_s', 0.0)):.3f} retries={item.get('retry_number', 0)}",
            flush=True,
        )

    progress_callback = None
    if args.progress:
        def render_progress(completed: int, total: int, item: TrialPlan) -> None:
            pct = (100.0 * completed / total) if total else 100.0
            width = 30
            filled = min(width, int(round(width * completed / total))) if total else width
            bar = "#" * filled + "-" * (width - filled)
            model = getattr(models[item.model_index], "model", "none")
            print(
                f"PROGRESS [{bar}] {completed}/{total} {pct:6.2f}% "
                f"model={model} arm={item.arm} family={item.family} complexity={item.complexity} "
                f"quality={item.quality:.2f} seed={item.seed} epoch={item.epoch}",
                flush=True,
            )
        progress_callback = render_progress

    try:
        result = run_experiment(
            config,
            models,
            run_id=args.run_id,
            checkpoint_store=checkpoint,
            resume=bool(args.resume),
            progress_callback=progress_callback,
        )
    except ModelCallError as exc:
        print("INFRASTRUCTURE_FAILURE: model call did not recover; campaign stopped before scoring the affected trial.", flush=True)
        print(json.dumps(exc.record.to_dict(), sort_keys=True, default=str), flush=True)
        return 3

    summary = aggregate_trials(result.trials, config.bootstrap_samples, config.bootstrap_seed)
    verdict = decide_verdict(summary, config)
    provenance = collect_provenance()
    provenance.update({
        "config_path": str(Path(args.config).resolve()),
        "models": _sanitized_models(raw),
        "preflight": preflight_evidence,
        "capture_content": capture_content,
        "include_raw_rows": include_raw_rows,
        "checkpoint_path": str(Path(args.checkpoint).resolve()) if args.checkpoint else None,
        "resumed": bool(args.resume),
        "run_started_at": result.started_at,
        "run_ended_at": result.ended_at,
    })
    root = Path(args.output_dir or raw.get("output_dir") or "runs")
    run_dir = root / result.run_id
    paths = ArtifactWriter(run_dir).write_all(result, summary, verdict, provenance, include_raw_rows=include_raw_rows)
    report = Path(paths["report"]).read_text(encoding="utf-8")
    print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
