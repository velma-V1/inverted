from __future__ import annotations

import json
from typing import Any


def _fmt(v: Any, digits: int = 4) -> str:
    if v is None:
        return "N/A"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def _pct(v: Any) -> str:
    return "N/A" if v is None else f"{float(v)*100:.2f}%"


def render_report(summary: dict[str, Any], verdict: dict[str, Any], result: Any, provenance: dict[str, Any], artifact_paths: dict[str, str], include_raw_rows: bool = True) -> str:
    lines: list[str] = []
    add = lines.append
    add("=" * 92)
    add("INVERTED ARCHITECTURE BENCHMARK REPORT")
    add("=" * 92)
    evidence_scope = getattr(getattr(result, "config", None), "metadata", {}).get("evidence_scope")
    if evidence_scope:
        add(f"EVIDENCE SCOPE: {evidence_scope}")
    add(f"VERDICT: {verdict.get('verdict')}")
    add(f"REASON: {verdict.get('reason')}")
    add(f"RUN ID: {result.run_id}")
    add(f"TRIALS: {summary.get('n_trials', 0)}")
    add("")

    add("PRIMARY COMPARISON")
    add("-" * 92)
    p = summary.get("primary", {})
    ci = p.get("ci95", {}) or {}
    add(f"D - A success-rate difference: {_pct(p.get('d_minus_a'))}")
    add(f"95% bootstrap CI: [{_pct(ci.get('lower'))}, {_pct(ci.get('upper'))}]  paired N={ci.get('n_pairs')} samples={ci.get('samples')}")
    add(f"Equal-token-budget D - A: {_pct(p.get('equal_budget_diff'))}")
    add(f"D - B checked-baseline difference: {_pct(p.get('d_minus_b'))}")
    add("")

    add("PREREGISTERED VERDICT GATES")
    add("-" * 92)
    if verdict.get("gates"):
        for gate in verdict["gates"]:
            add(f"{'PASS' if gate.get('passed') else 'FAIL'}  {gate.get('name')}  value={gate.get('value')} threshold={gate.get('threshold','')}")
    else:
        add("No scientific gates evaluated for this NON-DECISIVE run.")
    add("")

    add("CROSSOVER / SYSTEM QUALITY")
    add("-" * 92)
    cross = summary.get("quality_crossover", {})
    add(f"CROSSOVER quality where D first exceeds A: {_fmt(cross.get('crossover_quality'))}")
    for point in cross.get("points", []):
        add(f"quality={point['quality']:.2f} A={_pct(point.get('a_success'))} B={_pct(point.get('b_success'))} D={_pct(point.get('d_success'))} D-A={_pct(point.get('d_minus_a'))} D-B={_pct(point.get('d_minus_b'))}")
    add("")

    add("ARM METRICS")
    add("-" * 92)
    for arm, m in summary.get("by_arm", {}).items():
        add(f"[{arm}] N={m.get('n')} success={_pct(m.get('success_rate'))} requirement_accuracy={_pct(m.get('mean_requirement_accuracy'))} catastrophic={_pct(m.get('catastrophic_rate'))}")
        add(f"  MODEL CALLS={m.get('model_call_count')} RETRIES={m.get('retry_call_count')} TIMEOUTS={m.get('timeout_count')} PARSER failures={m.get('parser_failure_count')} model errors={m.get('model_error_count')}")
        add(f"  TOKENS input={m.get('input_tokens')} output={m.get('output_tokens')} reasoning={m.get('reasoning_tokens')} cached={m.get('cached_tokens')} cache_write={m.get('cache_write_tokens')} total={m.get('total_tokens')} TOKENS/success={_fmt(m.get('tokens_per_success'))}")
        add(f"  COST known_usd={_fmt(m.get('known_cost_usd'), 6)} cost/success={_fmt(m.get('known_cost_per_success_usd'), 6)}")
        lat = m.get("model_call_latency_s", {})
        add(f"  LATENCY model-call seconds P50={_fmt(lat.get('p50'))} P90={_fmt(lat.get('p90'))} P95={_fmt(lat.get('p95'))} P99={_fmt(lat.get('p99'))} mean={_fmt(lat.get('mean'))}")
        tlat = m.get("latency_s", {})
        add(f"  LATENCY trial seconds P50={_fmt(tlat.get('p50'))} P90={_fmt(tlat.get('p90'))} P95={_fmt(tlat.get('p95'))} P99={_fmt(tlat.get('p99'))}")
        ttft = m.get("ttft_s", {})
        add(f"  TTFT seconds N={ttft.get('n')} P50={_fmt(ttft.get('p50'))} P90={_fmt(ttft.get('p90'))} P95={_fmt(ttft.get('p95'))} P99={_fmt(ttft.get('p99'))}")
        gt = m.get("generated_tokens_per_s", {})
        et = m.get("end_to_end_tokens_per_s", {})
        add(f"  TOKENS/SEC generation P50={_fmt(gt.get('p50'))} P90={_fmt(gt.get('p90'))} P95={_fmt(gt.get('p95'))} P99={_fmt(gt.get('p99'))}; end-to-end P50={_fmt(et.get('p50'))} P95={_fmt(et.get('p95'))}")
        aud = m.get("auditor", {})
        add(f"  AUDITOR TP={aud.get('tp')} TN={aud.get('tn')} FP={aud.get('fp')} FN={aud.get('fn')} precision={_pct(aud.get('precision'))} recall={_pct(aud.get('recall'))} specificity={_pct(aud.get('specificity'))} F1={_fmt(aud.get('f1'))} FPR={_pct(aud.get('false_positive_rate'))} FNR={_pct(aud.get('false_negative_rate'))}")
        add(f"  candidates={m.get('candidate_attempts')} rejections={m.get('rejections')} rejection_rate={_pct(m.get('rejection_rate'))} budget_exhausted={m.get('budget_exhausted')}")
    add("")

    add("FAILURE TAXONOMY")
    add("-" * 92)
    failures = summary.get("failure_taxonomy", {})
    if failures:
        for name, count in sorted(failures.items(), key=lambda item: (-item[1], item[0])):
            add(f"{name}: {count}")
    else:
        add("None")
    add("")

    for title, key in [
        ("MODEL SLICES", "model"),
        ("FAMILY SLICES", "family"),
        ("COMPLEXITY SLICES", "complexity"),
        ("QUALITY SLICES", "quality"),
        ("SEED SLICES", "seed"),
        ("EPOCH SLICES", "epoch"),
    ]:
        add(title)
        add("-" * 92)
        for name, metrics in summary.get("slices", {}).get(key, {}).items():
            add(f"{name}: N={metrics.get('n')} success={_pct(metrics.get('success_rate'))} requirement_accuracy={_pct(metrics.get('mean_requirement_accuracy'))} catastrophic={_pct(metrics.get('catastrophic_rate'))} tokens={metrics.get('total_tokens')} calls={metrics.get('model_call_count')}")
        add("")

    add("PROVENANCE")
    add("-" * 92)
    add(json.dumps(provenance, sort_keys=True, indent=2, default=str))
    add("")

    add("RAW ARTIFACTS")
    add("-" * 92)
    for key, path in artifact_paths.items():
        add(f"{key}: {path}")
    add("")

    if include_raw_rows:
        add("FULL TRIAL LEDGER")
        add("-" * 92)
        for trial in result.trials:
            add(json.dumps(trial.to_dict(include_calls=False), sort_keys=True, default=str))
        add("")
        add("FULL MODEL CALL LEDGER")
        add("-" * 92)
        for call in result.model_calls:
            add(json.dumps(call.to_dict(), sort_keys=True, default=str))
        add("")

    return "\n".join(lines) + "\n"
