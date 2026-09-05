from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import json
import random
from typing import Any, Mapping

from .d3_assistance import evaluate_assistance
from .hd_next1_cases import generate_hd_next1_cases
from .types import stable_hash


_SYSTEM = (
    "INVERTED HD-NEXT-1 controlled measurement. Use only the supplied model-visible context. "
    "Return exactly one JSON object containing key answer. Do not invent a system disposition."
)


def _factor_levels() -> dict[str, tuple[str, ...]]:
    factors: dict[str, tuple[str, ...]] = {f"I{i}": ("OFF", "ON") for i in range(1, 11)}
    factors.update(
        {
            "representation": (
                "RAW_PROSE", "TYPED_FIELDS", "STRICT_JSON", "DECISION_TABLE", "PRIORITY_BLOCK",
                "EXPLICIT_ALTERNATIVES", "DECOMPOSITION", "MINIMAL_LEDGER", "COMPRESSED_SUMMARY",
                "ADMISSIBLE_ACTION_MATRIX",
            ),
            "ordering": ("DEFAULT", "TASK_OBJECTIVE_FIRST", "STATE_FIRST", "EVIDENCE_FIRST", "SAFETY_STATE_EVIDENCE_FIRST", "SHUFFLED_CONTROL"),
            "amount": ("MINIMUM", "COMPRESSED", "MODERATE", "FULL", "OVERLOADED"),
            "timing": ("UPFRONT", "PRE_DECISION", "JUST_IN_TIME"),
            "placement": ("TASK_CONTEXT", "SYSTEM_CONTEXT", "MIXED_CONTEXT"),
        }
    )
    for i in range(1, 5):
        factors[f"A{i}"] = ("OFF", "TARGET")
    return factors


def _pair_obligations(factors: Mapping[str, tuple[str, ...]]) -> set[tuple[str, str, str, str]]:
    rows: set[tuple[str, str, str, str]] = set()
    names = tuple(factors)
    for left, right in combinations(names, 2):
        for left_level in factors[left]:
            for right_level in factors[right]:
                rows.add((left, left_level, right, right_level))
    return rows


def _covered_pairs(row: Mapping[str, str], names: tuple[str, ...]) -> set[tuple[str, str, str, str]]:
    return {(left, row[left], right, row[right]) for left, right in combinations(names, 2)}


def _generate_pairwise(factors: Mapping[str, tuple[str, ...]], seed: int) -> tuple[dict[str, str], ...]:
    names = tuple(factors)
    index = {name: i for i, name in enumerate(names)}
    rng = random.Random(int(seed))
    tie = {(name, level): rng.random() for name in names for level in factors[name]}
    uncovered = _pair_obligations(factors)
    result: list[dict[str, str]] = []
    guard = 0
    while uncovered:
        guard += 1
        if guard > 10000:
            raise RuntimeError("HD-NEXT-1 covering design failed to converge")
        left, left_level, right, right_level = min(uncovered)
        partial = {left: left_level, right: right_level}
        for name in names:
            if name in partial:
                continue
            scored: list[tuple[int, float, str]] = []
            for level in factors[name]:
                gain = 0
                for other, other_level in partial.items():
                    pair = (other, other_level, name, level) if index[other] < index[name] else (name, level, other, other_level)
                    if pair in uncovered:
                        gain += 1
                scored.append((gain, -tie[(name, level)], level))
            scored.sort(reverse=True)
            partial[name] = scored[0][2]
        row = {name: partial[name] for name in names}
        if not any(row[f"I{i}"] == "ON" for i in range(1, 11)):
            anchor_factors = {left, right}
            repair = next(f"I{i}" for i in range(1, 11) if f"I{i}" not in anchor_factors)
            row[repair] = "ON"
        covered = _covered_pairs(row, names) & uncovered
        if not covered:
            raise RuntimeError("covering row made no progress")
        result.append(row)
        uncovered -= covered
    return tuple(result)


