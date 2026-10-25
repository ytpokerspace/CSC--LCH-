#!/usr/bin/env python3
"""Local GPT-4o-tokenizer audit for CSC-LCH.

This counts text with tiktoken's public o200k_base encoding. It does not call a
model or provider API. Counts exclude chat framing/server-side details, so they
are tokenizer-payload counts, not billed API usage. The corpus is synthetic.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import tiktoken
import csc_lch_bench as bench


def count(encoding, system: str, context: str, question: str, tool_schema=None) -> int:
    # Count all text payload components with one encoding; separators are explicit.
    payload = system + "\n\nCONTEXT:\n" + context + "\n\nQUESTION:\n" + question
    if tool_schema is not None:
        payload += "\n\nTOOL_SCHEMA_JSON:\n" + json.dumps(tool_schema, ensure_ascii=False, sort_keys=True)
    return len(encoding.encode(payload))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=int, default=1)
    parser.add_argument("--out", default="benchmark-results/tokenizer-audit")
    args = parser.parse_args()
    if args.scale < 1:
        parser.error("--scale must be >= 1")

    encoding = tiktoken.get_encoding("o200k_base")  # GPT-4o-family tokenizer encoding
    segs, questions = bench.build_synthetic(args.scale, seed=7)
    pairs = bench.usable_pairs(bench.LEXICON)
    variants = bench.build_variants(segs, pairs, pairs, defer_from=4)

    conditions = {
        "full_context": {
            "system": bench.BASE_SYSTEM,
            "context": variants["S0"],
            "tool": None,
        }
    }
    for name, variant in variants["variants"].items():
        conditions[name] = {
            "system": bench.BASE_SYSTEM + (("\n\n" + variant["registry"]) if variant["registry"] else ""),
            "context": variant["text"],
            "tool": bench.HYDRATE_TOOL if variant["store"] else None,
        }

    results = {}
    for name, condition in conditions.items():
        counts = [
            count(encoding, condition["system"], condition["context"], qa["q"], condition["tool"])
            for qa in questions
        ]
        results[name] = {
            "questions": len(counts),
            "mean_input_payload_tokens": round(sum(counts) / len(counts), 2),
            "min_input_payload_tokens": min(counts),
            "max_input_payload_tokens": max(counts),
            "total_over_all_questions": sum(counts),
        }

    baseline = results["full_context"]["mean_input_payload_tokens"]
    for name, result in results.items():
        result["reduction_vs_full_context_pct"] = round(
            100 * (baseline - result["mean_input_payload_tokens"]) / baseline, 2
        ) if baseline else 0.0

    report = {
        "method": "tiktoken o200k_base local encoding",
        "model_family_reference": "GPT-4o tokenizer encoding; not a live API request",
        "synthetic_scale": args.scale,
        "seed": 7,
        "question_count": len(questions),
        "conditions": results,
        "limitations": [
            "Counts are exact for the concatenated text passed to o200k_base, not provider-reported request tokens.",
            "Chat message framing and provider-specific tool accounting may differ.",
            "Synthetic corpus only; this is not an accuracy or semantic-equivalence test.",
            "Hydration is represented by the tool schema overhead; actual hydration calls are not simulated.",
            "No model generation or paid API calls are made."
        ],
    }

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "CSC-LCH LOCAL TOKENIZER AUDIT",
        "Encoding: o200k_base (GPT-4o-family tokenizer encoding)",
        "Corpus: synthetic; seed=7; scale=%d; questions=%d" % (args.scale, len(questions)),
        "No provider API or model generation calls.",
        "",
        "%-18s %12s %12s %12s" % ("condition", "mean tokens", "min", "max"),
    ]
    for name, result in results.items():
        lines.append("%-18s %12.2f %12d %12d  (%+.2f%% vs full)" % (
            name, result["mean_input_payload_tokens"], result["min_input_payload_tokens"],
            result["max_input_payload_tokens"], result["reduction_vs_full_context_pct"]))
    lines += ["", "LIMITATIONS: " + " ".join(report["limitations"])]
    output.with_suffix(".txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print("Saved: %s and %s" % (output.with_suffix(".txt"), output.with_suffix(".json")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
