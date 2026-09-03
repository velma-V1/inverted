from __future__ import annotations

import argparse
from pathlib import Path

from .campaign import HarvestDConfig, HarvestDCampaign


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="INVERTED Harvest D causal-identifiability harness")
    p.add_argument("--config", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--dry-run", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = HarvestDConfig.from_json(args.config)
    if not args.dry_run:
        raise SystemExit("Real-model execution uses inverted.harvest_d.local_run explicitly; normal Harvest D CLI remains model-free.")
    HarvestDCampaign(config).dry_run(Path(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
