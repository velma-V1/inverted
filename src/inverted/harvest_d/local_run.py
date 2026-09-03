from __future__ import annotations

import argparse
from pathlib import Path

from .artifacts import ArtifactWriter
from .cases import load_cases
from .experiment import CallBudget
from .models import ModelAdapter, OllamaChatAdapter
from .runner import ModelTrialRunner
from .telemetry import SystemInvolvement
from .types import RouteMode


def run_cases(case_path: str | Path, output: str | Path, adapter: ModelAdapter, *, route: RouteMode,
              max_calls: int, system_prompt: str | None = None, involvement: SystemInvolvement | None = None) -> dict[str, object]:
    cases = load_cases(case_path); budget = CallBudget(max_calls); runner = ModelTrialRunner(); writer = ArtifactWriter(output)
    involvement = involvement or SystemInvolvement()
    trials, prompts, responses, token_rows, latency_rows = [], [], [], [], []
    for case in cases:
        budget.consume()
        result = runner.run(case, adapter, route=route, involvement=involvement, system_prompt=system_prompt)
        trials.append(result.to_dict())
        prompts.append({"case_id": case.case_id, "physical_model_call_id": result.physical_model_call_id,
                        "prompt": case.model_prompt(), "system_prompt": system_prompt})
        responses.append({"case_id": case.case_id, "physical_model_call_id": result.physical_model_call_id,
                          "model": result.model, "response_text": result.response_text, "semantic_success": result.semantic_success})
        token_rows.append({"physical_model_call_id": result.physical_model_call_id, "input_tokens": result.input_tokens, "output_tokens": result.output_tokens})
        latency_rows.append({"physical_model_call_id": result.physical_model_call_id, "latency_ms": result.latency_ms})
    writer.write_jsonl("trials.jsonl", trials); writer.write_jsonl("prompts.jsonl", prompts); writer.write_jsonl("responses.jsonl", responses)
    writer.write_jsonl("model_calls.jsonl", [{"physical_model_call_id": r["physical_model_call_id"], "model": r["model"], "route": r["route"]} for r in trials])
    writer.write_csv("tokens.csv", token_rows, fieldnames=("physical_model_call_id", "input_tokens", "output_tokens"))
    writer.write_csv("latency.csv", latency_rows, fieldnames=("physical_model_call_id", "latency_ms"))
    summary = {"mode": "explicit-local-model-run", "model": adapter.model_id, "route": route.value, "cases": len(cases),
               "calls": budget.used, "max_calls": max_calls, "retries": 0, "semantic_successes": sum(bool(r["semantic_success"]) for r in trials)}
    writer.write_json("00-HARVEST-D-LOCAL-RUN.json", summary); writer.finalize(); return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run an explicit local-model Harvest D case set")
    p.add_argument("--cases", required=True); p.add_argument("--output", required=True); p.add_argument("--model", required=True)
    p.add_argument("--base-url", default="http://127.0.0.1:11434"); p.add_argument("--max-calls", type=int, required=True)
    p.add_argument("--route", choices=[x.value for x in RouteMode], default=RouteMode.QWEN_STANDARD.value); p.add_argument("--system-prompt-file")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    system_prompt = Path(args.system_prompt_file).read_text(encoding="utf-8") if args.system_prompt_file else None
    adapter = OllamaChatAdapter(args.model, base_url=args.base_url)
    run_cases(args.cases, args.output, adapter, route=RouteMode(args.route), max_calls=args.max_calls, system_prompt=system_prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
