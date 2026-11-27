#!/usr/bin/env python3
"""Deterministic, dependency-free hybrid retrieval prototype for CSC-LCH.

This is a retrieval layer, not a semantic embedding model or a replacement for
source-preserving CSC-LCH compression. It ranks sentence windows with BM25,
query coverage, exact-phrase and identifier signals, then applies a budget-aware
diversity pass. Original text and offsets are retained for later hydration.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Iterable

TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[._:/-][A-Za-z0-9]+)*")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by",
    "for", "from", "had", "has", "have", "he", "her", "his", "i", "if",
    "in", "into", "is", "it", "its", "of", "on", "or", "our", "she",
    "that", "the", "their", "them", "there", "these", "they", "this",
    "to", "was", "we", "were", "what", "when", "where", "which", "who",
    "will", "with", "you", "your",
})


def terms(text: str) -> list[str]:
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text)]


def _identifiers(text: str) -> set[str]:
    found = set()
    for token in TOKEN_RE.finditer(text):
        value = token.group(0)
        if any(ch.isdigit() for ch in value) or any(ch in "._:/-" for ch in value):
            found.add(value.lower())
    return found


@dataclass(frozen=True)
class RetrievalConfig:
    top_k: int = 5
    max_chars: int = 6000
    bm25_k1: float = 1.2
    phrase_boost: float = 2.0
    identifier_boost: float = 3.0
    coverage_weight: float = 1.0
    diversity_penalty: float = 0.20

    def validate(self) -> None:
        if self.top_k < 1 or self.max_chars < 1:
            raise ValueError("top_k and max_chars must be positive")
        if self.overlap_sentences < 0:
            raise ValueError("overlap_sentences cannot be negative")
        for name in ("bm25_k1", "phrase_boost", "identifier_boost",
                     "coverage_weight", "diversity_penalty"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str
    start: int
    end: int
    index: int


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: str
    text: str
    start: int
    end: int
    score: float
    matched_terms: tuple[str, ...]
    exact_phrase_match: bool
    identifier_matches: tuple[str, ...]


@dataclass(frozen=True)
class RetrievalResult:
    query: str
    hits: tuple[RetrievalHit, ...]
    retrieved_text: str
    source_characters: int
    retrieved_characters: int
    config: dict

    @property
    def character_reduction_fraction(self) -> float:
        if not self.source_characters:
            return 0.0
        return 1.0 - self.retrieved_characters / self.source_characters


def sentence_chunks(text: str) -> list[Chunk]:
    """Split into sentence-sized retrieval units with exact character offsets."""
    if not text:
        return []
    spans = []
    start = 0
    for match in SENTENCE_RE.finditer(text):
        end = match.start()
        if text[start:end].strip():
            left = start
            while left < end and text[left].isspace():
                left += 1
            right = end
            while right > left and text[right - 1].isspace():
                right -= 1
            spans.append((left, right))
        start = match.end()
    if text[start:].strip():
        left = start
        while left < len(text) and text[left].isspace():
            left += 1
        right = len(text)
        while right > left and text[right - 1].isspace():
            right -= 1
        spans.append((left, right))
    chunks = []
    for index, (left, right) in enumerate(spans):
        chunk_id = f"c{index:06d}-{left}-{right}"
        chunks.append(Chunk(chunk_id, text[left:right], left, right, index))
    return chunks


def _bm25(query_terms: list[str], documents: list[list[str]], k1: float) -> list[float]:
    if not documents or not query_terms:
        return [0.0] * len(documents)
    n = len(documents)
    avg_len = sum(map(len, documents)) / max(1, n)
    doc_freq = {}
    for doc in documents:
        for term in set(doc):
            doc_freq[term] = doc_freq.get(term, 0) + 1
    scores = []
    for doc in documents:
        counts = {}
        for term in doc:
            counts[term] = counts.get(term, 0) + 1
        score = 0.0
        for term in set(query_terms):
            tf = counts.get(term, 0)
            if not tf:
                continue
            df = doc_freq.get(term, 0)
            idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
            denom = tf + k1 * (1.0 - 0.75 + 0.75 * len(doc) / max(avg_len, 1.0))
            score += idf * tf * (k1 + 1.0) / denom
        scores.append(score)
    return scores


def retrieve(context: str, query: str, config: RetrievalConfig | None = None) -> RetrievalResult:
    config = config or RetrievalConfig()
    config.validate()
    chunks = sentence_chunks(context)
    query_tokens = [t for t in terms(query) if t not in STOPWORDS]
    query_set = set(query_tokens)
    query_phrase = " ".join(query.strip().lower().split())
    query_ids = _identifiers(query)
    doc_terms = [terms(chunk.text) for chunk in chunks]
    bm25_scores = _bm25(query_tokens, doc_terms, config.bm25_k1)
    scored = []
    for chunk, tokens, bm25 in zip(chunks, doc_terms, bm25_scores):
        present = set(tokens)
        matched = tuple(sorted(query_set & present))
        phrase_match = bool(query_phrase and query_phrase in " ".join(chunk.text.lower().split()))
        id_matches = tuple(sorted(query_ids & _identifiers(chunk.text)))
        coverage = len(matched) / max(1, len(query_set))
        score = bm25 + config.coverage_weight * coverage
        if phrase_match:
            score += config.phrase_boost
        score += config.identifier_boost * len(id_matches)
        scored.append((score, chunk, matched, phrase_match, id_matches, present))

    # Greedy maximal-marginal-relevance-style selection. Penalize overlap in
    # query terms, but never discard source text or alter its stored offsets.
    remaining = list(scored)
    chosen = []
    used_chars = 0
    covered_terms: set[str] = set()
    while remaining and len(chosen) < config.top_k:
        best_pos = None
        best_value = float("-inf")
        for pos, item in enumerate(remaining):
            score, chunk, matched, phrase, ids, present = item
            cost = len(chunk.text)
            if used_chars + cost > config.max_chars:
                continue
            overlap = len(covered_terms & set(matched)) / max(1, len(matched))
            adjusted = score - config.diversity_penalty * overlap
            # Stable source-order tie-break.
            adjusted -= chunk.index * 1e-12
            if adjusted > best_value:
                best_value, best_pos = adjusted, pos
        if best_pos is None:
            break
        item = remaining.pop(best_pos)
        chosen.append(item)
        used_chars += len(item[1].text)
        covered_terms.update(item[2])

    chosen.sort(key=lambda item: item[1].index)
    hits = tuple(
        RetrievalHit(chunk.chunk_id, chunk.text, chunk.start, chunk.end,
                     round(score, 8), matched, phrase, ids)
        for score, chunk, matched, phrase, ids, _ in chosen
    )
    retrieved = "\n".join(hit.text for hit in hits)
    return RetrievalResult(
        query=query, hits=hits, retrieved_text=retrieved,
        source_characters=len(context), retrieved_characters=len(retrieved),
        config=asdict(config),
    )


def result_to_dict(result: RetrievalResult) -> dict:
    return {
        "query": result.query,
        "hits": [
            {"chunk_id": h.chunk_id, "text": h.text, "start": h.start,
             "end": h.end, "score": h.score, "matched_terms": list(h.matched_terms),
             "exact_phrase_match": h.exact_phrase_match,
             "identifier_matches": list(h.identifier_matches)}
            for h in result.hits
        ],
        "retrieved_text": result.retrieved_text,
        "source_characters": result.source_characters,
        "retrieved_characters": result.retrieved_characters,
        "character_reduction_fraction": round(result.character_reduction_fraction, 8),
        "config": result.config,
        "measurement_note": "Character reduction only; use the target model tokenizer for token claims.",
    }
