# CSC-LCH v1.2 — Reversible Compression and Hydration Benchmark

## Purpose

This milestone measures a concrete, reversible dictionary serialization
experiment against unencoded source. It also separates the effect of lazy
selection from the overhead of dictionary encoding.

## Run locally

Install the optional tokenizer:

```bash
python -m pip install tiktoken
python csc_lch_compression_bench.py --selected 0,2
python -m unittest discover -s tests -v
```

The benchmark makes no network or model API calls. With `tiktoken` installed,
token counts use the local encoding associated with the selected model (default
`gpt-4o`). Without it, the output clearly labels counts as a lexical proxy,
not model tokens.

## Comparisons

- Raw full context.
- Complete lossless dictionary-encoded corpus, including dictionary and JSON overhead.
- Selected raw documents without an index (lower-bound context reference).
- Lazy index plus selected raw documents.
- Lazy index plus dictionary-encoded selected documents.

All selected-document variants use caller-supplied IDs (oracle selection).
Exact reconstruction is checked for the full corpus and selected documents.

## Interpretation limits

This is **lossless dictionary coding**, not semantic summarization. The benchmark
does not measure whether a retrieval model selects relevant documents, answer
quality, latency, or production API cost. Token counts are local tokenizer
counts, not provider billing; prompt framing, system instructions, and tool
schemas are excluded.

A positive token delta means the payload costs more tokens than the baseline.
That is a valid result and must not be presented as a saving.
