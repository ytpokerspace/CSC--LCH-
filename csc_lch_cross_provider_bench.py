#!/usr/bin/env python3
"""Compare original vs CSC-LCH safe text compression using provider-reported usage.

This is a small cross-provider experiment, separate from the existing Anthropic-
specific multi-section benchmark. It makes two generation calls and records the
provider's actual usage. Live calls require explicit confirmation unless --yes.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from csc_lch_bench import compress_text
from csc_lch_provider_clients import AnthropicAdapter, OpenAICompatibleAdapter
from csc_lch_providers import MockProvider


def build_prompt(context: str, question: str) -> str:
    return (
        "Answer the question using only the supplied context. If the answer is "
        "not present, say 'unknown'.\n\n<context>\n"
        + context + "\n</context>\n\nQuestion: " + question
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("anthropic", "openai-compatible", "mock"), default="mock")
    parser.add_argument("--model", default="mock-v1", help="Model identifier required by the selected provider")
    parser.add_argument("--context", required=True, help="UTF-8 text file to compare")
    parser.add_argument("--question", required=True)
    parser.add_argument("--must-match", action="append", default=[],
                        help="Optional regex expected in the answer; repeat for all required patterns")
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--yes", action="store_true", help="Skip confirmation before live API calls")
    parser.add_argument("--out", default="csc_lch_cross_provider_report.json")
    args = parser.parse_args()

    context = Path(args.context).read_text(encoding="utf-8")
    compressed = compress_text(context)
    if args.provider == "mock":
        adapter = MockProvider()
    elif args.provider == "anthropic":
        adapter = AnthropicAdapter()
    else:
        adapter = OpenAICompatibleAdapter()

    if args.provider != "mock" and not args.yes:
        print("This will make two live model requests and may incur API charges.")
        if input("Continue? [y/N] ").strip().lower() != "y":
            print("Cancelled; no requests made.")
            return 2

    cases = {"original": context, "compressed": compressed}
    report = {
        "provider": adapter.provider_name,
        "model_requested": args.model,
        "compression": {
            "original_characters": len(context),
            "compressed_characters": len(compressed),
            "character_reduction_percent": (
                100.0 * (len(context) - len(compressed)) / len(context) if context else 0.0
            ),
            "note": "Character reduction is not token reduction.",
        },
        "results": {},
    }
    for label, variant in cases.items():
        prompt = build_prompt(variant, args.question)
        preflight = adapter.count_tokens(prompt, model=args.model)
        started = time.perf_counter()
        response = adapter.generate(
            prompt, model=args.model, options={"max_tokens": args.max_tokens}
        )
        elapsed = time.perf_counter() - started
        matches = [bool(re.search(pattern, response.text, re.I | re.M)) for pattern in args.must_match]
        report["results"][label] = {
            "answer": response.text,
            "elapsed_seconds": round(elapsed, 4),
            "preflight_token_count": preflight,
            "preflight_count_source": (
                "provider-or-local-tokenizer" if preflight is not None else "unavailable"
            ),
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "source": response.usage.source,
            },
            "required_pattern_matches": matches,
            "all_required_patterns_matched": all(matches) if args.must_match else None,
        }
        print("%s: %s input tokens, %s output tokens, %.2fs" % (
            label,
            response.usage.input_tokens if response.usage.input_tokens is not None else "not reported",
            response.usage.output_tokens if response.usage.output_tokens is not None else "not reported",
            elapsed,
        ))

    orig = report["results"]["original"]["usage"]["input_tokens"]
    comp = report["results"]["compressed"]["usage"]["input_tokens"]
    if isinstance(orig, int) and isinstance(comp, int):
        report["input_token_reduction_percent"] = (100.0 * (orig - comp) / orig) if orig else 0.0
        report["input_token_comparison_source"] = "provider-reported generation usage"
    else:
        report["input_token_reduction_percent"] = None
        report["input_token_comparison_source"] = "unavailable; no token savings inferred"

    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved report:", args.out)
    if args.provider == "mock":
        print("NOTE: mock mode tests plumbing only; it provides no evidence about compression quality or savings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
