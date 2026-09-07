from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import yaml

from .audit import audit_run
from .campaign import run_campaign
from .config import QWEN_MODEL
from .instrument import LABEL, instrument_adapters


def _probe(command: list[str]) -> dict:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
        return {"ok": completed.returncode == 0, "returncode": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def preflight() -> dict:
    probes = {
        "docker": _probe(["docker", "version", "--format", "{{.Server.Version}}"]),
        "ollama": _probe(["ollama", "show", QWEN_MODEL]),
        "claude": _probe(["claude", "--version"]),
        "codex": _probe(["cmd", "/c", "codex", "--version"]),
    }
    return {"passed": all(x.get("ok") for x in probes.values()), "probes": probes}


def load_config(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="inverted-brain")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--instrument-smoke", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    if args.preflight:
        result = preflight()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["passed"] else 2
    if args.instrument_smoke:
        smoke = dict(config)
        smoke.update({"frontier_pool":18,"harvest_cases":4,"fresh_holdout":24,"run_ceiling":120})
        summary = run_campaign(smoke, args.output_dir, resume=not args.no_resume, adapters=instrument_adapters())
        print(LABEL)
        print(json.dumps(summary, indent=2, sort_keys=True))
        audit = audit_run(args.output_dir, run_ceiling=120)
        print(json.dumps({"audit":audit}, indent=2, sort_keys=True))
        return 0 if audit["passed"] else 3
    if not args.live:
        print("REFUSING LIVE CAMPAIGN: pass --live explicitly. Use --instrument-smoke for non-scientific validation.")
        return 4
    pf = preflight()
    if not pf["passed"]:
        print(json.dumps(pf, indent=2, sort_keys=True))
        return 2
    summary = run_campaign(config, args.output_dir, resume=not args.no_resume)
    print(json.dumps(summary, indent=2, sort_keys=True))
    audit = audit_run(args.output_dir, run_ceiling=int(config.get("run_ceiling",200)))
    print(json.dumps({"audit":audit}, indent=2, sort_keys=True))
    return 0 if audit["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
