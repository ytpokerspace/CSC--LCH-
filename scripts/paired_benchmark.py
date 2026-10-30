#!/usr/bin/env python3
"""Paired offline CSC-LCH benchmark; standard library only, no API calls."""
import argparse, csv, json, math, statistics, sys
from pathlib import Path

BASE = ("baseline_prompt_tokens", "baseline_hydration_prompt_tokens", "baseline_retrieved_tokens", "baseline_output_tokens")
POLICY = ("active_prompt_tokens", "hydration_prompt_tokens", "retrieved_tokens", "output_tokens")
FACTS = ("baseline_material_facts_expected", "baseline_material_facts_recovered", "material_facts_expected", "material_facts_recovered")
REQUIRED = {"question_id", "policy", "baseline_latency_ms", "latency_ms", "baseline_quality_score", "quality_score", "baseline_reconstruction_ok", "reconstruction_ok", *BASE, *POLICY, *FACTS}

def load_rows(path):
    rows = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_no}: invalid JSON: {exc}") from exc
        missing = REQUIRED - r.keys()
        if missing:
            raise ValueError(f"line {line_no}: missing fields: {', '.join(sorted(missing))}")
        for key in ("question_id", "policy"):
            if not isinstance(r[key], str) or not r[key].strip():
                raise ValueError(f"line {line_no}: {key} must be a non-empty string")
        for key in (*BASE, *POLICY, *FACTS):
            if isinstance(r[key], bool) or not isinstance(r[key], int) or r[key] < 0:
                raise ValueError(f"line {line_no}: {key} must be a non-negative integer")
        for key in ("baseline_latency_ms", "latency_ms", "baseline_quality_score", "quality_score"):
            v = r[key]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                raise ValueError(f"line {line_no}: {key} must be finite and non-negative")
        for key in ("baseline_quality_score", "quality_score"):
            if r[key] > 1:
                raise ValueError(f"line {line_no}: {key} must be between 0 and 1")
        for key in ("baseline_reconstruction_ok", "reconstruction_ok"):
            if not isinstance(r[key], bool):
                raise ValueError(f"line {line_no}: {key} must be boolean")
        for expected, recovered in (("baseline_material_facts_expected", "baseline_material_facts_recovered"), ("material_facts_expected", "material_facts_recovered")):
            if r[recovered] > r[expected]:
                raise ValueError(f"line {line_no}: recovered facts cannot exceed expected")
        r["baseline_total_tokens"] = sum(r[k] for k in BASE)
        r["policy_total_tokens"] = sum(r[k] for k in POLICY)
        rows.append(r)
    if not rows:
        raise ValueError("input contains no observations")
    seen = set()
    for r in rows:
        key = (r["question_id"], r["policy"])
        if key in seen:
            raise ValueError(f"duplicate observation for question_id={key[0]!r}, policy={key[1]!r}")
        seen.add(key)
    return rows

def summarize(rows):
    if not rows:
        raise ValueError("input contains no observations")
    question_sets = {}
    for row in rows:
        question_sets.setdefault(row["policy"], set()).add(row["question_id"])
    if len(question_sets) > 1:
        reference_policy = sorted(question_sets)[0]
        reference_questions = question_sets[reference_policy]
        mismatches = {
            policy: sorted(reference_questions ^ question_ids)
            for policy, question_ids in sorted(question_sets.items())
            if question_ids != reference_questions
        }
        if mismatches:
            details = "; ".join(
                f"{policy}: differing question_ids={ids}"
                for policy, ids in mismatches.items()
            )
            raise ValueError(
                "paired benchmark requires identical question_id sets across "
                f"policies (reference={reference_policy}): {details}"
            )
    grouped = {}
    for r in rows:
        grouped.setdefault(r["policy"], []).append(r)
    result = {}
    for policy, items in sorted(grouped.items()):
        bt = sum(r["baseline_total_tokens"] for r in items)
        pt = sum(r["policy_total_tokens"] for r in items)
        be = sum(r["baseline_material_facts_expected"] for r in items)
        br = sum(r["baseline_material_facts_recovered"] for r in items)
        pe = sum(r["material_facts_expected"] for r in items)
        pr = sum(r["material_facts_recovered"] for r in items)
        result[policy] = {
            "observations": len(items), "baseline_total_tokens": bt, "policy_total_tokens": pt,
            "tokens_saved": bt - pt,
            "token_reduction_pct": round(100 * (bt - pt) / bt, 4) if bt else None,
            "baseline_mean_latency_ms": round(statistics.mean(r["baseline_latency_ms"] for r in items), 4),
            "policy_mean_latency_ms": round(statistics.mean(r["latency_ms"] for r in items), 4),
            "baseline_fact_recall": round(br / be, 6) if be else None,
            "policy_fact_recall": round(pr / pe, 6) if pe else None,
            "baseline_mean_quality": round(statistics.mean(r["baseline_quality_score"] for r in items), 6),
            "policy_mean_quality": round(statistics.mean(r["quality_score"] for r in items), 6),
            "baseline_reconstruction_failures": sum(not r["baseline_reconstruction_ok"] for r in items),
            "policy_reconstruction_failures": sum(not r["reconstruction_ok"] for r in items),
        }
    status = "synthetic_fixture" if all(r.get("data_status") == "synthetic_fixture" for r in rows) else "user_supplied_observations"
    return {"schema_version": 1, "data_status": status,
            "accounting_note": "Paired comparison. Both totals include prompt/input + hydration prompt + retrieved context + output. Categories must be mutually exclusive and use the same tokenizer and output requirements.",
            "policies": result}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path)
    p.add_argument("--json-out", type=Path, default=Path("artifacts/paired_summary.json"))
    p.add_argument("--csv-out", type=Path, default=Path("artifacts/paired_summary.csv"))
    a = p.parse_args()
    try:
        summary = summarize(load_rows(a.input))
        a.json_out.parent.mkdir(parents=True, exist_ok=True)
        a.csv_out.parent.mkdir(parents=True, exist_ok=True)
        a.json_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with a.csv_out.open("w", newline="", encoding="utf-8") as f:
            fields = ["policy", "observations", "baseline_total_tokens", "policy_total_tokens", "tokens_saved", "token_reduction_pct", "baseline_mean_latency_ms", "policy_mean_latency_ms", "baseline_fact_recall", "policy_fact_recall", "baseline_mean_quality", "policy_mean_quality", "baseline_reconstruction_failures", "policy_reconstruction_failures"]
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
            for name, values in summary["policies"].items(): w.writerow({"policy": name, **values})
        print(json.dumps(summary, indent=2))
        print(f"\nWrote {a.json_out} and {a.csv_out}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr); return 2

if __name__ == "__main__":
    raise SystemExit(main())
