from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _persist_value_checkpoint(
    root: str | Path,
    run_id: str,
    completed_seed_count: int,
    total_seed_count: int,
    summary: dict[str, Any],
) -> dict[str, str]:
    root = Path(root)
    percent = round(100.0 * completed_seed_count / total_seed_count, 1) if total_seed_count else 100.0
    by_arm = summary.get("by_arm", {})
    a = by_arm.get("A_DIRECT", {})
    d = by_arm.get("D_INVERTED", {})
    e = by_arm.get("E_RANDOM_AUDITOR", {})
    primary = summary.get("primary", {})

    d_rate = d.get("success_rate")
    e_rate = e.get("success_rate")
    catastrophic_delta = None
    if d.get("catastrophic_rate") is not None and a.get("catastrophic_rate") is not None:
        catastrophic_delta = float(d["catastrophic_rate"]) - float(a["catastrophic_rate"])

    metrics = {
        "d_minus_a": primary.get("d_minus_a"),
        "d_minus_b": primary.get("d_minus_b"),
        "d_minus_e": (float(d_rate) - float(e_rate)) if d_rate is not None and e_rate is not None else None,
        "equal_budget_diff": primary.get("equal_budget_diff"),
        "ci95": primary.get("ci95"),
        "independent_task_clusters": primary.get("independent_task_clusters"),
        "catastrophic_delta_d_minus_a": catastrophic_delta,
        "family_advantage": summary.get("family_advantage", {}),
        "model_advantage": summary.get("model_advantage", {}),
        "seed_advantage": summary.get("seed_advantage", {}),
        "complexity_advantage": summary.get("complexity_advantage", {}),
        "quality_crossover": summary.get("quality_crossover", {}),
    }
    payload = {
        "record_type": "value_checkpoint",
        "status": "EXPLORATORY_NON_DECISIVE",
        "warning": "NOT A SCIENTIFIC VERDICT",
        "run_id": run_id,
        "completed_seed_count": completed_seed_count,
        "total_seed_count": total_seed_count,
        "percent": percent,
        "n_trials": summary.get("n_trials", 0),
        "metrics": metrics,
        "by_arm": by_arm,
    }

    def pp(value: Any) -> str:
        return "N/A" if value is None else f"{float(value) * 100:+.2f}pp"

    ci = metrics.get("ci95") or {}
    text = "\n".join([
        f"VALUE CHECKPOINT {percent:.0f}% — EXPLORATORY / NON-DECISIVE",
        "NOT A SCIENTIFIC VERDICT",
        f"Run: {run_id}",
        f"Seeds: {completed_seed_count}/{total_seed_count}",
        f"Trials completed: {summary.get('n_trials', 0)}",
        f"D - A: {pp(metrics.get('d_minus_a'))}",
        f"95% bootstrap CI D - A: [{pp(ci.get('lower'))}, {pp(ci.get('upper'))}]",
        f"D - B: {pp(metrics.get('d_minus_b'))}",
        f"D - E random auditor: {pp(metrics.get('d_minus_e'))}",
        f"Equal-token D - A: {pp(metrics.get('equal_budget_diff'))}",
        f"Catastrophic delta D - A: {pp(metrics.get('catastrophic_delta_d_minus_a'))}",
        f"Family direction: {json.dumps(metrics.get('family_advantage'), sort_keys=True)}",
        f"Model direction: {json.dumps(metrics.get('model_advantage'), sort_keys=True)}",
        f"Complexity direction: {json.dumps(metrics.get('complexity_advantage'), sort_keys=True)}",
        f"Quality crossover: {json.dumps(metrics.get('quality_crossover'), sort_keys=True)}",
        "Use this snapshot only to decide whether additional runtime is worthwhile; 60%/80%/100% gates retain scientific authority.",
        "",
    ])

    tag = int(round(percent))
    json_path = root / f"{run_id}.value-checkpoint-{tag:03d}.json"
    text_path = root / f"{run_id}.value-checkpoint-{tag:03d}.txt"
    _atomic_write_text(json_path, json.dumps(payload, sort_keys=True, indent=2, default=str) + "\n")
    _atomic_write_text(text_path, text)
    return {"json": str(json_path), "text": str(text_path)}
