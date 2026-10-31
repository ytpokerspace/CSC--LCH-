"""Offline CSC-LCH dictionary and lazy-hydration benchmark.

Examples:
  python csc_lch_compression_bench.py
  python csc_lch_compression_bench.py --selected 0,2 --output report.json

Selection is supplied explicitly (oracle selection). This measures payload cost,
not semantic retrieval accuracy or live API billing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from csc_lch_codec import (
    build_lazy_payload, decode_documents, decode_lazy_payload,
    encode_documents, tokenizer_counter,
)

SYNTHETIC_CORPUS = [
    ("architecture", "CSC LCH preserves source text, builds a semantic graph, and retrieves context lazily. "
     "The semantic graph stores reusable symbols and typed relationships."),
    ("benchmarking", "A benchmark must compare the original prompt with the complete encoded payload. "
     "Dictionary overhead, retrieval overhead, and reconstruction must all be measured."),
    ("reconstruction", "Exact reconstruction means every character is restored, including whitespace, "
     "punctuation, Unicode, and emoji such as 🧠."),
    ("retrieval", "Lazy context hydration retrieves only selected documents. Selection is supplied by the "
     "benchmark and does not prove that a semantic retriever can select relevant documents."),
    ("repeated-patterns", "CSC LCH preserves source text, builds a semantic graph, and retrieves context lazily. "
     "Repeated terms can make dictionary coding useful, but the dictionary itself has a cost."),
]


def run_benchmark(documents: List[str], selected_ids: List[int], model: str = "gpt-4o") -> dict:
    count_tokens, tokenizer_name = tokenizer_counter(model)
    original = "\n\n".join(documents)
    full = encode_documents(documents)
    reconstructed = decode_documents(full.serialized)
    if reconstructed != documents:
        raise AssertionError("full-corpus reconstruction mismatch")

    lazy = build_lazy_payload(documents, selected_ids)
    index, actual_ids, hydrated = decode_lazy_payload(lazy)
    expected = [documents[i] for i in sorted(set(selected_ids))]
    if actual_ids != sorted(set(selected_ids)) or hydrated != expected:
        raise AssertionError("lazy hydration reconstruction mismatch")

    raw_tokens = count_tokens(original)
    full_tokens = count_tokens(full.serialized)
    lazy_tokens = count_tokens(lazy)
    raw_bytes = len(original.encode("utf-8"))
    full_bytes = len(full.serialized.encode("utf-8"))
    lazy_bytes = len(lazy.encode("utf-8"))

    def delta(new: int, baseline: int) -> float:
        return ((new - baseline) / baseline * 100.0) if baseline else 0.0

    return {
        "benchmark": "CSC-LCH reversible dictionary + oracle-selected hydration",
        "version": 1,
        "tokenizer": tokenizer_name,
        "model": model,
        "documents": len(documents),
        "selected_document_ids": sorted(set(selected_ids)),
        "selected_document_count": len(set(selected_ids)),
        "source_characters": len(original),
        "dictionary_entries": full.dictionary_entries,
        "integrity": {
            "full_corpus_exact": reconstructed == documents,
            "lazy_selected_exact": hydrated == expected,
            "source_sha256_not_applicable": "This experiment checks exact decoded strings; source checksums remain available in v1.1 source records.",
        },
        "measurements": {
            "raw_full_context": {"utf8_bytes": raw_bytes, "tokens": raw_tokens},
            "encoded_full_corpus": {
                "utf8_bytes": full_bytes,
                "tokens": full_tokens,
                "token_delta_percent_vs_raw": round(delta(full_tokens, raw_tokens), 3),
                "byte_delta_percent_vs_raw": round(delta(full_bytes, raw_bytes), 3),
            },
            "lazy_index_plus_selected_payload": {
                "utf8_bytes": lazy_bytes,
                "tokens": lazy_tokens,
                "token_delta_percent_vs_raw_full_context": round(delta(lazy_tokens, raw_tokens), 3),
                "byte_delta_percent_vs_raw_full_context": round(delta(lazy_bytes, raw_bytes), 3),
            },
        },
        "limitations": [
            "Dictionary encoding is lossless serialization, not semantic compression or summarization.",
            "Lazy document selection is supplied by the caller (oracle selection); retrieval relevance is not measured.",
            "Token counts are local tokenizer counts only when tiktoken is installed; no API calls or billing are involved.",
            "Real prompt framing, system instructions, tool schemas, and provider-side tokenization overhead are excluded.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selected", default="0,2", help="comma-separated document IDs selected for hydration")
    parser.add_argument("--model", default="gpt-4o", help="tiktoken model encoding name")
    parser.add_argument("--output", default="csc_lch_v1_2_benchmark.json")
    args = parser.parse_args()
    selected = [int(item) for item in args.selected.split(",") if item.strip()]
    report = run_benchmark(SYNTHETIC_CORPUS, selected, args.model)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    print(f"Saved report: {args.output}")


if __name__ == "__main__":
    main()
