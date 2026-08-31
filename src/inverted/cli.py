from __future__ import annotations

import argparse
from dataclasses import fields
import json
import os
from pathlib import Path
import re
from typing import Any, Callable

import yaml

from .arms import _auditor_messages, _executor_messages, _parse_actions, _parse_audit
from .artifacts import ArtifactWriter, collect_provenance
from .checkpoint import CheckpointStore
from .models import GenerationCensored, ModelCallError, MockModelAdapter, OllamaAdapter, OpenAICompatibleAdapter
from .runner import ExperimentConfig, TrialPlan, run_experiment
from .statistics import aggregate_trials, bootstrap_rate_difference
from .system_executor import generate_candidate
from .tasks import generate_task
from .telemetry import ModelCallRecord
from .value_checkpoints import _persist_value_checkpoint
from .verdict import decide_interim_stop, decide_verdict

_ENV_RE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
_MODEL_DEPENDENT_ARMS = {"A_DIRECT", "B_DIRECT_CHECKED", "D_INVERTED"}
_REQUIRED_OLLAMA_TELEMETRY = {"thinking", "content", "prompt_eval_count", "eval_count", "done_reason"}


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        match = _ENV_RE.match(value)
        if match:
            name = match.group(1)
            if name not in os.environ:
                raise ValueError(f"required environment variable {name} is not set")
            return os.environ[name]
        return value
    if isinstance(value, list): return [_expand_env(x) for x in value]
    if isinstance(value, dict): return {k: _expand_env(v) for k, v in value.items()}
    return value


def _validate_decisive(raw: dict[str, Any]) -> None:
    bench = raw.get("benchmark", {})
    if not bench.get("decisive", False): return
    models = raw.get("models") or []
    if any(m.get("provider") == "mock" for m in models): raise ValueError("decisive runs may not use mock models")
    if len(models) < 3 or len({(m.get("provider"), m.get("model")) for m in models}) < 3: raise ValueError("decisive runs require three distinct model configurations")
    if not {"state", "policy", "reconciliation"}.issubset(set(bench.get("families", []))): raise ValueError("decisive runs require all three task families")
    if len(set(bench.get("complexities", []))) < 4 or len(set(bench.get("qualities", []))) < 5: raise ValueError("decisive runs require four complexity and five executor-quality levels")
    seeds = tuple(bench.get("seeds", []))
    if len(set(seeds)) < 3 or int(bench.get("epochs", 0)) < 2: raise ValueError("decisive runs require at least three seeds and two epochs")

    value_stages = tuple(int(x) for x in bench.get("value_checkpoint_seed_stages", []) or [])
    stages = tuple(int(x) for x in bench.get("sequential_seed_stages", []) or [])
    confidences = tuple(float(x) for x in bench.get("sequential_interim_confidence", []) or [])
    if value_stages:
        if tuple(sorted(set(value_stages))) != value_stages or any(x <= 0 or x >= len(seeds) for x in value_stages):
            raise ValueError("value_checkpoint_seed_stages must be strictly increasing partial cumulative seed counts")
        if not stages:
            raise ValueError("decisive value checkpoints require sequential_seed_stages")
    if stages:
        if tuple(sorted(set(stages))) != stages or any(x <= 0 for x in stages):
            raise ValueError("sequential_seed_stages must be strictly increasing positive cumulative seed counts")
        if stages[-1] != len(seeds):
            raise ValueError("final sequential seed stage must include every configured seed")
        if value_stages and value_stages[-1] >= stages[0]:
            raise ValueError("exploratory value checkpoints must occur before the first decisive sequential stage")
        if len(confidences) != len(stages) - 1:
            raise ValueError("sequential_interim_confidence must define one confidence level for each interim stage")
        if any(c <= 0.95 or c >= 1.0 for c in confidences):
            raise ValueError("sequential interim confidence levels must be stricter than 95% and below 100%")
    elif confidences:
        raise ValueError("sequential_interim_confidence requires sequential_seed_stages")

    preflight = raw.get("preflight") or {}
    cells = int(preflight.get("cells_per_model", 0))
    if cells < 10 or cells > 20 or cells % 2: raise ValueError("decisive preflight requires an even 10-20 cells per model")
    if "censorship_threshold" in preflight:
        raise ValueError("decisive preflight must use a zero-censorship count gate, not a percentage threshold")
    if int(preflight.get("max_generation_censored", -1)) != 0:
        raise ValueError("decisive preflight requires max_generation_censored: 0")
    for spec in models:
        if spec.get("provider") != "ollama": continue
        if spec.get("context_limit") is None: raise ValueError("decisive Ollama runs require an explicit context_limit")
        if spec.get("think") is not False: raise ValueError("decisive Ollama runs require think: false")
        if spec.get("format_json") is not True: raise ValueError("decisive Ollama runs require format_json: true")
        if int(spec.get("max_retries") or 0) < 2: raise ValueError("decisive Ollama runs require at least two transport retries")


