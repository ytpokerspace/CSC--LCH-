#!/usr/bin/env python3
"""Audit LongBench v2 and run a deterministic, offline lexical context-preparation baseline.

No model inference, paid API, or third-party dataset library is used. The optional
tiktoken package counts local cl100k_base tokens; it does not call an API.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

DATA_URL = "https://huggingface.co/datasets/THUDM/LongBench-v2/resolve/main/data.json"
REQUIRED = ("_id", "domain", "sub_domain", "difficulty", "length", "question",
            "choice_A", "choice_B", "choice_C", "choice_D", "answer", "context")
ANSWER_LABELS = {"A", "B", "C", "D"}
WORD_RE = re.compile(r"[A-Za-z0-9]+")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can",
    "could", "did", "do", "does", "for", "from", "had", "has", "have", "he",
    "her", "hers", "him", "his", "how", "i", "if", "in", "into", "is", "it",
    "its", "may", "might", "more", "most", "of", "on", "or", "our", "she",
    "should", "that", "the", "their", "them", "there", "these", "they", "this",
    "those", "to", "was", "we", "were", "what", "when", "where", "which",
    "who", "why", "will", "with", "would", "you", "your",
}

def words(text: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(text)]

def load_rows(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if isinstance(data, dict):
        for key in ("data", "train", "test"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise ValueError("Dataset must be a JSON array or JSONL object-per-line file.")
    if not all(isinstance(row, dict) for row in data):
        raise ValueError("Every dataset row must be a JSON object.")
    return data

def download_dataset(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(DATA_URL, headers={"User-Agent": "CSC-LCH-LongBench-Audit/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as out:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            out.write(block)

def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ids, duplicates, missing_fields, invalid_answers, bad_text = set(), [], [], [], []
    domain_counts, difficulty_counts, length_counts = Counter(), Counter(), Counter()
    context_chars, question_chars = [], []
    for index, row in enumerate(rows):
        rid = row.get("_id")
        if not isinstance(rid, str) or not rid.strip():
            missing_fields.append({"row": index, "field": "_id"})
        elif rid in ids:
            duplicates.append(rid)
        else:
            ids.add(rid)
        for field in REQUIRED:
            if field not in row or row[field] is None:
                missing_fields.append({"row": index, "field": field})
        for field in ("question", "context", "choice_A", "choice_B", "choice_C", "choice_D"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                bad_text.append({"row": index, "field": field})
        if row.get("answer") not in ANSWER_LABELS:
            invalid_answers.append({"row": index, "answer": row.get("answer")})
        domain_counts[str(row.get("domain", "<missing>"))] += 1
        difficulty_counts[str(row.get("difficulty", "<missing>"))] += 1
        length_counts[str(row.get("length", "<missing>"))] += 1
        if isinstance(row.get("context"), str):
            context_chars.append(len(row["context"]))
        if isinstance(row.get("question"), str):
            question_chars.append(len(row["question"]))
    return {
        "rows": len(rows),
        "unique_ids": len(ids),
        "duplicate_ids": duplicates,
        "missing_required_fields": missing_fields,
        "invalid_answer_labels": invalid_answers,
        "blank_or_nonstring_text_fields": bad_text,
        "answer_label_counts": dict(sorted(Counter(str(r.get("answer")) for r in rows).items())),
        "domain_counts": dict(sorted(domain_counts.items())),
        "difficulty_counts": dict(sorted(difficulty_counts.items())),
        "length_category_counts": dict(sorted(length_counts.items())),
        "context_characters": {
            "total": sum(context_chars),
            "min": min(context_chars) if context_chars else None,
            "max": max(context_chars) if context_chars else None,
            "mean": round(sum(context_chars) / len(context_chars), 2) if context_chars else None,
        },
        "question_characters": {
            "total": sum(question_chars),
            "mean": round(sum(question_chars) / len(question_chars), 2) if question_chars else None,
        },
        "schema_valid": not (duplicates or missing_fields or invalid_answers or bad_text),
    }

def make_chunks(text: str, chunk_chars: int, overlap_chars: int) -> list[str]:
    if chunk_chars <= 0 or overlap_chars < 0 or overlap_chars >= chunk_chars:
        raise ValueError("Require chunk_chars > overlap_chars >= 0.")
    if not text:
        return [""]
    stride = chunk_chars - overlap_chars
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + chunk_chars])
        if start + chunk_chars >= len(text):
            break
        start += stride
    return chunks

def lexical_retrieve(context: str, question: str, top_k: int,
                     chunk_chars: int, overlap_chars: int) -> tuple[str, float, int]:
    if top_k <= 0:
        raise ValueError("top_k must be positive.")
    query_terms = {w for w in words(question) if len(w) > 1 and w not in STOPWORDS}
    chunks = make_chunks(context, chunk_chars, overlap_chars)
    if not query_terms:
        selected = list(enumerate(chunks[:top_k]))
        coverage = 0.0
    else:
        ranked = []
        for index, chunk in enumerate(chunks):
            chunk_terms = set(words(chunk))
            score = len(query_terms.intersection(chunk_terms))
            ranked.append((score, -index, index, chunk))
        ranked.sort(reverse=True)
        chosen = sorted(ranked[:min(top_k, len(ranked))], key=lambda item: item[2])
        selected = [(item[2], item[3]) for item in chosen]
        present = set()
        for _, chunk in selected:
            present.update(words(chunk))
        coverage = len(query_terms.intersection(present)) / len(query_terms)
    return "\n\n".join(chunk for _, chunk in selected), coverage, len(chunks)

def load_tokenizer():
    try:
        import tiktoken
    except ImportError as exc:
        raise RuntimeError(
            "Missing optional tokenizer. In Colab run: !pip -q install tiktoken"
        ) from exc
    return tiktoken.get_encoding("cl100k_base")

def token_count(tokenizer, text: str) -> int:
    return len(tokenizer.encode(text, disallowed_special=()))

def run_baseline(rows: list[dict[str, Any]], tokenizer, sample_size: int,
                 seed: int, top_k: int, chunk_chars: int, overlap_chars: int) -> dict[str, Any]:
    rng = random.Random(seed)
    sample_indices = set(rng.sample(range(len(rows)), min(sample_size, len(rows))))
    full_tokens = retrieved_tokens = 0
    coverage_values = []
    sample_details = []
    for index, row in enumerate(rows):
        context = row["context"]
        retrieved, coverage, chunk_count = lexical_retrieve(
            context, row["question"], top_k, chunk_chars, overlap_chars
        )
        full_count = token_count(tokenizer, context)
        retrieved_count = token_count(tokenizer, retrieved)
        full_tokens += full_count
        retrieved_tokens += retrieved_count
        coverage_values.append(coverage)
        if index in sample_indices:
            sample_details.append({
                "row_index": index,
                "question_id": row["_id"],
                "domain": row["domain"],
                "difficulty": row["difficulty"],
                "length": row["length"],
                "gold_answer_label": row["answer"],
                "context_characters": len(context),
                "chunk_count": chunk_count,
                "full_context_tokens": full_count,
                "retrieved_context_tokens": retrieved_count,
                "query_term_coverage_proxy": round(coverage, 6),
            })
    reduction = 1 - (retrieved_tokens / full_tokens) if full_tokens else 0.0
    return {
        "protocol": "csc_lch_longbench_v2_lexical_baseline_v1",
        "examples_evaluated": len(rows),
        "sample_size": len(sample_details),
        "sample_seed": seed,
        "top_k_chunks": top_k,
        "chunk_chars": chunk_chars,
        "overlap_chars": overlap_chars,
        "tokenizer": "cl100k_base",
        "total_full_context_tokens": full_tokens,
        "total_retrieved_context_tokens": retrieved_tokens,
        "context_token_reduction_fraction": round(reduction, 6),
        "mean_query_term_coverage_proxy": round(
            sum(coverage_values) / len(coverage_values), 6
        ) if coverage_values else None,
        "sampled_examples": sorted(sample_details, key=lambda x: x["row_index"]),
        "answer_accuracy": None,
        "answer_accuracy_note": (
            "Not measured: this script does not generate answers or run model inference. "
            "The dataset's A-D labels are retained for a later paired prediction evaluation."
        ),
        "method_note": (
            "This is an explicit lexical control: split context into fixed character windows, "
            "rank by count of distinct non-stopword query terms present, break ties by earlier "
            "chunk, then restore selected chunks to source order. Query-term coverage is a lexical "
            "diagnostic, not evidence recall or answer accuracy. It is not the full CSC-LCH retriever."
        ),
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/longbench_v2.json"),
                        help="Local official JSON/JSONL dataset path.")
    parser.add_argument("--download", action="store_true",
                        help="Download the official LongBench v2 JSON file if --data is absent.")
    parser.add_argument("--outdir", type=Path, default=Path("artifacts/longbench_v2_audit"))
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--chunk-chars", type=int, default=3000)
    parser.add_argument("--overlap-chars", type=int, default=300)
    args = parser.parse_args()
    try:
        if args.sample_size < 1:
            raise ValueError("--sample-size must be at least 1")
        if not args.data.exists():
            if not args.download:
                raise FileNotFoundError(
                    f"{args.data} not found. Add --download or supply --data PATH."
                )
            print(f"Downloading official dataset to {args.data} ...")
            download_dataset(args.data)
        rows = load_rows(args.data)
        audit = audit_rows(rows)
        args.outdir.mkdir(parents=True, exist_ok=True)
        (args.outdir / "dataset_audit.json").write_text(
            json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print("DATASET AUDIT")
        print(json.dumps(audit, indent=2))
        if not audit["schema_valid"]:
            raise ValueError("Dataset audit found schema or integrity problems; baseline stopped.")
        tokenizer = load_tokenizer()
        baseline = run_baseline(
            rows, tokenizer, args.sample_size, args.seed, args.top_k,
            args.chunk_chars, args.overlap_chars
        )
        (args.outdir / "baseline_summary.json").write_text(
            json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print("\nLEXICAL BASELINE")
        print(json.dumps(baseline, indent=2))
        print(f"\nWrote audit and baseline artifacts to: {args.outdir}")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
