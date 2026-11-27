#!/usr/bin/env python3
"""Score paired model answers against supplied gold answers; standard library only."""
import argparse
import json
import re
import string
import sys
from collections import defaultdict
from pathlib import Path

ARTICLES = {"a", "an", "the"}
PUNCT = set(string.punctuation)

def normalize(text):
    text = str(text or "").lower()
    text = "".join(ch for ch in text if ch not in PUNCT)
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())

def token_f1(prediction, gold):
    pred = normalize(prediction).split()
    truth = normalize(gold).split()
    if not pred and not truth:
        return 1.0
    if not pred or not truth:
        return 0.0
    remaining = list(truth)
    overlap = 0
    for token in pred:
        if token in remaining:
            overlap += 1
            remaining.remove(token)
    if not overlap:
        return 0.0
    precision = overlap / len(pred)
    recall = overlap / len(truth)
    return 2 * precision * recall / (precision + recall)

def score_one(prediction, gold_answers):
    aliases = [gold_answers] if isinstance(gold_answers, str) else gold_answers
    if not isinstance(aliases, list) or not aliases or not all(isinstance(x, str) and x.strip() for x in aliases):
        raise ValueError("gold_answers must be a non-empty string or list of non-empty strings")
    em = max(float(normalize(prediction) == normalize(gold)) for gold in aliases)
    f1 = max(token_f1(prediction, gold) for gold in aliases)
    return em, f1

def load_and_score(path):
    groups = defaultdict(list)
    seen = set()
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {line_no}: each row must be a JSON object")
        for key in ("question_id", "policy", "prediction", "gold_answers"):
            if key not in row:
                raise ValueError(f"line {line_no}: missing field {key!r}")
        qid, policy = row["question_id"], row["policy"]
        if not isinstance(qid, str) or not qid.strip() or not isinstance(policy, str) or not policy.strip():
            raise ValueError(f"line {line_no}: question_id and policy must be non-empty strings")
        key = (qid, policy)
        if key in seen:
            raise ValueError(f"line {line_no}: duplicate question_id/policy pair {key!r}")
        seen.add(key)
        if not isinstance(row["prediction"], str):
            raise ValueError(f"line {line_no}: prediction must be a string")
        em, f1 = score_one(row["prediction"], row["gold_answers"])
        groups[policy].append({
            "question_id": qid,
            "exact_match": em,
            "token_f1": round(f1, 6),
            "prediction": row["prediction"],
        })
    if not groups:
        raise ValueError("input contains no answer observations")
    question_sets = {policy: {x["question_id"] for x in items} for policy, items in groups.items()}
    if len(question_sets) < 2:
        raise ValueError("paired evaluation requires at least two policies")
    reference_policy = sorted(question_sets)[0]
    reference_ids = question_sets[reference_policy]
    for policy, ids in sorted(question_sets.items()):
        if ids != reference_ids:
            raise ValueError(f"paired evaluation requires identical question_id sets; {policy!r} differs from {reference_policy!r}")
    result = {}
    for policy, items in sorted(groups.items()):
        result[policy] = {
            "examples": len(items),
            "exact_match_accuracy": round(sum(x["exact_match"] for x in items) / len(items), 6),
            "mean_token_f1": round(sum(x["token_f1"] for x in items) / len(items), 6),
            "per_example": sorted(items, key=lambda x: x["question_id"]),
        }
    return {
        "schema_version": 1,
        "metric_note": "Exact match is normalized string match against any supplied gold alias. Token F1 is a lexical overlap metric, not a semantic judge.",
        "provenance_note": "Scores are only as reliable as the supplied predictions and gold answers. This script makes no model/API calls and does not generate predictions.",
        "policies": result,
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSONL: question_id, policy, prediction, gold_answers")
    parser.add_argument("--out", type=Path, default=Path("artifacts/answer_accuracy.json"))
    args = parser.parse_args()
    try:
        result = load_and_score(args.input)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        print(f"\nWrote {args.out}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