def load_config(path: str | Path) -> dict[str, Any]:
    raw = _expand_env(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})
    if not raw.get("models"): raise ValueError("configuration must define at least one model")
    _validate_decisive(raw)
    return raw


def _experiment_config(raw: dict[str, Any]) -> ExperimentConfig:
    bench = dict(raw.get("benchmark") or {})
    for key in {"families", "complexities", "qualities", "seeds", "arms", "value_checkpoint_seed_stages", "sequential_seed_stages", "sequential_interim_confidence"}:
        if key in bench: bench[key] = tuple(bench[key])
    allowed = {f.name for f in fields(ExperimentConfig)}
    unknown = set(bench) - allowed
    if unknown: raise ValueError(f"unknown benchmark config fields: {sorted(unknown)}")
    return ExperimentConfig(**bench)


def _build_models(raw: dict[str, Any], capture_content: bool) -> list[Any]:
    out = []
    for spec in raw.get("models", []):
        provider = spec.get("provider"); common = {"model": str(spec["model"]), "capture_content": capture_content}
        if provider == "mock":
            out.append(MockModelAdapter(**common, seed=int(spec.get("seed", 0)), executor_accuracy=float(spec.get("executor_accuracy", 1.0)), auditor_accuracy=float(spec.get("auditor_accuracy", 1.0))))
        elif provider == "ollama":
            out.append(OllamaAdapter(**common, base_url=str(spec.get("base_url", "http://127.0.0.1:11434")), timeout_s=float(spec.get("timeout_s", 180.0)), temperature=float(spec.get("temperature", 0.0)), max_tokens=int(spec.get("max_tokens", 1024)), max_retries=int(spec.get("max_retries", 0)), retry_backoff_s=float(spec.get("retry_backoff_s", 1.0)), think=spec.get("think"), format_json=bool(spec.get("format_json", False)), context_limit=int(spec["context_limit"]) if spec.get("context_limit") is not None else None))
        elif provider == "openai-compatible":
            api_key = os.environ.get(str(spec["api_key_env"])) if spec.get("api_key_env") else None
            if spec.get("api_key_env") and not api_key: raise ValueError(f"API key environment variable {spec['api_key_env']} is not set")
            out.append(OpenAICompatibleAdapter(**common, base_url=str(spec["base_url"]), api_key=api_key, timeout_s=float(spec.get("timeout_s", 180.0)), temperature=float(spec.get("temperature", 0.0)), max_tokens=int(spec.get("max_tokens", 1024)), price_per_m_input=float(spec["price_per_m_input"]) if spec.get("price_per_m_input") is not None else None, price_per_m_output=float(spec["price_per_m_output"]) if spec.get("price_per_m_output") is not None else None))
        else: raise ValueError(f"unknown model provider: {provider}")
    return out


def _append_call_record(path: Path, record: ModelCallRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record.to_dict(), sort_keys=True, default=str) + "\n")
        handle.flush(); os.fsync(handle.fileno())


