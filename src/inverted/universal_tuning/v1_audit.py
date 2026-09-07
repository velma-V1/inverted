from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any

from inverted.qwen_thinking_tuning import canonical_tuning_cases

from .core import AtomicTask
from .scoring import score_atomic_task


_V1_CODE_SPECS = {
    "budget": [
        {"behavior": "v1_sorted_unique_items"},
        {"behavior": "v1_sum_squares"},
        {"behavior": "v1_dict_exclude_none"},
    ],
    "temperature": [
        {"behavior": "v1_first_positive"},
        {"behavior": "v1_even_values"},
        {"behavior": "v1_square_map"},
    ],
    "validation": [
        {"behavior": "max_default", "default": 0},
        {"behavior": "all_gt", "threshold": 0},
        {"behavior": "reverse_items"},
    ],
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _adapt_case(case: Any) -> AtomicTask:
    if case.scorer == "exact_json":
        expected = case.expected["answer"] if isinstance(case.expected, dict) and "answer" in case.expected else case.expected
        scorer = "exact_value"
    elif case.scorer == "contains_all_batch":
        expected = [list(group) for group in case.expected]
        scorer = "contains_all_batch"
    elif case.scorer == "python_expr_batch":
        expected = _V1_CODE_SPECS[case.phase]
        scorer = "python_expr_batch"
    else:
        raise ValueError(f"unsupported V1 scorer: {case.scorer}")
    return AtomicTask(
        task_id=case.case_id, family=case.family, difficulty=0,
        prompt=case.prompt, expected=expected, scorer=scorer,
        contract="answer_object",
    )


def _evaluator_hash() -> str:
    here = Path(__file__)
    scoring = here.with_name("scoring.py")
    return _sha256(here.read_bytes() + b"\0" + scoring.read_bytes())


def audit_v1_run(run_root: str | Path, *, output_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(run_root)
    source = root / "observations.jsonl"
    source_bytes = source.read_bytes()
    source_hash = _sha256(source_bytes)
    cases = {case.case_id: _adapt_case(case) for case in canonical_tuning_cases()}
    derived_rows: list[dict[str, Any]] = []

    for raw_line in source_bytes.decode("utf-8").splitlines():
        if not raw_line.strip():
            continue
        raw = json.loads(raw_line)
        case_id = raw["case_id"]
        if case_id not in cases:
            raise ValueError(f"unknown V1 case_id: {case_id}")
        score = score_atomic_task(cases[case_id], raw.get("response_text", ""))
        derived_rows.append({
            "trial_id": raw.get("trial_id"),
            "family": raw.get("family"),
            "case_id": case_id,
            "stage": raw.get("stage"),
            "profile": raw.get("profile"),
            "completed": score.completed,
            "semantic_pass": score.semantic_pass,
            "semantic_quality": score.semantic_quality,
            "contract_pass": score.contract_pass,
            "contract_quality": score.contract_quality,
            "failure_classes": [item.value for item in score.failure_classes],
            "source_row_sha256": _sha256(raw_line.encode("utf-8")),
        })

    destination = Path(output_root) if output_root is not None else root
    destination.mkdir(parents=True, exist_ok=True)
    audit_path = destination / "v1-derived-audit.jsonl"
    audit_path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in derived_rows),
        encoding="utf-8",
    )

    semantic_passes = sum(row["semantic_pass"] for row in derived_rows)
    contract_passes = sum(row["contract_pass"] for row in derived_rows)
    contract_only = sum(row["semantic_pass"] and not row["contract_pass"] for row in derived_rows)
    evaluator_hash = _evaluator_hash()
    summary = {
        "protocol": "V1_DERIVED_AUDIT",
        "source": str(source),
        "source_sha256": source_hash,
        "evaluator_sha256": evaluator_hash,
        "observation_count": len(derived_rows),
        "semantic_passes": semantic_passes,
        "contract_passes": contract_passes,
        "semantic_pass_contract_fail": contract_only,
        "mean_semantic_quality": (
            sum(row["semantic_quality"] for row in derived_rows) / len(derived_rows)
            if derived_rows else 0.0
        ),
    }
    (destination / "v1-derived-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if source.read_bytes() != source_bytes:
        raise RuntimeError("V1 source evidence changed during derived audit")
    return summary
