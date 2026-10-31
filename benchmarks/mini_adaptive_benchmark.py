#!/usr/bin/env python3
"""Small, deterministic smoke benchmark for adaptive CSC LCH.

No network calls, model calls, or dependencies. This tests the bookkeeping and
retrieval policy on hand-labeled toy cases; it does NOT test automatic semantic
extraction or real model accuracy. Token counts are a rough regex proxy, not a
model tokenizer. Replace with the target model's tokenizer before making token
savings claims.

Run: python3 benchmarks/mini_adaptive_benchmark.py
"""
import re

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[^\w\s]", re.UNICODE)

CASES = [
    {
        "id": "meeting",
        "source": "Mira approved version 2 on Tuesday. She rejected version 3 on Thursday.",
        "summary": "Mira approved version 2 and rejected version 3.",
        "facts": {
            "approval": {"value": "Tuesday", "record": "APPROVE(Mira, version_2, Tuesday)"},
            "rejection": {"value": "Thursday", "record": "REJECT(Mira, version_3, Thursday)"},
        },
        "questions": ["approval", "rejection"],
    },
    {
        "id": "temperature",
        "source": "The sample reached 80 degrees Celsius at 14:00, but only after pressure was reduced.",
        "summary": "The sample reached 80 degrees Celsius.",
        "facts": {
            "temperature": {"value": "80 degrees Celsius", "record": "TEMP(sample, 80, Celsius)"},
            "time": {"value": "14:00", "record": "TIME(sample, 14:00)"},
            "condition": {"value": "after pressure was reduced", "record": "COND(pressure_reduced -> sample_reached_80C)"},
        },
        "questions": ["temperature", "time", "condition"],
    },
    {
        "id": "shipment",
        "source": "Order 481 shipped on May 4. It did not arrive on May 6; the carrier reported a weather delay.",
        "summary": "Order 481 shipped on May 4 and was delayed by weather.",
        "facts": {
            "shipped": {"value": "May 4", "record": "SHIP(order_481, May_4)"},
            "arrival": {"value": "did not arrive on May 6", "record": "NOT_ARRIVED(order_481, May_6)"},
            "cause": {"value": "weather delay", "record": "CAUSE(weather, shipment_delay)"},
        },
        "questions": ["shipped", "arrival", "cause"],
    },
    {
        "id": "experiment",
        "source": "Trial B improved recall by 4 percentage points, but response time increased by 120 milliseconds.",
        "summary": "Trial B improved recall but became slower.",
        "facts": {
            "recall": {"value": "4 percentage points", "record": "DELTA(recall, +4, percentage_points)"},
            "latency": {"value": "120 milliseconds", "record": "DELTA(response_time, +120, milliseconds)"},
        },
        "questions": ["recall", "latency"],
    },
]


def tokens(text):
    return len(TOKEN_RE.findall(text))


def answer_available(text, expected):
    """Simple literal check; deliberately not a semantic judge."""
    return expected.casefold() in text.casefold()


def run():
    totals = {name: {"tokens": 0, "correct": 0, "questions": 0, "hydration_tokens": 0}
              for name in ("original", "summary", "graph", "graph_hydrated")}
    print("MINI ADAPTIVE CSC LCH BENCHMARK")
    print("Token metric: regex proxy, NOT a model tokenizer. Hand-labeled toy data only.\n")
    for case in CASES:
        source = case["source"]
        summary = case["summary"]
        graph = " | ".join(item["record"] for item in case["facts"].values())
        totals["original"]["tokens"] += tokens(source)
        totals["summary"]["tokens"] += tokens(summary)
        totals["graph"]["tokens"] += tokens(graph)
        totals["graph_hydrated"]["tokens"] += tokens(graph)
        for q in case["questions"]:
            expected = case["facts"][q]["value"]
            totals["original"]["questions"] += 1
            totals["summary"]["questions"] += 1
            totals["graph"]["questions"] += 1
            totals["graph_hydrated"]["questions"] += 1
            totals["original"]["correct"] += answer_available(source, expected)
            totals["summary"]["correct"] += answer_available(summary, expected)
            # The graph carries normalized facts, not necessarily the source wording.
            graph_text = graph + " " + " ".join(v["value"] for v in case["facts"].values())
            graph_has = answer_available(graph_text, expected)
            totals["graph"]["correct"] += graph_has
            if graph_has:
                totals["graph_hydrated"]["correct"] += 1
            else:
                # Simulate one source-span lookup. Charge the query and retrieved fact.
                retrieval = "retrieve " + q + " " + case["facts"][q]["value"]
                overhead = tokens(retrieval)
                totals["graph_hydrated"]["tokens"] += overhead
                totals["graph_hydrated"]["hydration_tokens"] += overhead
                totals["graph_hydrated"]["correct"] += answer_available(retrieval, expected)
    base = totals["original"]["tokens"]
    print(f"{'method':<18} {'proxy_tokens':>12} {'vs_original':>12} {'literal_accuracy':>18} {'hydrate_tokens':>15}")
    for name, row in totals.items():
        pct = (row["tokens"] / base - 1) * 100 if base else 0
        accuracy = row["correct"] / row["questions"] if row["questions"] else 0
        print(f"{name:<18} {row['tokens']:>12} {pct:>11.1f}% {accuracy:>17.1%} {row['hydration_tokens']:>15}")
    print("\nInterpretation: smoke test only. Literal accuracy is not model QA accuracy.")
    print("The graph is hand-authored, so this does not measure extraction quality.")
    print("Use a real target tokenizer and held-out questions before drawing conclusions.")


if __name__ == "__main__":
    run()