def _validate_ollama_telemetry_record(record: ModelCallRecord) -> None:
    telemetry = record.raw_provider_telemetry
    if not isinstance(telemetry, dict):
        raise ValueError(f"preflight telemetry missing raw_provider_telemetry for {record.model}/{record.role}")
    missing = _REQUIRED_OLLAMA_TELEMETRY - set(telemetry)
    if missing:
        raise ValueError(f"preflight telemetry missing fields for {record.model}/{record.role}: {sorted(missing)}")
    attempts = telemetry.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        raise ValueError(f"preflight telemetry missing attempt ledger for {record.model}/{record.role}")
    for index, attempt in enumerate(attempts):
        if not isinstance(attempt, dict):
            raise ValueError(f"preflight telemetry attempt {index} is not a mapping for {record.model}/{record.role}")
        attempt_missing = _REQUIRED_OLLAMA_TELEMETRY - set(attempt)
        if attempt_missing:
            raise ValueError(f"preflight telemetry attempt {index} missing fields for {record.model}/{record.role}: {sorted(attempt_missing)}")


def _preflight_models(
    models: list[Any],
    *,
    cells_per_model: int = 12,
    max_generation_censored: int = 0,
    telemetry_callback: Callable[[ModelCallRecord], None] | None = None,
    failure_callback: Callable[[ModelCallRecord], None] | None = None,
) -> list[dict[str, Any]]:
    if cells_per_model < 10 or cells_per_model > 20 or cells_per_model % 2: raise ValueError("preflight cells_per_model must be an even value from 10 through 20")
    if int(max_generation_censored) != 0: raise ValueError("preflight max_generation_censored must be 0")
    pairs = cells_per_model // 2
    probes = [(family, complexity) for complexity in (1, 4) for family in ("state", "policy", "reconciliation")][:pairs]
    if len(probes) < pairs: raise ValueError("requested preflight size exceeds representative probe set")
    evidence = []
    for model in models:
        if str(getattr(model, "provider", "")) != "ollama": continue
        model_name = str(getattr(model, "model", "unknown"))
        censored = attempted = retries = 0
        executor_parse_failures = auditor_parse_failures = 0
        latencies = []
        max_prompt_chars = 0
        try:
            for probe_index, (family, complexity) in enumerate(probes):
                task = generate_task(family, complexity, 20260831 + probe_index); candidate = generate_candidate(task, 0.60, 20261831 + probe_index)
                for role, messages, parser, candidate_id in [("preflight_executor", _executor_messages(task), _parse_actions, None), ("preflight_auditor", _auditor_messages(task, candidate), _parse_audit, candidate.id)]:
                    attempted += 1; max_prompt_chars = max(max_prompt_chars, sum(len(m["content"]) for m in messages))
                    try:
                        result = model.complete(messages, role=role, context={"run_id": "preflight", "trial_id": f"preflight-{model_name}-{probe_index}-{role}", "call_id": f"preflight-{model_name}-{probe_index}-{role}", "candidate_id": candidate_id})
                    except GenerationCensored as exc:
                        censored += 1
                        _validate_ollama_telemetry_record(exc.record)
                        if telemetry_callback: telemetry_callback(exc.record)
                        if failure_callback: failure_callback(exc.record)
                        continue
                    except ModelCallError as exc:
                        _validate_ollama_telemetry_record(exc.record)
                        if telemetry_callback: telemetry_callback(exc.record)
                        if failure_callback: failure_callback(exc.record)
                        raise
                    _validate_ollama_telemetry_record(result.record)
                    latencies.append(result.record.latency_s); retries += result.record.retry_number
                    try:
                        parser(result.text)
                    except Exception as exc:
                        result.record.parse_success = False
                        result.record.parse_error = f"{type(exc).__name__}: {exc}"
                        if role.endswith("executor"):
                            executor_parse_failures += 1
                        else:
                            auditor_parse_failures += 1
                        if telemetry_callback: telemetry_callback(result.record)
                        continue
                    result.record.parse_success = True
                    if telemetry_callback: telemetry_callback(result.record)
            row = {
                "model": model_name,
                "provider": "ollama",
                "cells_attempted": attempted,
                "generation_censored": censored,
                "censorship_policy": "ZERO_CENSORSHIP",
                "max_generation_censored": 0,
                "executor_parse_ok": executor_parse_failures == 0,
                "auditor_parse_ok": auditor_parse_failures == 0,
                "executor_parse_failures": executor_parse_failures,
                "auditor_parse_failures": auditor_parse_failures,
                "max_prompt_chars": max_prompt_chars,
                "total_latency_s": sum(latencies),
                "total_retries": retries,
                "context_limit": getattr(model, "context_limit", None),
                "think": getattr(model, "think", None),
                "format_json": getattr(model, "format_json", None),
            }
            evidence.append(row)
            if censored > max_generation_censored:
                raise RuntimeError(f"zero-censorship preflight failed for {model_name}: {censored}/{attempted} GENERATION_CENSORED; required 0/{attempted}")
        finally:
            unload = getattr(model, "unload", None)
            if callable(unload):
                try:
                    unload()
                except Exception:
                    pass
    return evidence


