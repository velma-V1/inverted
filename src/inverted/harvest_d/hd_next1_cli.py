from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen

from .hd_next1_campaign import HDNext1Campaign
from .hd_next1_config import HDNext1ConfigError, load_hd_next1_config
from .hd_next1_preregistration import build_preregistration_package
from .models import OllamaChatAdapter


class HDNext1PreflightError(RuntimeError):
    pass


def _ollama_preflight(config: dict[str, object]) -> dict[str, str]:
    base = str(config["ollama_base_url"]).rstrip("/")
    try:
        with urlopen(Request(base + "/api/tags", method="GET"), timeout=10.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise HDNext1PreflightError("Ollama preflight failed before inference") from exc
    installed = {
        str(row.get("name") or row.get("model") or ""): str(row.get("digest") or "")
        for row in payload.get("models", [])
        if isinstance(row, dict)
    }
    required = dict(config["models"])
    digests: dict[str, str] = {}
    for key, model_id in required.items():
        if str(model_id) not in installed:
            raise HDNext1PreflightError(f"required model is not installed: {model_id}")
        if not installed[str(model_id)]:
            raise HDNext1PreflightError(f"model digest unavailable: {model_id}")
        digests[str(key)] = installed[str(model_id)]
    return digests


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build or execute HD-NEXT-1")
    parser.add_argument("--config", default="configs/harvest-d-hd-next-1.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--preregistration", default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--owner-authorization", default=None)
    parser.add_argument("--max-calls", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = load_hd_next1_config(args.config)
        output = Path(args.output)
        prereg = Path(args.preregistration or args.output)
        if not args.execute:
            summary = build_preregistration_package(Path.cwd(), output, config)
            print(json.dumps({"experiment_id": "HD-NEXT-1", "physical_model_calls": 0, "ready_for_owner_authorization": summary.ready_for_owner_authorization}, sort_keys=True))
            return 0
        if not args.owner_authorization:
            raise HDNext1PreflightError("owner execution authorization is required")
        owner = json.loads(Path(args.owner_authorization).read_text(encoding="utf-8"))
        digests = _ollama_preflight(config)
        adapters = {
            key: OllamaChatAdapter(str(model_id), base_url=str(config["ollama_base_url"]), generation_options=dict(config["generation_options"]))
            for key, model_id in dict(config["models"]).items()
        }
        campaign = HDNext1Campaign(output, prereg_root=prereg, config=config, adapters=adapters, owner_authorization=owner)
        result = campaign.run_authorized(max_calls=args.max_calls)
        (output / "runtime_model_digests.json").write_text(json.dumps(digests, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"physical_model_calls": result.physical_model_calls, "final_state": result.final_state}, sort_keys=True))
        return 0 if result.final_state == "COMPLETE" else 2
    except (HDNext1ConfigError, HDNext1PreflightError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"HD-NEXT-1 ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