_HIGH_RISK_THREE_WAY = (
    (("I4", "ON"), ("A3", "TARGET"), ("representation", "TYPED_FIELDS")),
    (("I7", "ON"), ("A2", "TARGET"), ("representation", "ADMISSIBLE_ACTION_MATRIX")),
    (("I2", "ON"), ("A1", "TARGET"), ("ordering", "STATE_FIRST")),
    (("I3", "ON"), ("ordering", "SAFETY_STATE_EVIDENCE_FIRST"), ("placement", "SYSTEM_CONTEXT")),
    (("I1", "ON"), ("amount", "OVERLOADED"), ("timing", "JUST_IN_TIME")),
    (("I8", "ON"), ("A4", "TARGET"), ("ordering", "TASK_OBJECTIVE_FIRST")),
)


def _with_required_rows(rows: tuple[dict[str, str], ...], factors: Mapping[str, tuple[str, ...]]) -> tuple[dict[str, str], ...]:
    output = [dict(row) for row in rows]
    for requirement in _HIGH_RISK_THREE_WAY:
        if any(all(row[name] == level for name, level in requirement) for row in output):
            continue
        row = {name: levels[0] for name, levels in factors.items()}
        for name, level in requirement:
            row[name] = level
        if not any(row[f"I{i}"] == "ON" for i in range(1, 11)):
            row["I1"] = "ON"
        output.append(row)
    unique: list[dict[str, str]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for row in output:
        key = tuple((name, row[name]) for name in factors)
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return tuple(unique)


def _ordered(field_ids: list[str], ordering: str, seed_text: str) -> list[str]:
    priority = {
        "TASK_OBJECTIVE_FIRST": [f"I{i}" for i in range(1, 11)],
        "STATE_FIRST": ["I2", "I1", "I3", "I4", "I5", "I6", "I7", "I8", "I9", "I10"],
        "EVIDENCE_FIRST": ["I4", "I1", "I2", "I3", "I5", "I6", "I7", "I8", "I9", "I10"],
        "SAFETY_STATE_EVIDENCE_FIRST": ["I6", "I2", "I4", "I3", "I5", "I7", "I8", "I9", "I10", "I1"],
    }
    if ordering == "SHUFFLED_CONTROL":
        result = list(field_ids)
        random.Random(int(stable_hash(seed_text)[:16], 16)).shuffle(result)
        return result
    if ordering == "DEFAULT":
        return list(field_ids)
    rank = {name: i for i, name in enumerate(priority[ordering])}
    return sorted(field_ids, key=lambda name: rank.get(name, 99))


def _render_fields(order: list[str], info: Mapping[str, Any], representation: str) -> str:
    payload = {field_id: info[field_id] for field_id in order}
    if representation == "STRICT_JSON":
        return json.dumps(payload, sort_keys=False, separators=(",", ":"), ensure_ascii=False)
    if representation == "RAW_PROSE":
        return "\n".join(f"{key}: {payload[key]}" for key in order)
    if representation == "DECISION_TABLE":
        return "field | value\n" + "\n".join(f"{key} | {json.dumps(payload[key], sort_keys=True)}" for key in order)
    if representation == "PRIORITY_BLOCK":
        return "PRIORITY INFORMATION\n" + "\n".join(f"[{key}] {json.dumps(payload[key], sort_keys=True)}" for key in order)
    if representation == "EXPLICIT_ALTERNATIVES":
        return "ALTERNATIVES / CONSTRAINTS\n" + "\n".join(f"{key}={json.dumps(payload[key], sort_keys=True)}" for key in order)
    if representation == "DECOMPOSITION":
        return "DECOMPOSED STATE\n" + "\n".join(f"step-context {key}: {json.dumps(payload[key], sort_keys=True)}" for key in order)
    if representation == "MINIMAL_LEDGER":
        return "\n".join(f"{key}:{json.dumps(payload[key], sort_keys=True, separators=(',', ':'))}" for key in order)
    if representation == "COMPRESSED_SUMMARY":
        return ";".join(f"{key}={json.dumps(payload[key], sort_keys=True, separators=(',', ':'))}" for key in order)
    if representation == "ADMISSIBLE_ACTION_MATRIX":
        return "ADMISSIBILITY CONTEXT\n" + "\n".join(f"{key} -> {json.dumps(payload[key], sort_keys=True)}" for key in order)
    return "\n".join(f"{key}: {json.dumps(payload[key], sort_keys=True)}" for key in order)


def _apply_amount(text: str, amount: str) -> str:
    if amount == "MINIMUM":
        return " ".join(part.strip() for part in text.splitlines() if part.strip())
    if amount == "COMPRESSED":
        return " ".join(text.split())
    if amount == "MODERATE":
        return text
    if amount == "FULL":
        return f"FULL CANONICAL CONTEXT\n{text}\nEND FULL CANONICAL CONTEXT"
    neutral = " NON_AUTHORITATIVE_NEUTRAL_BURDEN"
    return f"FULL CANONICAL CONTEXT\n{text}\nEND FULL CANONICAL CONTEXT\nCONTROL_BURDEN:" + neutral * max(16, len(text) // max(1, len(neutral)))


def _case_context(case: Any) -> dict[str, Any]:
    info = dict((case.metadata or {}).get("d3_information", {}))
    return {
        "canonical_state": dict(info.get("I2", {})),
        "candidate_actions": list(dict(info.get("I7", {})).get("admissible_actions", [])),
        "admissible_actions": list(dict(info.get("I7", {})).get("admissible_actions", [])),
        "required_evidence": list(dict(info.get("I4", {})).get("required", [])),
        "available_evidence": list(dict(info.get("I4", {})).get("available", [])),
        "missing_evidence": list(dict(info.get("I4", {})).get("missing", [])),
        "dependencies": dict(info.get("I8", {})),
    }


def render_treatment_messages(case: Any, factor_vector: Mapping[str, str]) -> tuple[str, str, dict[str, object]]:
    info = dict((case.metadata or {}).get("d3_information", {}))
    fields = [f"I{i}" for i in range(1, 11) if factor_vector[f"I{i}"] == "ON" and f"I{i}" in info]
    if not fields:
        raise ValueError("treatment must expose at least one information field")
    order = _ordered(fields, factor_vector["ordering"], case.case_id + json.dumps(dict(factor_vector), sort_keys=True))
    rendered = _apply_amount(_render_fields(order, info, factor_vector["representation"]), factor_vector["amount"])
    base_context = _case_context(case)
    assistance: dict[str, Any] = {}
    for i in range(1, 5):
        mechanism = f"A{i}"
        if factor_vector[mechanism] == "TARGET":
            evaluated = evaluate_assistance(mechanism, "TARGET", base_context).output
            assistance[mechanism] = {key: value for key, value in evaluated.items() if base_context.get(key) != value}
    assist_block = ""
    if assistance:
        assist_block = "\n<PREDECISION_ASSISTANCE>\n" + json.dumps(assistance, sort_keys=True) + "\n</PREDECISION_ASSISTANCE>"
    task = str(case.prompt).replace(
        "Return one JSON object with exactly keys disposition and answer.",
        "Return one JSON object with exactly key answer. Do not return a system disposition.",
    )
    context = f"<HD_NEXT1_CONTEXT>\n{rendered}\n</HD_NEXT1_CONTEXT>"
    placement = factor_vector["placement"]
    timing = factor_vector["timing"]
    system, user = _SYSTEM, task
    if placement == "SYSTEM_CONTEXT":
        system += "\n" + context
    elif placement == "TASK_CONTEXT":
        if timing == "UPFRONT":
            user = context + "\n" + task
        elif timing == "PRE_DECISION":
            user = task + "\n" + context + "\nUse this context immediately before deciding."
        else:
            user = task + "\n<JIT_INFORMATION>\n" + rendered + "\n</JIT_INFORMATION>"
    else:
        midpoint = max(1, len(order) // 2)
        left = _apply_amount(_render_fields(order[:midpoint], info, factor_vector["representation"]), factor_vector["amount"])
        right_order = order[midpoint:]
        right = _apply_amount(_render_fields(right_order, info, factor_vector["representation"]), factor_vector["amount"]) if right_order else ""
        system += "\n<HD_NEXT1_CONTEXT>\n" + left + "\n</HD_NEXT1_CONTEXT>"
        if right:
            user = ("<HD_NEXT1_CONTEXT>\n" + right + "\n</HD_NEXT1_CONTEXT>\n" + task) if timing == "UPFRONT" else (task + "\n<HD_NEXT1_CONTEXT>\n" + right + "\n</HD_NEXT1_CONTEXT>")
    user += assist_block
    metadata = {
        "field_ids": fields,
        "field_order": order,
        "system_message_hash": stable_hash(system),
        "user_message_hash": stable_hash(user),
        "semantic_field_hash": stable_hash({key: info[key] for key in sorted(fields)}),
        "approx_token_count": max(1, (len((system + "\n" + user).encode("utf-8")) + 3) // 4),
    }
    return system, user, metadata


@dataclass(frozen=True)
class HDNext1ZeroCallDesign:
    factor_levels: dict[str, tuple[str, ...]]
    treatments: tuple[dict[str, Any], ...]
    pruning_ledger: tuple[dict[str, Any], ...]
    pairwise_coverage_ratio: float
    required_three_way_coverage_ratio: float
    required_three_way: tuple[dict[str, Any], ...]
    uncovered_regions: tuple[dict[str, Any], ...]
    physical_model_calls: int = 0


def build_zero_call_design(config: Mapping[str, Any]) -> HDNext1ZeroCallDesign:
    factors = _factor_levels()
    rows = _with_required_rows(_generate_pairwise(factors, int(config["randomization_seed"])), factors)
    expected = _pair_obligations(factors)
    observed: set[tuple[str, str, str, str]] = set()
    for row in rows:
        observed |= _covered_pairs(row, tuple(factors))
    pair_ratio = len(expected & observed) / len(expected) if expected else 1.0
    required_rows = tuple(
        {
            "factors": [name for name, _ in requirement],
            "levels": [level for _, level in requirement],
            "covered": any(all(row[name] == level for name, level in requirement) for row in rows),
        }
        for requirement in _HIGH_RISK_THREE_WAY
    )
    required_ratio = sum(bool(row["covered"]) for row in required_rows) / len(required_rows)
    cases = generate_hd_next1_cases("hd-next1-development", seed=int(config["seeds"]["development"]), per_family=4)
    treatments: list[dict[str, Any]] = []
    pruning: list[dict[str, Any]] = [
        {"candidate_scope": "timing=PROGRESSIVE", "reason_code": "REQUIRES_REAL_MULTI_STEP_DELIVERY", "action": "EXPLICITLY_UNCOVERED"}
    ]
    seen_equivalence: dict[str, str] = {}
    for index, row in enumerate(rows):
        case = cases[index % len(cases)]
        system, user, metadata = render_treatment_messages(case, row)
        equivalence_id = stable_hash({"system": metadata["system_message_hash"], "user": metadata["user_message_hash"]})
        if equivalence_id in seen_equivalence:
            pruning.append({"candidate_scope": stable_hash(row), "reason_code": "ACTUAL_MODEL_VISIBLE_EQUIVALENCE", "action": "COLLAPSE", "kept_treatment_id": seen_equivalence[equivalence_id]})
            continue
        treatment_id = stable_hash({"equivalence_id": equivalence_id, "case_id": case.case_id})
        seen_equivalence[equivalence_id] = treatment_id
        treatments.append(
            {
                "treatment_id": treatment_id,
                "case_id": case.case_id,
                "family": case.family,
                "factor_vector": dict(row),
                "system_message_hash": metadata["system_message_hash"],
                "user_message_hash": metadata["user_message_hash"],
                "semantic_field_hash": metadata["semantic_field_hash"],
                "approx_token_count": metadata["approx_token_count"],
                "equivalence_class_id": equivalence_id,
            }
        )
    if not treatments:
        raise ValueError("HD-NEXT-1 zero-call treatment catalog is empty")
    return HDNext1ZeroCallDesign(
        factor_levels=factors,
        treatments=tuple(treatments),
        pruning_ledger=tuple(pruning),
        pairwise_coverage_ratio=pair_ratio,
        required_three_way_coverage_ratio=required_ratio,
        required_three_way=required_rows,
        uncovered_regions=(
            {"region": "PROGRESSIVE_REAL_MULTI_STEP_DELIVERY", "reason": "not representable as one-call cosmetic timing"},
            {"region": "POST_DEVELOPMENT_DECISION_CELL_DEPTH", "reason": "resolved only after the frozen development selector runs"},
        ),
        physical_model_calls=0,
    )
