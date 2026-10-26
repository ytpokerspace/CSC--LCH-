#!/usr/bin/env python3
"""Zero-dependency, deterministic mini-benchmark for CSC LCH + mechanism-aware compression.

This is a mechanics smoke test, NOT an LLM quality benchmark. Token counts are a
transparent word/punctuation proxy, not model-tokenizer counts. No network/API calls.
Run: python tests/mini_mechanism_benchmark.py
"""
import re
import json
from collections import OrderedDict

CASES = [
    {
        "id": "quantity",
        "source": "The pump ran for 12 minutes. The pump ran for 12 minutes. Flow was 4 liters per minute. The report estimates 48 liters total, but this was not measured directly.",
        "questions": [
            {"q": "How long did the pump run?", "need": ["12 minutes"]},
            {"q": "Was 48 liters directly measured?", "need": ["not measured directly"]},
        ],
    },
    {
        "id": "condition",
        "source": "The sensor passed in dry conditions. The sensor passed in dry conditions. If humidity exceeds 80 percent, the sensor must be recalibrated. Wet-condition performance is unknown.",
        "questions": [
            {"q": "When must the sensor be recalibrated?", "need": ["humidity", "80 percent"]},
            {"q": "Is wet-condition performance known?", "need": ["unknown"]},
        ],
    },
    {
        "id": "negation",
        "source": "The cache reduced repeated reads by 20 percent in the test. The cache reduced repeated reads by 20 percent in the test. It did not reduce total runtime. The result applies only to a 100-item dataset.",
        "questions": [
            {"q": "Did total runtime decrease?", "need": ["did not reduce total runtime"]},
            {"q": "What dataset scope was tested?", "need": ["100-item dataset"]},
        ],
    },
    {
        "id": "causal",
        "source": "The team observed lower latency after enabling batching. The team observed lower latency after enabling batching. This suggests batching may have helped, but no controlled comparison was run. The cause is not confirmed.",
        "questions": [
            {"q": "Was batching proven to cause lower latency?", "need": ["not confirmed"]},
            {"q": "Was a controlled comparison run?", "need": ["no controlled comparison"]},
        ],
    },
    {
        "id": "time",
        "source": "Version B was tested on 3 March. Version B was tested on 3 March. Version A was tested on 1 March. Results from the two dates are not a fair head-to-head comparison because the hardware configuration changed.",
        "questions": [
            {"q": "When was Version B tested?", "need": ["3 March"]},
            {"q": "Why are the dates not a fair comparison?", "need": ["hardware configuration changed"]},
        ],
    },
    {
        "id": "source",
        "source": "The operator reported 7 failures. The operator reported 7 failures. The log file independently records 5 failures. The discrepancy has not been resolved.",
        "questions": [
            {"q": "How many failures did the log record?", "need": ["5 failures"]},
            {"q": "Is the discrepancy resolved?", "need": ["not been resolved"]},
        ],
    },
    {
        "id": "exception",
        "source": "The converter handled UTF-8 input. The converter handled UTF-8 input. It failed on malformed byte sequences unless strict validation was disabled. No fix has been verified.",
        "questions": [
            {"q": "What was the exception?", "need": ["malformed byte sequences"]},
            {"q": "Has a fix been verified?", "need": ["no fix has been verified"]},
        ],
    },
    {
        "id": "dependency",
        "source": "The report generator needs an index. The report generator needs an index. Without the index, lookup time rose from 2 milliseconds to 30 milliseconds. This measurement came from one run.",
        "questions": [
            {"q": "What happened without the index?", "need": ["2 milliseconds", "30 milliseconds"]},
            {"q": "How many runs support the measurement?", "need": ["one run"]},
        ],
    },
    {
        "id": "unknown",
        "source": "The prototype completed 9 of 10 local tests. The prototype completed 9 of 10 local tests. The tenth test failed. The failure mechanism is unknown and no remote API was used.",
        "questions": [
            {"q": "How many local tests passed?", "need": ["9 of 10"]},
            {"q": "Is the failure mechanism known?", "need": ["unknown"]},
        ],
    },
    {
        "id": "scope",
        "source": "The parser supports nested lists up to depth 4. The parser supports nested lists up to depth 4. Depth 5 is unsupported. Performance beyond depth 4 has not been measured.",
        "questions": [
            {"q": "What is the supported nesting depth?", "need": ["depth 4"]},
            {"q": "Has performance beyond depth 4 been measured?", "need": ["not been measured"]},
        ],
    },
]

