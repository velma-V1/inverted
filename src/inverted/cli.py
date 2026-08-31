from __future__ import annotations

import argparse
from dataclasses import fields
import json
import os
from pathlib import Path
import re
from typing import Any

import yaml

from .arms import _auditor_messages, _executor_messages, _parse_actions, _parse_audit
from .artifacts import ArtifactWriter, collect_provenance
from .checkpoint import CheckpointStore
from .models import GenerationCensored, ModelCallError, MockModelAdapter, OllamaAdapter, OpenAICompatibleAdapter
from .runner import ExperimentConfig, TrialPlan, run_experiment
from .statistics import aggregate_trials
from .system_executor import generate_candidate
from .tasks import generate_task
from .verdict import decide_verdict

_ENV_RE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
_MODEL_DEPENDENT_ARMS = {"A_DIRECT", "B_DIRECT_CHECKED", "D_INVERTED"}


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
    if len({(m.get("provider"), m.get("model")) for m in models}) < 3:
        raise ValueError("decisive runs require three distinct model configurations")
    if not {"state", "policy", "reconciliation"}.issubset(set(bench.get("families", []))):
        raise ValueError("decisive runs require all three task families")
    if len(set(bench.get("complexities", []))) < 4 or len(set(bench.get("qualities", []))) < 5:
        raise ValueError("decisive runs require four complexity and five executor-quality levels")
    if len(set(bench.get("seeds", []))) < 3 or int(bench.get("epochs", 0)) < 2:
        raise ValueError("decisive runs require at least three seeds and two epochs")
    preflight = raw.get("preflight") or {}
    cells = int(preflight.get("cells_per_model", 0))
    threshold = float(preflight.get("censorship_threshold", 1.0))
    if cells < 10 or cells > 20 or cells % 2:
        raise ValueError("decisive preflight requires an even 10-20 cells per model")
    if not (0.0 <= threshold <= 0.05):
        raise ValueError("decisive preflight censorship_threshold must be <= 0.05")
    for spec in models:
        if spec.get("provider") != "ollama":
            continue
        if spec.get("context_limit") is None:
            raise ValueError("decisive Ollama runs require an explicit context_limit")
        if spec.get("think") is not False:
            raise ValueError("decisive Ollama runs require think: false")
        if spec.get("format_json") is not True:
            raise ValueError("decisive Ollama runs require format_json: true")
        if int(spec.get("max_retries") or 0) < 2:
            raise ValueError("decisive Ollama runs require at least two transport retries")


def load_config(path: str | Path) -> dict[str, Any]:
    raw = _expand_env(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})
    if not raw.get("models"):
        raise ValueError("configuration must define at least one model")
    _validate_decisive(raw)
    return raw


def _experiment_config(raw: dict[str, Any]) -> ExperimentConfig:
    bench = dict(raw.get("benchmark") or {})
    for key in {"families", "complexities", "qualities", "seeds", "arms"}:
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
            out.append(MockModelAdapter(**common, seed=int(spec.get("seed", 0)), executor_accuracy=float(spec.get("executor_accuracy", 1.0)), auditor_accuracy=float(spec.get("auditor_accuracy", 1.0))))
        elif provider == "ollama":
            out.append(OllamaAdapter(**common, base_url=str(spec.get("base_url", "http://127.0.0.1:11434")), timeout_s=float(spec.get("timeout_s", 180.0)), temperature=float(spec.get("temperature", 0.0)), max_tokens=int(spec.get("max_tokens", 1024)), max_retries=int(spec.get("max_retries", 0)), retry_backoff_s=float(spec.get("retry_backoff_s", 1.0)), think=spec.get("think"), format_json=bool(spec.get("format_json", False)), context_limit=int(spec["context_limit"]) if spec.get("context_limit") is not None else None))
        elif provider == "openai-compatible":
            api_key = None
            if spec.get("api_key_env"):
                api_key = os.environ.get(str(spec["api_key_env"]))
                if not api_key:
                    raise ValueError(f"API key environment variable {spec['api_key_env']} is not set")
            out.append(OpenAICompatibleAdapter(**common, base_url=str(spec["base_url"]), api_key=api_key, timeout_s=float(spec.get("timeout_s", 180.0)), temperature=float(spec.get("temperature", 0.0)), max_tokens=int(spec.get("max_tokens", 1024)), price_per_m_input=float(spec["price_per_m_input"]) if spec.get("price_per_m_input") is not None else None, price_per_m_output=float(spec["price_per_m_output"]) if spec.get("price_per_m_output") is not None else None))
        else:
            raise ValueError(f"unknown model provider: {provider}")
    return out


