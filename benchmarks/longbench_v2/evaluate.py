#!/usr/bin/env python3
"""Offline LongBench v2 context-budget experiment.

This is a retrieval/context-preparation prototype, NOT a model-answer benchmark and
NOT a claim that CSC-LCH is already integrated. It compares full-context prompting
with a deterministic lexical top-k chunk selector while retaining the original
context in memory for exact hydration. No model API is called.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

DATASET_URL = "https://huggingface.co/datasets/THUDM/LongBench-v2/resolve/main/data.json"
TOKENIZER_NAME = "cl100k_base"
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for", "from",
    "has", "have", "how", "in", "into", "is", "it", "its", "of", "on", "or",
    "that", "the", "their", "there", "this", "to", "was", "what", "when",
    "where", "which", "who", "why", "will", "with", "would", "you", "your",
}


def load_rows(path: Path | None, url: str = DATASET_URL) -> list[dict[str, Any]]:
    if path is not None:
        raw = path.read_text(encoding="utf-8")
    else:
        request = urllib.request.Request(url, headers={"User-Agent": "CSC-LCH-LongBench-Experiment/0.1"})
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read().decode("utf-8")
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    rows = []
    for line_no, line in enumerate(raw.splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON/JSONL at line {line_no}: {exc}") from exc
    return rows


def validate_row(row: dict[str, Any]) -> None:
    required = ("_id", "question", "context", "answer")
    missing = [key for key in required if key not in row]
    if missing:
        raise ValueError(f"Dataset row missing required fields: {missing}")
    if row["answer"] not in {"A", "B", "C", "D"}:
        raise ValueError(f"Unexpected answer label for {row['_id']!r}")


def terms(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9_]{2,}", text)
        if token.lower() not in STOPWORDS
    }


def split_chunks(text: str, chunk_chars: int = 3000, overlap_chars: int = 300) -> list[str]:
    """Deterministic overlapping chunks; source text is never rewritten."""
    if chunk_chars <= 0 or overlap_chars < 0 or overlap_chars >= chunk_chars:
        raise ValueError("Require chunk_chars > overlap_chars >= 0")
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_chars)
        if end < len(text):
            boundary = text.rfind("\n", start + chunk_chars // 2, end)
            if boundary > start:
                end = boundary + 1
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(start + 1, end - overlap_chars)
    return chunks


def select_chunks(question: str, chunks: list[str], top_k: int = 5) -> list[int]:
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    query_terms = terms(question)
    if not chunks:
        return []
    scored = []
    for index, chunk in enumerate(chunks):
        score = len(query_terms & terms(chunk))
        scored.append((score, -index, index))
    scored.sort(reverse=True)
    return sorted(item[2] for item in scored[: min(top_k, len(scored))])


def token_count(encoder: Any, text: str) -> int:
    return len(encoder.encode(text, disallowed_special=()))


def evaluate(rows: list[dict[str, Any]], limit: int, seed: int, top_k: int,
             chunk_chars: int, overlap_chars: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        import tiktoken
    except ImportError as exc:
        raise RuntimeError("Install requirements: python -m pip install tiktoken") from exc

    encoder = tiktoken.get_encoding(TOKENIZER_NAME)
    for row in rows:
        validate_row(row)
    if not rows:
        raise ValueError("Dataset contains no rows")
    if limit < 1:
        raise ValueError("--limit must be >= 1")

    if limit < len(rows):
        selected = random.Random(seed).sample(rows, limit)
        selected.sort(key=lambda row: str(row["_id"]))
    else:
        selected = rows

    results: list[dict[str, Any]] = []
    total_full = total_retrieved = 0
    for row in selected:
        context = row["context"]
        question = row["question"]
        chunks = split_chunks(context, chunk_chars, overlap_chars)
        chosen_indices = select_chunks(question, chunks, top_k)
        retrieved = "\n".join(chunks[index] for index in chosen_indices)
        full_tokens = token_count(encoder, context)
        retrieved_tokens = token_count(encoder, retrieved)
        query_terms = terms(question)
        available_query_terms = query_terms & terms(context)
        retained_query_terms = query_terms & terms(retrieved)
        coverage = (
            len(available_query_terms & retained_query_terms) / len(available_query_terms)
            if available_query_terms else 1.0
        )
        total_full += full_tokens
        total_retrieved += retrieved_tokens
        results.append({
            "id": str(row["_id"]),
            "domain": row.get("domain", ""),
            "difficulty": row.get("difficulty", ""),
            "length": row.get("length", ""),
            "full_context_tokens": full_tokens,
            "retrieved_context_tokens": retrieved_tokens,
            "chunks_total": len(chunks),
            "chunks_selected": len(chosen_indices),
            "query_term_coverage_proxy": round(coverage, 6),
            "answer_scored": False,
        })

    reduction = 1.0 - (total_retrieved / total_full) if total_full else 0.0
    summary = {
        "benchmark": "LongBench v2",
        "experiment": "full_context_vs_lexical_top_k_context_preparation",
        "status": "context_preparation_only_no_model_inference",
        "dataset_rows_available": len(rows),
        "examples_evaluated": len(selected),
        "seed": seed,
        "top_k_chunks": top_k,
        "chunk_chars": chunk_chars,
        "overlap_chars": overlap_chars,
        "tokenizer": TOKENIZER_NAME,
        "total_full_context_tokens": total_full,
        "total_retrieved_context_tokens": total_retrieved,
        "context_token_reduction_fraction": round(reduction, 6),
        "mean_query_term_coverage_proxy": round(
            sum(item["query_term_coverage_proxy"] for item in results) / len(results), 6
        ),
        "answer_accuracy": None,
        "answer_accuracy_note": (
            "Not measured: this workflow does not call an LLM. Query-term coverage is "
            "a diagnostic proxy, not evidence recall or answer accuracy."
        ),
        "limitations": [
            "Lexical top-k retrieval is a simple control, not the full CSC-LCH algorithm.",
            "Original context remains in memory; this measures prompt selection, not archive storage savings.",
            "cl100k_base is a fixed reference tokenizer, not every evaluated model's tokenizer.",
            "No model inference, answer scoring, or paid API calls are performed.",
        ],
    }
    return summary, results


def write_outputs(summary: dict[str, Any], results: list[dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if results:
        with (out_dir / "per_example.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(results[0]))
            writer.writeheader()
            writer.writerows(results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, help="Local JSON/JSONL dataset; otherwise download official data")
    parser.add_argument("--dataset-url", default=DATASET_URL)
    parser.add_argument("--limit", type=int, default=10, help="Number of examples; use 503 for the full set")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--chunk-chars", type=int, default=3000)
    parser.add_argument("--overlap-chars", type=int, default=300)
    parser.add_argument("--output-dir", type=Path, default=Path("research-results/longbench-v2"))
    args = parser.parse_args(argv)
    try:
        rows = load_rows(args.dataset, args.dataset_url)
        summary, results = evaluate(
            rows, args.limit, args.seed, args.top_k, args.chunk_chars, args.overlap_chars
        )
        write_outputs(summary, results, args.output_dir)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
