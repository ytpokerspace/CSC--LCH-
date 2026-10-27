#!/usr/bin/env python3
"""Offline CSC LCH Milestone 6.1 benchmark aggregator (standard library only).

Input is JSON Lines: one observation per policy/question/run. See
benchmarks/milestone6_report.md for the schema and accounting caveats.
No network or paid API calls are made.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REQUIRED = {
    "policy", "question_id", "baseline_prompt_tokens", "active_prompt_tokens",
    "hydration_calls", "hydration_prompt_tokens", "retrieved_tokens",
    "output_tokens", "latency_ms", "quality_score",
    "material_facts_expected", "material_facts_recovered", "reconstruction_ok",
}
NONNEGATIVE_INT_FIELDS = {
    "baseline_prompt_tokens", "active_prompt_tokens", "hydration_calls",
    "hydration_prompt_tokens", "retrieved_tokens", "output_tokens",
    "material_facts_expected", "material_facts_recovered",
}


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        missing = REQUIRED - row.keys()
        if missing:
            raise ValueError(f"{path}:{line_no}: missing fields: {', '.join(sorted(missing))}")
        if not isinstance(row["policy"], str) or not row["policy"].strip():
            raise ValueError(f"{path}:{line_no}: policy must be a non-empty string")
        if not isinstance(row["question_id"], str) or not row["question_id"].strip():
            raise ValueError(f"{path}:{line_no}: question_id must be a non-empty string")
        for field in NONNEGATIVE_INT_FIELDS:
            value = row[field]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{path}:{line_no}: {field} must be a non-negative integer")
        for field in ("latency_ms", "quality_score"):
            value = row[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{path}:{line_no}: {field} must be a finite non-negative number")
        if row["quality_score"] > 1:
            raise ValueError(f"{path}:{line_no}: quality_score must be between 0 and 1")
        if not isinstance(row["reconstruction_ok"], bool):
            raise ValueError(f"{path}:{line_no}: reconstruction_ok must be boolean")
        if row["material_facts_recovered"] > row["material_facts_expected"]:
            raise ValueError(f"{path}:{line_no}: recovered facts cannot exceed expected facts")
        row["total_tokens"] = sum(row[k] for k in (
            "active_prompt_tokens", "hydration_prompt_tokens",
            "retrieved_tokens", "output_tokens",
        ))
        rows.append(row)
    if not rows:
        raise ValueError("input contains no observations")
    return rows


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile; returns None for an empty collection."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p * len(ordered)) - 1)]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["policy"]].append(row)
    policies: dict[str, Any] = {}
    for policy, items in sorted(grouped.items()):
        baseline_values = {r["baseline_prompt_tokens"] for r in items}
        if len(baseline_values) != 1:
            raise ValueError(f"{policy}: baseline_prompt_tokens differs across observations")
        baseline = next(iter(baseline_values))
        active = sum(r["active_prompt_tokens"] for r in items)
        # Compare aggregate active tokens with a per-question baseline.
        baseline_total = baseline * len(items)
        total = sum(r["total_tokens"] for r in items)
        latencies = [float(r["latency_ms"]) for r in items]
        expected = sum(r["material_facts_expected"] for r in items)
        recovered = sum(r["material_facts_recovered"] for r in items)
        policies[policy] = {
            "observations": len(items),
            "baseline_prompt_tokens_total": baseline_total,
            "active_prompt_tokens_total": active,
            "active_tokens_saved": baseline_total - active,
            "active_reduction_pct": round(100 * (baseline_total - active) / baseline_total, 4) if baseline_total else None,
            "active_compression_ratio": round(baseline_total / active, 6) if active else None,
            "hydration_calls_total": sum(r["hydration_calls"] for r in items),
            "hydration_prompt_tokens_total": sum(r["hydration_prompt_tokens"] for r in items),
            "retrieved_tokens_total": sum(r["retrieved_tokens"] for r in items),
            "output_tokens_total": sum(r["output_tokens"] for r in items),
            "total_tokens_including_recorded_retrieval_and_output": total,
            "total_tokens_saved_vs_baseline_prompt_only": baseline_total - total,
            "mean_quality_score": round(statistics.mean(r["quality_score"] for r in items), 6),
            "material_facts_expected": expected,
            "material_facts_recovered": recovered,
            "material_fact_recall": round(recovered / expected, 6) if expected else None,
            "reconstruction_failures": sum(not r["reconstruction_ok"] for r in items),
            "mean_latency_ms": round(statistics.mean(latencies), 4),
            "median_latency_ms": round(statistics.median(latencies), 4),
            "p95_latency_ms_nearest_rank": percentile(latencies, 0.95),
        }
    return {
        "schema_version": 1,
        "accounting_note": "total_tokens sums active prompt + hydration prompt + retrieved + output fields; ensure fields are mutually exclusive for your instrumentation.",
        "policies": policies,
    }


def write_outputs(summary: dict[str, Any], json_path: Path, csv_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fields = [
        "policy", "observations", "baseline_prompt_tokens_total", "active_prompt_tokens_total",
        "active_tokens_saved", "active_reduction_pct", "active_compression_ratio",
        "hydration_calls_total", "hydration_prompt_tokens_total", "retrieved_tokens_total",
        "output_tokens_total", "total_tokens_including_recorded_retrieval_and_output",
        "total_tokens_saved_vs_baseline_prompt_only", "mean_quality_score",
        "material_facts_expected", "material_facts_recovered", "material_fact_recall",
        "reconstruction_failures", "mean_latency_ms", "median_latency_ms", "p95_latency_ms_nearest_rank",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for policy, values in summary["policies"].items():
            writer.writerow({"policy": policy, **values})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSONL observations file")
    parser.add_argument("--json-out", type=Path, default=Path("artifacts/m6_summary.json"))
    parser.add_argument("--csv-out", type=Path, default=Path("artifacts/m6_summary.csv"))
    args = parser.parse_args(argv)
    try:
        rows = load_rows(args.input)
        summary = summarize(rows)
        write_outputs(summary, args.json_out, args.csv_out)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {args.json_out} and {args.csv_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
