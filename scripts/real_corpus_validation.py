#!/usr/bin/env python3
"""Offline paired CSC-LCH validation on the repository's real project documents.

No model/API calls. Retrieval is an exact-evidence oracle: this measures whether
required source evidence remains visible or can be recovered from deferred stubs.
It does NOT measure semantic answer quality or real tokenizer usage.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from csc_lch_bench import Seg, build_variants, join  # noqa: E402

SOURCES = [
    ROOT / "README.md",
    ROOT / "benchmarks" / "milestone6_report.md",
    ROOT / "ARAF" / "README.md",
]

# Evidence strings are exact, auditable claims drawn from the frozen source files.
QUESTIONS = [
    ("Q01", "project license", "GPL-3.0-or-later", "README.md"),
    ("Q02", "source authority", "The source remains the authority.", "benchmarks/milestone6_report.md"),
    ("Q03", "projection limitation", "Projected savings are not measured savings.", "README.md"),
    ("Q04", "paired corpus control", "Use the same frozen corpus and question set for each policy.", "benchmarks/milestone6_report.md"),
    ("Q05", "evidence marker", "OBS", "README.md"),
    ("Q06", "inference marker", "INF", "README.md"),
    ("Q07", "speculation marker", "SPEC", "README.md"),
    ("Q08", "latency limitation", "Hydration-call counts alone do not establish latency or cost.", "benchmarks/milestone6_report.md"),
    ("Q09", "experiment evidence requirement", "Treat performance numbers as established only when the corresponding experiment has been run and its method and evidence are available.", "README.md"),
    ("Q10", "offline evaluation constraint", "Do not make paid API calls in the default workflow.", "benchmarks/milestone6_report.md"),
    ("Q11", "workload limitation", "every LLM or workload will benefit", "README.md"),
    ("Q12", "author attribution", "William Gunnell Cox", "README.md"),
    ("Q13", "retrieval principle", "Retrieve only what's needed, when it's needed.", "benchmarks/milestone6_report.md"),
    ("Q14", "provisional operating policy", "provisional default pending full-cost measurements.", "benchmarks/milestone6_report.md"),
]

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def lexical_units(text: str) -> int:
    """Tokenizer-independent lexical proxy; NOT model tokens."""
    return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))

def tier_for(section: str, source_name: str) -> int:
    critical = {
        "Evaluation standard", "Research status and limitations", "Reproduce carefully",
        "How CSC LCH works", "Milestone 6.1: total-cost and retrieval-latency validation",
        "Reproducibility checklist", "Attribution", "License",
    }
    if section in critical:
        return 1
    if source_name == "milestone6_report.md" and section in {
        "Reported ablation results", "Interpretation", "Provisional policy guidance"
    }:
        return 4
    return 3

def load_real_documents():
    segments = []
    source_hashes = {}
    evidence_text = {}
    counter = 0
    for path in SOURCES:
        raw = path.read_bytes()
        source_hashes[str(path.relative_to(ROOT))] = sha256(raw)
        text = raw.decode("utf-8")
        evidence_text[str(path.relative_to(ROOT))] = text
        section = ""
        for block in re.split(r"\n\s*\n", text):
            block = block.strip()
            if not block:
                continue
            if block.startswith("#"):
                section = block.lstrip("#").strip()
                continue
            # Keep source paragraphs intact; the heading determines an explicit tier.
            counter += 1
            segments.append(Seg(f"doc{counter:03d}", tier_for(section, path.name), block))
    return segments, source_hashes, evidence_text

def evaluate_policy(name, segments, defer_from, baseline_context, expected):
    start = time.perf_counter()
    built = build_variants(segments, {}, {}, defer_from)
    variant = built["variants"]["noglyph"]
    active = variant["text"]
    store = variant["store"]
    build_ms = (time.perf_counter() - start) * 1000.0

    traces = []
    total_active = total_hydration_prompt = total_retrieved = total_output = 0
    recovered = 0
    reconstruction_failures = 0
    hydration_calls = 0

    for qid, label, fact, _source in QUESTIONS:
        q_start = time.perf_counter()
        active_has = fact.casefold() in active.casefold()
        hydrated_ids = []
        recovered_text = []
        if not active_has:
            for sid, original in store.items():
                if fact.casefold() in original.casefold():
                    hydrated_ids.append(sid)
                    recovered_text.append(original)
        found = active_has or bool(recovered_text)
        if found:
            recovered += 1
        hydration_calls += len(hydrated_ids)
        total_active += lexical_units(active)
        total_hydration_prompt += 12 * len(hydrated_ids)
        total_retrieved += sum(lexical_units(x) for x in recovered_text)
        total_output += 8
        # The stored value must be byte-for-byte the original deduplicated segment.
        for sid in hydrated_ids:
            source_original = next((s.text for s in segments if s.id == sid), None)
            if source_original != store[sid]:
                reconstruction_failures += 1
        traces.append({
            "question_id": qid, "evidence_label": label, "evidence": fact,
            "visible_without_hydration": active_has,
            "hydrated_entry_ids": hydrated_ids,
            "evidence_recovered": found,
            "retrieval_elapsed_ms": round((time.perf_counter() - q_start) * 1000, 4),
        })

    baseline_per_task = lexical_units(baseline_context) + 8
    baseline_total = baseline_per_task * len(QUESTIONS)
    policy_total = total_active + total_hydration_prompt + total_retrieved + total_output
    return {
        "policy": name, "defer_from_tier": defer_from, "observations": len(QUESTIONS),
        "baseline_total_lexical_units": baseline_total,
        "policy_active_lexical_units": total_active,
        "hydration_prompt_lexical_units": total_hydration_prompt,
        "retrieved_lexical_units": total_retrieved,
        "output_lexical_units": total_output,
        "policy_total_lexical_units": policy_total,
        "lexical_unit_reduction_pct": round(100 * (baseline_total-policy_total) / baseline_total, 3),
        "evidence_recall": round(recovered / len(expected), 4),
        "evidence_recovered": recovered, "evidence_expected": len(expected),
        "hydration_calls": hydration_calls,
        "stubs_created": len(store),
        "reconstruction_failures": reconstruction_failures,
        "build_elapsed_ms": round(build_ms, 4),
        "per_question": traces,
    }

def main():
    segments, source_hashes, evidence_text = load_real_documents()
    for qid, label, fact, source in QUESTIONS:
        if fact.casefold() not in evidence_text[source].casefold():
            raise SystemExit(f"Evidence fixture {qid} not found in {source}: {fact!r}")

    baseline_context = join(segments)
    corpus_hash = sha256(baseline_context.encode("utf-8"))
    policies = [
        evaluate_policy("T3", segments, 3, baseline_context, QUESTIONS),
        evaluate_policy("T4", segments, 4, baseline_context, QUESTIONS),
        evaluate_policy("T5", segments, 5, baseline_context, QUESTIONS),
    ]
    baseline_recall = 1.0
    report = {
        "schema_version": 1,
        "status": "PASS" if all(p["evidence_recall"] == baseline_recall and p["reconstruction_failures"] == 0 for p in policies) else "REVIEW",
        "data_status": "REAL_REPOSITORY_DOCUMENTS_DETERMINISTIC_EVIDENCE_TEST",
        "scope": "Offline evaluation on the project's actual README and research documentation; not an external corpus or LLM task benchmark.",
        "method": {
            "implementation": "csc_lch_bench.py build_variants; no-glyph path isolates deduplication, safe text compression, and lazy deferral.",
            "retrieval": "Exact-evidence oracle hydrates a deferred source segment when it contains the required evidence.",
            "baseline": "Full uncompressed source context repeated for each of the same 14 evidence questions.",
            "accounting": "Lexical units are a tokenizer-independent proxy, not actual model tokens. Each answer is assigned 8 output units; each hydration prompt is assigned 12 units.",
            "limitations": [
                "No LLM inference or semantic answer scoring.",
                "Exact-match oracle retrieval is an upper bound, not a realistic retriever.",
                "Lexical units are not model tokenizer tokens.",
                "Corpus is real project documentation but small and in-domain.",
                "No provider latency, energy, or monetary cost is measured."
            ]
        },
        "commit_sha": os.environ.get("GITHUB_SHA", "local-unpinned"),
        "corpus_sha256": corpus_hash,
        "source_sha256": source_hashes,
        "source_paragraphs": len(segments),
        "source_lexical_units": lexical_units(baseline_context),
        "baseline": {
            "observations": len(QUESTIONS),
            "total_lexical_units": (lexical_units(baseline_context) + 8) * len(QUESTIONS),
            "evidence_recall": 1.0,
        },
        "policies": policies,
    }
    out = ROOT / "artifacts" / "real_corpus_validation.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nWrote {out.relative_to(ROOT)}")
    return 0 if report["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