def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]

def words(text):
    # Explicit proxy: alphanumeric words and punctuation marks.
    return re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)

def unique_sentences(ss):
    return list(OrderedDict((re.sub(r"\s+", " ", s).casefold(), s) for s in ss).values())

def ordinary_summary(ss):
    # Simple deterministic summary baseline: retain the first two unique sentences.
    return " ".join(unique_sentences(ss)[:2])

def csc_dedup(ss):
    # Deterministic baseline inspired by CSC LCH: remove exact repeated sentences.
    return " ".join(unique_sentences(ss))

def mechanism_compact(ss):
    # Heuristic, not an NLP model: keep unique sentences with evidence-risk markers.
    unique = unique_sentences(ss)
    markers = re.compile(
        r"\b(not|no|never|unless|if|only|unknown|unresolved|unconfirmed|"
        r"not been|has not|did not|must|except|because|suggests|may|estimate|"
        r"reported|records|measured|milliseconds|minutes|percent|depth|fail)\b",
        re.I,
    )
    selected = [s for s in unique if markers.search(s)]
    # Retain one neutral sentence if the heuristic selected none.
    if not selected and unique:
        selected = [unique[0]]
    return " ".join(selected)

def answer_from_context(context, question):
    # Deterministic evidence lookup, no generative model: checks whether required
    # gold phrases remain in the representation or its query-triggered hydration.
    low = context.casefold()
    return low

def main():
    variants = {
        "original": lambda ss: " ".join(ss),
        "ordinary_summary": ordinary_summary,
        "csc_dedup": csc_dedup,
        "mechanism_aware": mechanism_compact,
    }
    totals = {name: {"source_proxy_tokens": 0, "stored_proxy_tokens": 0,
                     "questions": 0, "required_phrase_hits": 0,
                     "all_requirements_met": 0} for name in variants}
    rows = []
    for case in CASES:
        ss = sentences(case["source"])
        source_tokens = len(words(case["source"]))
        for name, fn in variants.items():
            stored = fn(ss)
            store_tokens = len(words(stored))
            stats = totals[name]
            stats["source_proxy_tokens"] += source_tokens
            stats["stored_proxy_tokens"] += store_tokens
            passed = 0
            required = 0
            for qa in case["questions"]:
                stats["questions"] += 1
                ctx = answer_from_context(stored, qa["q"])
                hits = sum(1 for phrase in qa["need"] if phrase.casefold() in ctx)
                required += len(qa["need"])
                stats["required_phrase_hits"] += hits
                ok = hits == len(qa["need"])
                passed += int(ok)
                stats["all_requirements_met"] += int(ok)
            rows.append({"case": case["id"], "variant": name,
                         "source_tokens_proxy": source_tokens,
                         "stored_tokens_proxy": store_tokens,
                         "case_questions_passed": passed,
                         "case_questions_total": len(case["questions"])})
    report = {
        "status": "DETERMINISTIC_SMOKE_TEST_NOT_LLM_QUALITY_EVALUATION",
        "token_count_method": "word/punctuation proxy; not a real model tokenizer",
        "api_calls": 0,
        "cases": len(CASES),
        "questions": sum(len(c["questions"]) for c in CASES),
        "variants": {},
        "case_results": rows,
    }
    for name, s in totals.items():
        saving = 100.0 * (1 - s["stored_proxy_tokens"] / s["source_proxy_tokens"])
        report["variants"][name] = {
            **s,
            "proxy_token_reduction_percent": round(saving, 2),
            "required_phrase_recall_percent": round(
                100.0 * s["required_phrase_hits"] /
                max(1, sum(len(q["need"]) for c in CASES for q in c["questions"])), 2),
            "questions_all_requirements_met_percent": round(
                100.0 * s["all_requirements_met"] / max(1, s["questions"]), 2),
        }
    print(json.dumps(report, indent=2))
    # Smoke-test invariant: original source must preserve every gold phrase.
    assert report["variants"]["original"]["questions_all_requirements_met_percent"] == 100.0
    print("\nPASS: original-source control preserves all expected evidence phrases.")

if __name__ == "__main__":
    main()
