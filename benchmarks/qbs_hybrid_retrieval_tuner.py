#!/usr/bin/env python3
"""Offline QBS-style coordinate/grid tuning for hybrid retrieval.

Input JSONL rows require: id, question, context, gold_evidence (non-empty list
of exact evidence strings). No model inference, network calls, or paid APIs.
The held-out split is evaluated only after selecting a configuration on dev.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import statistics
import sys
from pathlib import Path

try:
    from benchmarks.hybrid_retrieval import RetrievalConfig, retrieve
except ImportError:  # direct script execution
    from hybrid_retrieval import RetrievalConfig, retrieve

WEIGHTS = {"evidence_recall": 0.55, "evidence_precision": 0.25, "char_reduction": 0.20}


def load_rows(path: Path) -> list[dict]:
    rows, seen = [], set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {line_no}: expected an object")
        rid = row.get("id")
        if not isinstance(rid, str) or not rid.strip() or rid in seen:
            raise ValueError(f"line {line_no}: id must be unique and non-empty")
        seen.add(rid)
        if not isinstance(row.get("question"), str) or not row["question"].strip():
            raise ValueError(f"line {line_no}: question must be non-empty text")
        if not isinstance(row.get("context"), str) or not row["context"]:
            raise ValueError(f"line {line_no}: context must be non-empty text")
        evidence = row.get("gold_evidence")
        if not isinstance(evidence, list) or not evidence or any(
            not isinstance(x, str) or not x.strip() for x in evidence
        ):
            raise ValueError(f"line {line_no}: gold_evidence must be a non-empty list of strings")
        if any(item not in row["context"] for item in evidence):
            raise ValueError(f"line {line_no}: every gold_evidence string must occur in context")
        rows.append(row)
    if len(rows) < 2:
        raise ValueError("at least two rows are required for dev/held-out evaluation")
    return rows


def split_rows(rows: list[dict], seed: int) -> tuple[list[dict], list[dict]]:
    salt = str(seed).encode("utf-8")
    ordered = sorted(rows, key=lambda r: hashlib.sha256(salt + r["id"].encode("utf-8")).hexdigest())
    cut = max(1, min(len(rows) - 1, round(len(rows) * 0.7)))
    return ordered[:cut], ordered[cut:]


def evaluate(rows: list[dict], config: RetrievalConfig) -> dict:
    recall_values, precision_values, reductions = [], [], []
    for row in rows:
        result = retrieve(row["context"], row["question"], config)
        retrieved = result.retrieved_text
        found = [evidence for evidence in row["gold_evidence"] if evidence in retrieved]
        relevant_hits = [
            hit for hit in result.hits
            if any(evidence in hit.text for evidence in row["gold_evidence"])
        ]
        recall_values.append(len(found) / len(row["gold_evidence"]))
        precision_values.append(len(relevant_hits) / len(result.hits) if result.hits else 0.0)
        reductions.append(result.character_reduction_fraction)
    mean = lambda values: round(statistics.mean(values), 6) if values else 0.0
    metrics = {
        "examples": len(rows),
        "evidence_recall": mean(recall_values),
        "evidence_precision": mean(precision_values),
        "character_reduction_fraction": mean(reductions),
    }
    metrics["utility_score"] = round(
        WEIGHTS["evidence_recall"] * metrics["evidence_recall"]
        + WEIGHTS["evidence_precision"] * metrics["evidence_precision"]
        + WEIGHTS["char_reduction"] * metrics["character_reduction_fraction"], 6
    )
    return metrics


def tune(rows: list[dict], seed: int = 2026, min_recall: float = 0.90) -> dict:
    if not 0.0 <= min_recall <= 1.0:
        raise ValueError("min_recall must be between 0 and 1")
    dev, heldout = split_rows(rows, seed)
    grid = itertools.product(
        (2, 4, 6),          # top_k
        (1000, 2500, 5000), # max_chars
        (0.0, 1.0, 2.0),    # phrase_boost
        (0.0, 0.2, 0.5),    # diversity_penalty
    )
    candidates = []
    for top_k, max_chars, phrase_boost, diversity_penalty in grid:
        config = RetrievalConfig(
            top_k=top_k, max_chars=max_chars,
            phrase_boost=phrase_boost, diversity_penalty=diversity_penalty,
        )
        metrics = evaluate(dev, config)
        candidates.append({
            "config": config.__dict__,
            "dev_metrics": metrics,
            "passes_recall_gate": metrics["evidence_recall"] >= min_recall,
        })
    feasible = [c for c in candidates if c["passes_recall_gate"]]
    pool = feasible or candidates
    pool.sort(key=lambda c: (
        -c["dev_metrics"]["utility_score"],
        -c["dev_metrics"]["evidence_recall"],
        c["dev_metrics"]["character_reduction_fraction"],
        json.dumps(c["config"], sort_keys=True),
    ))
    winner = pool[0]
    heldout_metrics = evaluate(heldout, RetrievalConfig(**winner["config"]))
    return {
        "schema_version": 1,
        "method": "bounded_classical_grid_search",
        "seed": seed,
        "split": {"dev_examples": len(dev), "heldout_examples": len(heldout)},
        "minimum_dev_evidence_recall": min_recall,
        "feasible_candidate_count": len(feasible),
        "candidate_count": len(candidates),
        "winner": winner,
        "heldout_metrics": heldout_metrics,
        "heldout_passes_recall_gate": heldout_metrics["evidence_recall"] >= min_recall,
        "weights": WEIGHTS,
        "answer_accuracy": None,
        "limitations": [
            "Requires exact gold evidence strings supplied by the dataset owner.",
            "Evidence recall is not answer accuracy or general semantic correctness.",
            "Character reduction is not tokenizer-measured token reduction.",
            "Held-out results are reported once for the selected configuration; do not tune against them.",
            "No model inference, embeddings, network calls, or quantum computation are used.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSONL with id, question, context, gold_evidence")
    parser.add_argument("--out", type=Path, default=Path("artifacts/qbs_hybrid_retrieval_tuning.json"))
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--min-recall", type=float, default=0.90)
    args = parser.parse_args()
    try:
        result = tune(load_rows(args.input), args.seed, args.min_recall)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        print(f"\\nWrote {args.out}")
        return 0 if result["heldout_passes_recall_gate"] else 2
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
