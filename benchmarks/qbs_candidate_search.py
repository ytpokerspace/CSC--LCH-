#!/usr/bin/env python3
"""Rank measured retrieval candidates and propose bounded QBS-style coordinate neighbors."""
import argparse
import json
import math
import sys
from pathlib import Path

CONTROLS = (
    "compression", "retrieval_relevance", "hydration_priority",
    "evidence_confidence", "exploration", "validation_strictness",
)
METRICS = ("answer_accuracy", "evidence_recall", "factual_precision", "efficiency")
WEIGHTS = {
    "answer_accuracy": 0.50,
    "evidence_recall": 0.20,
    "factual_precision": 0.15,
    "efficiency": 0.15,
}

def bounded_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be a finite number between 0 and 1")
    return float(value)

def load_candidates(path):
    candidates, seen = [], set()
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {line_no}: candidate must be a JSON object")
        cid = row.get("candidate_id")
        if not isinstance(cid, str) or not cid.strip() or cid in seen:
            raise ValueError(f"line {line_no}: candidate_id must be unique and non-empty")
        seen.add(cid)
        controls = row.get("controls")
        if not isinstance(controls, dict) or set(controls) != set(CONTROLS):
            raise ValueError(f"line {line_no}: controls must contain exactly {', '.join(CONTROLS)}")
        clean_controls = {key: bounded_number(controls[key], f"controls.{key}") for key in CONTROLS}
        clean = {"candidate_id": cid, "controls": clean_controls}
        for key in METRICS:
            clean[key] = bounded_number(row.get(key), key)
        if not isinstance(row.get("critical_facts_pass"), bool):
            raise ValueError(f"line {line_no}: critical_facts_pass must be boolean")
        clean["critical_facts_pass"] = row["critical_facts_pass"]
        candidates.append(clean)
    if not candidates:
        raise ValueError("input contains no candidates")
    return candidates

def score_candidate(candidate):
    return sum(WEIGHTS[key] * candidate[key] for key in METRICS)

def rank_and_propose(candidates, step=0.1, min_accuracy=0.0):
    step = bounded_number(step, "step")
    if step == 0:
        raise ValueError("step must be greater than zero")
    min_accuracy = bounded_number(min_accuracy, "min_accuracy")
    eligible = [
        {**item, "utility_score": round(score_candidate(item), 6)}
        for item in candidates
        if item["critical_facts_pass"] and item["answer_accuracy"] >= min_accuracy
    ]
    eligible.sort(key=lambda x: (
        -x["utility_score"], -x["answer_accuracy"], -x["evidence_recall"],
        -x["factual_precision"], -x["efficiency"], x["candidate_id"],
    ))
    if not eligible:
        return {
            "schema_version": 1,
            "status": "no_feasible_candidate",
            "weights": WEIGHTS,
            "hard_gate": "critical_facts_pass must be true and answer_accuracy must meet min_accuracy",
            "winner": None,
            "next_candidates": [],
        }
    winner = eligible[0]
    eligible_ids = {item["candidate_id"] for item in eligible}
    known = {tuple(round(item["controls"][key], 6) for key in CONTROLS) for item in candidates}
    proposals = []
    for key in CONTROLS:
        current = winner["controls"][key]
        for direction in (-1, 1):
            value = round(min(1.0, max(0.0, current + direction * step)), 6)
            if value == current:
                continue
            controls = dict(winner["controls"])
            controls[key] = value
            signature = tuple(controls[name] for name in CONTROLS)
            if signature in known:
                continue
            known.add(signature)
            proposals.append({
                "candidate_id": f"next_{key}_{'minus' if direction < 0 else 'plus'}",
                "parent_candidate_id": winner["candidate_id"],
                "changed_control": key,
                "direction": "minus" if direction < 0 else "plus",
                "controls": controls,
                "status": "proposal_not_yet_evaluated",
            })
    return {
        "schema_version": 1,
        "status": "winner_selected",
        "weights": WEIGHTS,
        "hard_gate": "critical_facts_pass must be true and answer_accuracy must meet min_accuracy",
        "min_accuracy": min_accuracy,
        "step": step,
        "winner": winner,
        "eligible_candidates": eligible,
        "rejected_candidates": [
            {"candidate_id": item["candidate_id"], "critical_facts_pass": item["critical_facts_pass"],
             "answer_accuracy": item["answer_accuracy"]}
            for item in candidates if item["candidate_id"] not in eligible_ids
        ],
        "next_candidates": proposals,
        "method_note": "Classical bounded coordinate search over measured candidates. Proposals require a real retrieval run and independent answer scoring before they can be ranked. No quantum computation or model/API calls are performed.",
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSONL of measured candidate configurations")
    parser.add_argument("--out", type=Path, default=Path("artifacts/qbs_candidate_search.json"))
    parser.add_argument("--step", type=float, default=0.1)
    parser.add_argument("--min-accuracy", type=float, default=0.0)
    args = parser.parse_args()
    try:
        result = rank_and_propose(load_candidates(args.input), args.step, args.min_accuracy)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        print(f"\nWrote {args.out}")
        return 0 if result["status"] == "winner_selected" else 2
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
