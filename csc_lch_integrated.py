#!/usr/bin/env python3
"""Integrated CSC LCH prototype: conservative compression + provenance + lazy hydration.

This is a deterministic, offline baseline, not a semantic parser or a validated
compression result. Supply a provider/model tokenizer through token_counter for
real token budgeting. The default counter is explicitly an estimate.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Callable, Iterable

TokenCounter = Callable[[str], int]

_WORD_RE = re.compile(r"[\w'-]+", re.UNICODE)
_SENTENCE_RE = re.compile(r".+?(?:[.!?](?=\s|$)|$)", re.DOTALL)
_PINNED_RE = re.compile(
    r"\b(not|never|no|unless|except|only|must|required|cannot|can't|"
    r"do not|don't|before|after|if|otherwise|at least|at most)\b|\d",
    re.IGNORECASE,
)


def estimated_tokens(text: str) -> int:
    """Rough lexical estimate only; never report this as a real tokenizer count."""
    return len(re.findall(r"\w+|[^\w\s]", text, re.UNICODE))


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _split_sentences(source: str) -> list[str]:
    # Conservative sentence splitting; original source is separately preserved.
    pieces = [m.group(0).strip() for m in _SENTENCE_RE.finditer(source) if m.group(0).strip()]
    return pieces or ([source.strip()] if source.strip() else [])


def _terms(text: str) -> set[str]:
    return {w.casefold() for w in _WORD_RE.findall(text) if len(w) > 1}


@dataclass(frozen=True)
class Unit:
    unit_id: str
    source_index: int
    text: str
    source_sha256: str
    evidence_status: str = "OBS"
    pinned: bool = False


def _make_units(source: str) -> list[Unit]:
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    units: list[Unit] = []
    seen: set[str] = set()
    for index, sentence in enumerate(_split_sentences(source)):
        normalized = _normalize(sentence)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        units.append(Unit(
            unit_id=f"u{index:04d}",
            source_index=index,
            text=sentence,
            source_sha256=digest,
            # OBS means verbatim evidence from the supplied source, not externally verified truth.
            evidence_status="OBS",
            pinned=bool(_PINNED_RE.search(sentence)),
        ))
    return units


def _score(unit: Unit, query_terms: set[str]) -> tuple[int, int, int]:
    overlap = len(_terms(unit.text) & query_terms)
    # Preserve constraints and quantified statements preferentially.
    return (int(unit.pinned), overlap, -unit.source_index)


def compress(
    source: str,
    query: str = "",
    budget: int = 256,
    token_counter: TokenCounter | None = None,
) -> dict:
    """Create a compact prompt payload and a separate source archive.

    The archive is for an external store/tool, not intended to be placed in the
    model prompt. Hydration uses this archive to recover exact original sentences.
    """
    if budget < 0:
        raise ValueError("budget must be >= 0")
    counter = token_counter or estimated_tokens
    units = _make_units(source)
    qterms = _terms(query)

    # Greedy relevance order. Pinned units rank first; stable source order breaks ties.
    ranked = sorted(units, key=lambda u: _score(u, qterms), reverse=True)
    selected: list[Unit] = []
    deferred: list[Unit] = []
    used = 0
    for unit in ranked:
        cost = counter(unit.text)
        if used + cost <= budget:
            selected.append(unit)
            used += cost
        else:
            deferred.append(unit)

    # Keep payload in original order for readability and deterministic behavior.
    selected.sort(key=lambda u: u.source_index)
    deferred.sort(key=lambda u: u.source_index)
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    payload = "\n".join(
        f"[{u.unit_id}|{u.evidence_status}|src={u.source_index}] {u.text}"
        for u in selected
    )
    return {
        "schema": "csc-lch-integrated-v0.1",
        "source_sha256": source_hash,
        "budget": budget,
        "token_count_mode": "custom_exact" if token_counter else "estimated_lexical",
        "selected_units": [asdict(u) for u in selected],
        "deferred_refs": [
            {"unit_id": u.unit_id, "source_index": u.source_index, "source_sha256": u.source_sha256}
            for u in deferred
        ],
        "prompt_payload": payload,
        "measured_payload_tokens": counter(payload),
        "budget_exceeded": counter(payload) > budget,
        "coverage": {
            "unique_units": len(units),
            "selected_units": len(selected),
            "deferred_units": len(deferred),
            "duplicate_sentences_removed": len(_split_sentences(source)) - len(units),
        },
        # Keep outside the prompt in a source store. This is not counted as prompt payload.
        "source_archive": {
            "source_text": source,
            "units": [asdict(u) for u in units],
        },
        "limitations": [
            "Sentence-level heuristic; no full semantic or causal graph is built.",
            "Lexical overlap is not semantic relevance.",
            "The default token counter is an estimate, not a model tokenizer.",
            "Archive storage and retrieval costs must be measured in a real deployment.",
        ],
    }


def hydrate(package: dict, query: str, limit: int = 3) -> dict:
    """Recover deferred source spans relevant to a query, with exact provenance."""
    if limit < 0:
        raise ValueError("limit must be >= 0")
    archive = package.get("source_archive", {})
    expected_hash = package.get("source_sha256")
    source = archive.get("source_text", "")
    actual_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if not source or actual_hash != expected_hash:
        return {"status": "source_unavailable_or_hash_mismatch", "results": []}

    deferred_ids = {item["unit_id"] for item in package.get("deferred_refs", [])}
    deferred = [u for u in archive.get("units", []) if u["unit_id"] in deferred_ids]
    qterms = _terms(query)
    ranked = sorted(
        deferred,
        key=lambda u: (
            len(_terms(u["text"]) & qterms),
            int(u.get("pinned", False)),
            -u["source_index"],
        ),
        reverse=True,
    )
    results = []
    for unit in ranked:
        overlap = len(_terms(unit["text"]) & qterms)
        if qterms and overlap == 0:
            continue
        results.append({
            "unit_id": unit["unit_id"],
            "source_index": unit["source_index"],
            "text": unit["text"],
            "evidence_status": unit["evidence_status"],
            "source_sha256": unit["source_sha256"],
            "lexical_match_count": overlap,
        })
        if len(results) >= limit:
            break
    return {
        "status": "ok",
        "query": query,
        "results": results,
        "note": "Matches are lexical retrieval candidates, not proof that the query was answered.",
    }


def audit(package: dict) -> dict:
    """Check source integrity and accounting consistency without claiming semantic fidelity."""
    archive = package.get("source_archive", {})
    source = archive.get("source_text", "")
    actual_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    expected_hash = package.get("source_sha256")
    unit_ids = [u["unit_id"] for u in archive.get("units", [])]
    selected_ids = {u["unit_id"] for u in package.get("selected_units", [])}
    deferred_ids = {u["unit_id"] for u in package.get("deferred_refs", [])}
    return {
        "source_hash_matches": bool(source) and actual_hash == expected_hash,
        "unit_ids_unique": len(unit_ids) == len(set(unit_ids)),
        "selected_deferred_disjoint": selected_ids.isdisjoint(deferred_ids),
        "all_units_accounted_for": selected_ids | deferred_ids == set(unit_ids),
        "semantic_preservation_verified": False,
        "token_savings_verified": False,
    }


if __name__ == "__main__":
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="UTF-8 text file to compress")
    parser.add_argument("--query", default="", help="task/query used to prioritize context")
    parser.add_argument("--budget", type=int, default=256, help="budget in counter units")
    parser.add_argument("--hydrate", action="store_true", help="retrieve deferred spans for --query")
    args = parser.parse_args()
    with open(args.file, "r", encoding="utf-8") as handle:
        source_text = handle.read()
    result = compress(source_text, args.query, args.budget)
    if args.hydrate:
        result["hydration"] = hydrate(result, args.query)
    result["audit"] = audit(result)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
