#!/usr/bin/env python3
"""Offline CSC-LCH validation on real project documents with independent retrieval.

No model/API calls. BM25 retrieval sees only the query and deferred paragraphs;
expected evidence is used only for scoring. Lexical units are not model tokens.
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
# Queries are independent of expected evidence: the retriever never receives the answer key.
QUESTIONS = [
    ("Q01", "project license", "What license governs this project?", "GPL-3.0-or-later", "README.md"),
    ("Q02", "source authority", "Which record is authoritative when a summary conflicts with the source?", "The source remains the authority.", "benchmarks/milestone6_report.md"),
    ("Q03", "projection limitation", "Are projected efficiency gains equivalent to measured results?", "Projected savings are not measured savings.", "README.md"),
    ("Q04", "paired corpus control", "What must remain identical when comparing tier policies?", "Use the same frozen corpus and question set for each policy.", "benchmarks/milestone6_report.md"),
    ("Q05", "evidence marker", "Which marker denotes an observed fact?", "OBS", "README.md"),
    ("Q06", "inference marker", "Which marker denotes an inference?", "INF", "README.md"),
    ("Q07", "speculation marker", "Which marker denotes speculation?", "SPEC", "README.md"),
    ("Q08", "latency limitation", "Do retrieval counts alone prove the system is faster or cheaper?", "Hydration-call counts alone do not establish latency or cost.", "benchmarks/milestone6_report.md"),
    ("Q09", "experiment evidence requirement", "What evidence is required before treating a performance claim as established?", "Treat performance numbers as established only when the corresponding experiment has been run and its method and evidence are available.", "README.md"),
    ("Q10", "offline evaluation constraint", "What is the default workflow rule for paid API usage?", "Do not make paid API calls in the default workflow.", "benchmarks/milestone6_report.md"),
    ("Q11", "workload limitation", "Does the framework guarantee benefits for every model and workload?", "every LLM or workload will benefit", "README.md"),
    ("Q12", "author attribution", "Who is credited as the framework author?", "William Gunnell Cox", "README.md"),
    ("Q13", "retrieval principle", "What should happen when a question needs information that is not in active context?", "When a query requires deferred information, resolve the stub and retrieve the original source content.", "benchmarks/milestone6_report.md"),
    ("Q14", "provisional operating policy", "Which tier policy is currently recommended provisionally?", "provisional default pending full-cost measurements.", "benchmarks/milestone6_report.md"),
    ("Q15", "archived T3 ablation result", "What compression ratio was reported for the T3 ablation?", "1.40×", "benchmarks/milestone6_report.md"),
]

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def split_preserving_bytes(raw: bytes) -> list[bytes]:
    """Split at blank-line boundaries without discarding a single source byte."""
    return [part for part in re.split(rb"(\r?\n[ \t]*\r?\n)", raw) if part]


def archive_source(raw: bytes) -> list[dict]:
    """Create ordered, independently hashed cold-storage chunks for one source file."""
    return [
        {"index": index, "data": chunk, "sha256": sha256(chunk)}
        for index, chunk in enumerate(split_preserving_bytes(raw))
    ]


def reconstruct_source(chunks: list[dict], expected_sha256: str) -> bytes:
    """Reassemble exact source bytes; reject missing, reordered, or corrupted chunks."""
    ordered = sorted(chunks, key=lambda item: item["index"])
    if [item["index"] for item in ordered] != list(range(len(ordered))):
        raise ValueError("Source archive chunk sequence is incomplete or duplicated")
    for item in ordered:
        if sha256(item["data"]) != item["sha256"]:
            raise ValueError(f"Source archive chunk SHA-256 mismatch at index {item['index']}")
    rebuilt = b"".join(item["data"] for item in ordered)
    if sha256(rebuilt) != expected_sha256:
        raise ValueError("Reconstructed source file SHA-256 mismatch")
    return rebuilt


def hydrate_verified(segment_id: str, store: dict[str, str], expected_hashes: dict[str, str]) -> str:
    """Retrieve deferred text only when its UTF-8 bytes match the source SHA-256."""
    if segment_id not in store:
        raise KeyError(f"Deferred segment not found: {segment_id}")
    if segment_id not in expected_hashes:
        raise KeyError(f"No source integrity hash for deferred segment: {segment_id}")
    text = store[segment_id]
    actual_hash = sha256(text.encode("utf-8"))
    if actual_hash != expected_hashes[segment_id]:
        raise ValueError(f"SHA-256 mismatch for deferred segment: {segment_id}")
    return text

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
    # The historical, explicitly reported ablation table is archive material.
    # This places genuine repository content in T5 so the archive path is exercised.
    if source_name == "milestone6_report.md" and section == "Reported ablation results":
        return 5
    if source_name == "milestone6_report.md" and section in {
        "Interpretation", "Provisional policy guidance"
    }:
        return 4
    return 3

def load_real_documents():
    segments = []
    source_hashes = {}
    source_archives = {}
    evidence_text = {}
    segment_hashes = {}
    counter = 0
    for path in SOURCES:
        raw = path.read_bytes()
        source_name = str(path.relative_to(ROOT))
        source_hashes[source_name] = sha256(raw)
        source_archives[source_name] = archive_source(raw)
        # Fail closed if the immutable cold archive cannot reproduce source bytes.
        reconstruct_source(source_archives[source_name], source_hashes[source_name])
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
            segment_id = f"doc{counter:03d}"
            segments.append(Seg(segment_id, tier_for(section, path.name), block))
            segment_hashes[segment_id] = sha256(block.encode("utf-8"))
    return segments, source_hashes, source_archives, evidence_text, segment_hashes

def retrieval_terms(text: str) -> list[str]:
    """Normalize query/document text using a small deterministic lexical tokenizer."""
    stop = {"a", "an", "and", "are", "as", "at", "be", "by", "does", "for", "from",
            "how", "in", "is", "it", "of", "on", "or", "the", "this", "to", "what",
            "when", "which", "who", "with"}
    return [token for token in re.findall(r"[a-z0-9]+", text.casefold())
            if token not in stop]


def retrieve_bm25(query: str, store: dict[str, str], top_k: int = 3) -> list[tuple[str, float]]:
    """Rank deferred paragraphs from query text alone; no expected-answer access."""
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    query_tokens = retrieval_terms(query)
    if not query_tokens or not store:
        return []
    docs = {sid: retrieval_terms(text) for sid, text in store.items()}
    n_docs = len(docs)
    avg_len = sum(len(tokens) for tokens in docs.values()) / n_docs
    if avg_len == 0:
        return []
    doc_freq = {}
    for tokens in docs.values():
        for term in set(tokens):
            doc_freq[term] = doc_freq.get(term, 0) + 1
    k1, b = 1.5, 0.75
    ranked = []
    for sid, tokens in docs.items():
        frequencies = {}
        for term in tokens:
            frequencies[term] = frequencies.get(term, 0) + 1
        score = 0.0
        for term in query_tokens:
            tf = frequencies.get(term, 0)
            if not tf:
                continue
            df = doc_freq.get(term, 0)
            idf = __import__("math").log(1 + (n_docs - df + 0.5) / (df + 0.5))
            denominator = tf + k1 * (1 - b + b * len(tokens) / avg_len)
            score += idf * (tf * (k1 + 1)) / denominator
        if score > 0:
            ranked.append((sid, score))
    ranked.sort(key=lambda item: (-item[1], item[0]))
    return ranked[:top_k]

def evaluate_policy(name, segments, defer_from, baseline_context, expected, segment_hashes):
    start = time.perf_counter()
    built = build_variants(segments, {}, {}, defer_from)
    variant = built["variants"]["noglyph"]
    active = variant["text"]
    store = variant["store"]
    build_ms = (time.perf_counter() - start) * 1000.0

    traces = []
    total_active = total_registry = total_hydration_prompt = total_retrieved = total_output = 0
    recovered = 0
    reconstruction_failures = 0
    hydration_calls = 0

    for qid, label, query, fact, _source in QUESTIONS:
        q_start = time.perf_counter()
        active_has = fact.casefold() in active.casefold()
        hydrated_ids = []
        recovered_text = []
        if not active_has:
            # Independent BM25 retrieval sees only the question and deferred text.
            # The expected evidence string is consulted only after retrieval for scoring.
            candidates = retrieve_bm25(query, store, top_k=3)
            for sid, _score in candidates:
                hydrated_ids.append(sid)
                try:
                    recovered_text.append(hydrate_verified(sid, store, segment_hashes))
                except (KeyError, ValueError):
                    reconstruction_failures += 1
        found = active_has or any(fact.casefold() in text.casefold() for text in recovered_text)
        if found:
            recovered += 1
        hydration_calls += len(hydrated_ids)
        total_active += lexical_units(active)
        registry_units = lexical_units(variant["registry"])
        total_registry += registry_units
        total_hydration_prompt += 12 * len(hydrated_ids)
        total_retrieved += sum(lexical_units(x) for x in recovered_text)
        total_output += 8
        traces.append({
            "question_id": qid, "evidence_label": label, "query": query, "evidence": fact,
            "retrieval_mode": "bm25_lexical_top_3",
            "retrieval_candidates": [{"entry_id": sid, "score": round(score, 6)} for sid, score in candidates] if not active_has else [],
            "visible_without_hydration": active_has,
            "hydrated_entry_ids": hydrated_ids,
            "registry_lexical_units": registry_units,
            "hydrated_sha256_verified": [sid for sid in hydrated_ids if sid in segment_hashes and sha256(store[sid].encode("utf-8")) == segment_hashes[sid]],
            "evidence_recovered": found,
            "retrieval_elapsed_ms": round((time.perf_counter() - q_start) * 1000, 4),
        })

    baseline_per_task = lexical_units(baseline_context) + 8
    baseline_total = baseline_per_task * len(QUESTIONS)
    policy_total = total_active + total_registry + total_hydration_prompt + total_retrieved + total_output
    return {
        "policy": name, "defer_from_tier": defer_from, "observations": len(QUESTIONS),
        "baseline_total_lexical_units": baseline_total,
        "policy_active_lexical_units": total_active,
        "registry_lexical_units": total_registry,
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
    segments, source_hashes, source_archives, evidence_text, segment_hashes = load_real_documents()
    for qid, label, query, fact, source in QUESTIONS:
        if fact.casefold() not in evidence_text[source].casefold():
            raise SystemExit(f"Evidence fixture {qid} not found in {source}: {fact!r}")

    baseline_context = join(segments)
    corpus_hash = sha256(baseline_context.encode("utf-8"))
    policies = [
        evaluate_policy("T3", segments, 3, baseline_context, QUESTIONS, segment_hashes),
        evaluate_policy("T4", segments, 4, baseline_context, QUESTIONS, segment_hashes),
        evaluate_policy("T5", segments, 5, baseline_context, QUESTIONS, segment_hashes),
    ]
    baseline_recall = 1.0
    archive_report = {}
    source_reconstruction_failures = 0
    for source_name, chunks in source_archives.items():
        try:
            rebuilt = reconstruct_source(chunks, source_hashes[source_name])
            archive_report[source_name] = {
                "chunks": len(chunks), "archived_bytes": sum(len(x["data"]) for x in chunks),
                "reconstructed_sha256": sha256(rebuilt), "byte_exact_round_trip": True,
            }
        except ValueError:
            source_reconstruction_failures += 1
            archive_report[source_name] = {"chunks": len(chunks), "byte_exact_round_trip": False}
    report = {
        "schema_version": 1,
        "status": "PASS" if all(p["evidence_recall"] == baseline_recall and p["reconstruction_failures"] == 0 for p in policies) and source_reconstruction_failures == 0 else "REVIEW",
        "data_status": "REAL_REPOSITORY_DOCUMENTS_DETERMINISTIC_EVIDENCE_TEST",
        "scope": "Offline evaluation on the project's actual README and research documentation; not an external corpus or LLM task benchmark.",
        "method": {
            "implementation": "csc_lch_bench.py build_variants; no-glyph path isolates deduplication, safe text compression, and lazy deferral.",
            "retrieval": "Deterministic BM25 lexical retrieval ranks deferred paragraphs using only the natural-language query; the expected answer is used only after retrieval to score evidence recovery.",
            "retrieval_mode": "bm25_lexical_top_3",
            "tier_assignment": "CURATED FIXTURE: tier_for() assigns tiers from a hand-authored section-name map. This is not an automatic tier classifier and must not be presented as production classification performance.",
            "baseline": "Full uncompressed source context repeated for each of the same 15 evidence questions.",
            "accounting": "Lexical units are a tokenizer-independent proxy, not actual model tokens. Active context and registry instructions are counted for every question; each answer is assigned 8 output units; each hydration prompt is assigned 12 units; retrieved source text is counted separately.",
            "integrity": "Each hydrated deferred paragraph is verified against SHA-256 of its original UTF-8 paragraph. Source-file SHA-256 values are recorded as fingerprints; this experiment does not prove byte-for-byte reconstruction of whole source files from the tiered segments.",
            "tier_coverage": "The historical reported-ablation table is explicitly classified as T5 archive content and Q15 requires retrieval of its 1.40x result.",
            "evidence_recall_interpretation": "Evidence recall measures whether a top-3 lexical retriever returned a paragraph containing the fixture evidence. It is not semantic answer accuracy or end-to-end task quality.",
            "limitations": [
                "No LLM inference or semantic answer scoring.",
                "BM25 is a simple lexical baseline; it does not provide semantic matching or production-grade retrieval.",
                "Tier assignment is curated by section name, not predicted by a classifier.",
                "The 15 evaluation queries are hand-authored and in-domain.",
                "Lexical units are not model tokenizer tokens.",
                "Corpus is real project documentation but small and in-domain.",
                "No provider latency, energy, or monetary cost is measured.",
                "The byte-exact source archive is a separate cold-storage layer; optimized tier text is not itself a byte-for-byte file representation."
            ]
        },
        "commit_sha": os.environ.get("GITHUB_SHA", "local-unpinned"),
        "corpus_sha256": corpus_hash,
        "source_sha256": source_hashes,
        "source_archive": archive_report,
        "source_reconstruction_failures": source_reconstruction_failures,
        "source_paragraphs": len(segments),
        "source_paragraphs_by_tier": {f"T{tier}": sum(1 for seg in segments if seg.tier == tier) for tier in range(6)},
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
    return 0 if report["status"] == "PASS" and all(p["stubs_created"] > 0 and p["registry_lexical_units"] > 0 for p in policies) and policies[-1]["hydration_calls"] > 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