def _sanitized_models(raw: dict[str, Any]) -> list[dict[str, Any]]:
    return [{k: v for k, v in spec.items() if k not in {"api_key", "token", "authorization"}} for spec in raw.get("models", [])]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Benchmark direct-AI execution versus non-AI execution + AI auditing.")
    p.add_argument("--config", required=True); p.add_argument("--output-dir", default=None); p.add_argument("--run-id", default=None); p.add_argument("--checkpoint", default=None); p.add_argument("--resume", action="store_true"); p.add_argument("--progress", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.resume and not args.checkpoint: raise ValueError("--resume requires --checkpoint")
    raw = load_config(args.config); config = _experiment_config(raw); report_cfg = raw.get("report") or {}; root = Path(args.output_dir or raw.get("output_dir") or "runs")
    models = _build_models(raw, bool(report_cfg.get("capture_content", True))); checkpoint = CheckpointStore(args.checkpoint) if args.checkpoint else None
    ledger_root = Path(args.checkpoint).parent if args.checkpoint else root
    run_label = args.run_id or "unassigned"
    failure_log = ledger_root / f"{run_label}.call-failures.jsonl"
    preflight_log = ledger_root / f"{run_label}.preflight-model-calls.jsonl"
    persist_failure = lambda record: _append_call_record(failure_log, record)
    persist_preflight = lambda record: _append_call_record(preflight_log, record)
    pf = raw.get("preflight") or {}
    try:
        preflight_evidence = _preflight_models(
            models,
            cells_per_model=int(pf.get("cells_per_model", 12)),
            max_generation_censored=int(pf.get("max_generation_censored", 0)),
            telemetry_callback=persist_preflight,
            failure_callback=persist_failure,
        )
    except (GenerationCensored, ModelCallError, RuntimeError, ValueError) as exc:
        print(f"PREFLIGHT_FAILURE: {type(exc).__name__}: {exc}", flush=True)
        return 2
    for item in preflight_evidence:
        print(
            f"PREFLIGHT PASS model={item['model']} censored={item['generation_censored']}/{item['cells_attempted']} "
            f"policy={item['censorship_policy']} retries={item['total_retries']} "
            f"executor_parse_failures={item['executor_parse_failures']} auditor_parse_failures={item['auditor_parse_failures']}",
            flush=True,
        )

    progress_callback = None
    if args.progress:
        from .progress import ProgressTracker

        initial_completed = len(checkpoint.load_trials()) if args.resume and checkpoint is not None else 0
        tracker = ProgressTracker(initial_completed=initial_completed)

        def render_progress(completed: int, total: int, item: TrialPlan) -> None:
            model = getattr(models[item.model_index], "model", "none") if item.arm in _MODEL_DEPENDENT_ARMS else "CONTROL"
            current = (
                f"model={model} arm={item.arm} family={item.family} complexity={item.complexity} "
                f"quality={item.quality:.2f} seed={item.seed} epoch={item.epoch}"
            )
            print(tracker.render(completed, total, current), flush=True)

        progress_callback = render_progress

    stage_callback = None
    if config.value_checkpoint_seed_stages or config.sequential_seed_stages:
        def evaluate_stage(stage_number: int, completed_seed_count: int, total_seed_count: int, trials: list[Any]) -> dict[str, Any]:
            interim_summary = aggregate_trials(trials, config.bootstrap_samples, config.bootstrap_seed)
            pct = 100.0 * completed_seed_count / total_seed_count

            if completed_seed_count in config.value_checkpoint_seed_stages:
                paths = _persist_value_checkpoint(ledger_root, run_label, completed_seed_count, total_seed_count, interim_summary)
                primary = interim_summary.get("primary", {})
                print(
                    f"VALUE CHECKPOINT: seeds={completed_seed_count}/{total_seed_count} ({pct:.0f}%) "
                    f"D-A={primary.get('d_minus_a')} D-B={primary.get('d_minus_b')} status=EXPLORATORY_NON_DECISIVE",
                    flush=True,
                )
                print(f"VALUE CHECKPOINT FILES: {paths['json']} | {paths['text']}", flush=True)
                return {"stop": False, "verdict": "VALUE_CHECK", "stage": stage_number, "completed_seed_count": completed_seed_count}

            if completed_seed_count not in config.sequential_seed_stages:
                return {"stop": False, "verdict": "CONTINUE"}
            sequential_index = config.sequential_seed_stages.index(completed_seed_count)
            if sequential_index >= len(config.sequential_interim_confidence):
                return {"stop": False, "verdict": "CONTINUE"}
            confidence = float(config.sequential_interim_confidence[sequential_index])
            interval = bootstrap_rate_difference(
                trials, "D_INVERTED", "A_DIRECT",
                config.bootstrap_samples, config.bootstrap_seed + sequential_index + 1,
                confidence=confidence,
            )
            decision = decide_interim_stop(
                interim_summary, config,
                stage_number=sequential_index + 1,
                completed_seed_count=completed_seed_count,
                confidence=confidence,
                primary_interval=interval,
            )
            print(
                f"SEQUENTIAL STAGE {sequential_index + 1}: seeds={completed_seed_count}/{total_seed_count} ({pct:.0f}%) "
                f"confidence={confidence:.3f} decision={decision.get('verdict')} stop={decision.get('stop')}",
                flush=True,
            )
            if decision.get("stop"):
                print(f"SEQUENTIAL STOP: {decision.get('reason')}", flush=True)
            return decision
        stage_callback = evaluate_stage

    try:
        result = run_experiment(
            config, models, run_id=args.run_id,
            checkpoint_store=checkpoint, resume=bool(args.resume),
            progress_callback=progress_callback, stage_callback=stage_callback,
        )
    except GenerationCensored as exc:
        persist_failure(exc.record); print("GENERATION_CENSORED: output budget exhausted with empty final content; affected trial was NOT scored.", flush=True); print(json.dumps(exc.record.to_dict(), sort_keys=True, default=str), flush=True); return 4
    except ModelCallError as exc:
        persist_failure(exc.record); print("INFRASTRUCTURE_FAILURE: model call did not recover; affected trial was NOT scored.", flush=True); print(json.dumps(exc.record.to_dict(), sort_keys=True, default=str), flush=True); return 3

    summary = aggregate_trials(result.trials, config.bootstrap_samples, config.bootstrap_seed)
    verdict = result.sequential_decision if result.stopped_early and result.sequential_decision else decide_verdict(summary, config)
    provenance = collect_provenance()
    provenance.update({
        "config_path": str(Path(args.config).resolve()),
        "models": _sanitized_models(raw),
        "preflight": preflight_evidence,
        "preflight_call_log": str(preflight_log.resolve()),
        "failure_log": str(failure_log.resolve()),
        "capture_content": bool(report_cfg.get("capture_content", True)),
        "include_raw_rows": bool(report_cfg.get("include_raw_rows", True)),
        "checkpoint_path": str(Path(args.checkpoint).resolve()) if args.checkpoint else None,
        "resumed": bool(args.resume),
        "run_started_at": result.started_at,
        "run_ended_at": result.ended_at,
        "value_checkpoint_seed_stages": list(config.value_checkpoint_seed_stages),
        "sequential_seed_stages": list(config.sequential_seed_stages),
        "sequential_interim_confidence": list(config.sequential_interim_confidence),
        "stopped_early": result.stopped_early,
        "completed_seed_count": result.completed_seed_count,
        "planned_trial_units": result.planned_trial_units,
        "completed_trial_units": len(result.trials),
        "sequential_decision": result.sequential_decision,
    })
    paths = ArtifactWriter(root / result.run_id).write_all(result, summary, verdict, provenance, include_raw_rows=bool(report_cfg.get("include_raw_rows", True))); print(Path(paths["report"]).read_text(encoding="utf-8"), end=""); return 0


if __name__ == "__main__": raise SystemExit(main())