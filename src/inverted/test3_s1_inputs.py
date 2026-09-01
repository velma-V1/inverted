from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .test2_local import LOCAL_MODELS
from .test3_s1_freeze import ANALYSIS_ONLY_COMPONENTS


@dataclass(frozen=True)
class S1ResolvedInputs:
    s0_dir: str
    test2_tier_a_dir: str
    preregistration: dict[str, Any]
    arms: tuple[dict[str, Any], ...]
    best_single_model: str
    repair_model: str
    exact_budget: int
    per_arm_call_cap: int
    holdout: str
    full_power_clusters: int | None


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not load S1 input {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"S1 input must be a JSON object: {path}")
    return value


def _resolve_source_path(raw: str, s0_dir: Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    direct = path.resolve()
    if direct.exists():
        return direct
    return (s0_dir.parent / path).resolve()


def _order_components(order: Any) -> list[str]:
    if order in (None, ""):
        return []
    return [part.strip() for part in str(order).split("->") if part.strip()]


def _validate_preregistration(prereg: dict[str, Any]) -> tuple[tuple[dict[str, Any], ...], int, int]:
    if prereg.get("arm_freeze_ready") is not True or prereg.get("status") != "S1_SCREEN_FROZEN_AWAITING_TIER_A_AUTHORIZATION":
        raise ValueError("S1 preregistration is not frozen for execution")
    if prereg.get("section") != "S1_FIXED_STACK_ORDER" or prereg.get("holdout") != "A":
        raise ValueError("S1 preregistration does not target frozen Holdout A")
    exact_budget = int(prereg.get("exact_budget") or 0)
    per_arm = int(prereg.get("physical_call_cap_per_arm") or 0)
    arms = tuple(dict(row) for row in (prereg.get("arms") or []) if isinstance(row, dict))
    if exact_budget != 80 or per_arm != 20 or len(arms) != 4:
        raise ValueError("S1 frozen budget must be exactly 80 calls across four 20-call arms")
    if sum(int(arm.get("physical_call_cap") or 0) for arm in arms) != exact_budget:
        raise ValueError("S1 arm call caps do not sum to the frozen exact budget")
    ids = [str(arm.get("arm_id") or "") for arm in arms]
    if ids != ["S1-A0", "S1-A1", "S1-A2", "S1-A3"]:
        raise ValueError("S1 arm identities are not the frozen A0-A3 contract")
    for arm in arms:
        forbidden = set(_order_components(arm.get("order"))).intersection(ANALYSIS_ONLY_COMPONENTS)
        if forbidden:
            raise ValueError(
                "S1 production arm contains analysis-only component(s): " + ", ".join(sorted(forbidden))
            )
    return arms, exact_budget, per_arm


def _find_test2_tier_a(manifest: dict[str, Any], s0_dir: Path) -> Path:
    rows = manifest.get("sources") or []
    matches = [row for row in rows if isinstance(row, dict) and row.get("source_class") == "test2_tier_a"]
    if len(matches) != 1:
        raise ValueError(f"S1 requires exactly one test2_tier_a source; found {len(matches)}")
    raw_path = str(matches[0].get("path") or "")
    if not raw_path:
        raise ValueError("test2_tier_a source path is missing")
    path = _resolve_source_path(raw_path, s0_dir)
    if not path.is_dir():
        raise ValueError(f"test2_tier_a source directory does not exist: {path}")
    return path


def _best_single_from_router_regret(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise ValueError(f"could not parse Test-2 router-regret.csv: {exc}") from exc
    matches = [row for row in rows if str(row.get("router_level") or "") == "best_single_model"]
    if len(matches) != 1:
        return ""
    return str(matches[0].get("model") or "")


def _load_model_evidence(test2_root: Path) -> tuple[str, str]:
    router_path = test2_root / "models" / "router-policy.json"
    router_regret_path = test2_root / "models" / "router-regret.csv"
    champions_path = test2_root / "models" / "role-champions.json"
    if not champions_path.is_file():
        raise ValueError("Test-2 Tier-A bundle is missing role-champions.json")
    champions = _load_mapping(champions_path)

    # Current Test-2 local evidence writes role champions to router-policy.json
    # and writes the best-single model as the `best_single_model` row in
    # router-regret.csv. Retain the earlier JSON shape as a compatibility
    # fallback without treating it as authoritative when the CSV exists.
    best_model = _best_single_from_router_regret(router_regret_path)
    if not best_model and router_path.is_file():
        router = _load_mapping(router_path)
        best = router.get("best_single_model")
        best_model = str(best.get("model") if isinstance(best, dict) else "")

    repair_model = str(champions.get("repairer") or "")
    if not best_model or not repair_model:
        raise ValueError("Test-2 Tier-A evidence does not identify best-single and repairer models")
    allowed = set(LOCAL_MODELS)
    if best_model not in allowed or repair_model not in allowed:
        raise ValueError("S1 selected model identity is outside the frozen Test-2 local model set")
    return best_model, repair_model


def load_s1_inputs(s0_dir: str | Path) -> S1ResolvedInputs:
    root = Path(s0_dir)
    if not root.is_dir():
        raise ValueError(f"S0 evidence directory does not exist: {root}")
    prereg = _load_mapping(root / "candidate_section1_preregistration.json")
    arms, exact_budget, per_arm = _validate_preregistration(prereg)
    manifest = _load_mapping(root / "source_manifest.json")
    test2_root = _find_test2_tier_a(manifest, root)
    best_single, repairer = _load_model_evidence(test2_root)
    power = prereg.get("power_evidence") if isinstance(prereg.get("power_evidence"), dict) else {}
    full_power = power.get("recommended_clusters")
    return S1ResolvedInputs(
        s0_dir=str(root.resolve()),
        test2_tier_a_dir=str(test2_root.resolve()),
        preregistration=prereg,
        arms=arms,
        best_single_model=best_single,
        repair_model=repairer,
        exact_budget=exact_budget,
        per_arm_call_cap=per_arm,
        holdout="A",
        full_power_clusters=int(full_power) if full_power is not None else None,
    )