def _preflight_models(models: list[Any], *, cells_per_model: int = 12, censorship_threshold: float = 0.05) -> list[dict[str, Any]]:
    if cells_per_model < 10 or cells_per_model > 20 or cells_per_model % 2:
        raise ValueError("preflight cells_per_model must be an even value from 10 through 20")
    pairs = cells_per_model // 2
    probes = [(family, complexity) for complexity in (1, 4) for family in ("state", "policy", "reconciliation")][:pairs]
    if len(probes) < pairs:
        raise ValueError("requested preflight size exceeds representative probe set")

    evidence: list[dict[str, Any]] = []
    for model in models:
        if str(getattr(model, "provider", "")) != "ollama":
            continue
        model_name = str(getattr(model, "model", "unknown"))
        censored = 0
        attempted = 0
        latencies: list[float] = []
        retries = 0
        max_prompt_chars = 0

        for probe_index, (family, complexity) in enumerate(probes):
            task = generate_task(family, complexity, 20260831 + probe_index)
            candidate = generate_candidate(task, 0.60, 20261831 + probe_index)
            calls = [
                ("preflight_executor", _executor_messages(task), _parse_actions, None),
                ("preflight_auditor", _auditor_messages(task, candidate), _parse_audit, candidate.id),
            ]
            for role, messages, parser, candidate_id in calls:
                attempted += 1
                max_prompt_chars = max(max_prompt_chars, sum(len(m["content"]) for m in messages))
                try:
                    result = model.complete(messages, role=role, context={"run_id": "preflight", "trial_id": f"preflight-{model_name}-{probe_index}-{role}", "call_id": f"preflight-{model_name}-{probe_index}-{role}", "candidate_id": candidate_id})
                except GenerationCensored:
                    censored += 1
                    continue
                try:
                    parser(result.text)
                except Exception as exc:
                    raise ValueError(f"preflight {role.removeprefix('preflight_')} JSON contract failed for {model_name}: {type(exc).__name__}: {exc}") from exc
                latencies.append(result.record.latency_s)
                retries += result.record.retry_number

        censorship_rate = censored / attempted if attempted else 0.0
        row = {
            "model": model_name,
            "provider": "ollama",
            "cells_attempted": attempted,
            "generation_censored": censored,
            "censorship_rate": censorship_rate,
            "censorship_threshold": censorship_threshold,
            "executor_parse_ok": True,
            "auditor_parse_ok": True,
            "max_prompt_chars": max_prompt_chars,
            "total_latency_s": sum(latencies),
            "total_retries": retries,
            "context_limit": getattr(model, "context_limit", None),
            "think": getattr(model, "think", None),
            "format_json": getattr(model, "format_json", None),
        }
        evidence.append(row)
        if censorship_rate > censorship_threshold:
            raise RuntimeError(f"preflight censorship threshold exceeded for {model_name}: {censored}/{attempted}={censorship_rate:.3%} > {censorship_threshold:.3%}")
    return evidence


def _sanitized_models(raw: dict[str, Any]) -> list[dict[str, Any]]:
    return [{k: v for k, v in spec.items() if k not in {"api_key", "token", "authorization"}} for spec in raw.get("models", [])]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Benchmark direct-AI execution versus non-AI execution + AI auditing.")
    p.add_argument("--config", required=True)
    p.add_argument("--output-dir", default=None)
    p.add_argument("--run-id", default=None)
    p.add_argument("--checkpoint", default=None)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--progress", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.resume and not args.checkpoint:
        raise ValueError("--resume requires --checkpoint")
    raw = load_config(args.config)
    config = _experiment_config(raw)
    report_cfg = raw.get("report") or {}
    models = _build_models(raw, bool(report_cfg.get("capture_content", True)))
    checkpoint = CheckpointStore(args.checkpoint) if args.checkpoint else None
    pf = raw.get("preflight") or {}
    preflight_evidence = _preflight_models(models, cells_per_model=int(pf.get("cells_per_model", 12)), censorship_threshold=float(pf.get("censorship_threshold", 0.05)))
    for item in preflight_evidence:
        print(f"PREFLIGHT OK model={item['model']} cells={item['cells_attempted']} censored={item['generation_censored']} rate={item['censorship_rate']:.2%} retries={item['total_retries']}", flush=True)

    progress_callback = None
    if args.progress:
        def render_progress(completed: int, total: int, item: TrialPlan) -> None:
            pct = 100.0 * completed / total if total else 100.0
            width = 30
            filled = min(width, int(round(width * completed / total))) if total else width
            model = getattr(models[item.model_index], "model", "none") if item.arm in _MODEL_DEPENDENT_ARMS else "CONTROL"
            print(f"PROGRESS [{'#' * filled}{'-' * (width - filled)}] {completed}/{total} {pct:6.2f}% model={model} arm={item.arm} family={item.family} complexity={item.complexity} quality={item.quality:.2f} seed={item.seed} epoch={item.epoch}", flush=True)
        progress_callback = render_progress

    try:
        result = run_experiment(config, models, run_id=args.run_id, checkpoint_store=checkpoint, resume=bool(args.resume), progress_callback=progress_callback)
    except GenerationCensored as exc:
        print("GENERATION_CENSORED: output budget exhausted with empty final content; affected trial was NOT scored.", flush=True)
        print(json.dumps(exc.record.to_dict(), sort_keys=True, default=str), flush=True)
        return 4
    except ModelCallError as exc:
        print("INFRASTRUCTURE_FAILURE: model call did not recover; affected trial was NOT scored.", flush=True)
        print(json.dumps(exc.record.to_dict(), sort_keys=True, default=str), flush=True)
        return 3

    summary = aggregate_trials(result.trials, config.bootstrap_samples, config.bootstrap_seed)
    verdict = decide_verdict(summary, config)
    provenance = collect_provenance()
    provenance.update({"config_path": str(Path(args.config).resolve()), "models": _sanitized_models(raw), "preflight": preflight_evidence, "capture_content": bool(report_cfg.get("capture_content", True)), "include_raw_rows": bool(report_cfg.get("include_raw_rows", True)), "checkpoint_path": str(Path(args.checkpoint).resolve()) if args.checkpoint else None, "resumed": bool(args.resume), "run_started_at": result.started_at, "run_ended_at": result.ended_at})
    root = Path(args.output_dir or raw.get("output_dir") or "runs")
    paths = ArtifactWriter(root / result.run_id).write_all(result, summary, verdict, provenance, include_raw_rows=bool(report_cfg.get("include_raw_rows", True)))
    print(Path(paths["report"]).read_text(encoding="utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
