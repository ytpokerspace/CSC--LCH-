# CSC-LCH v1.2 — Reversible Compression and Hydration Benchmark

## Purpose

This milestone measures a concrete, reversible dictionary serialization experiment
against the unencoded source. It also measures a lazy payload containing an index
and only explicitly selected documents.

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

## What is measured

- Raw full-context UTF-8 bytes and tokenizer tokens.
- Complete dictionary-encoded payload bytes and tokens, including dictionary
  and JSON overhead.
- Lazy index plus selected-document payload bytes and tokens.
- Exact reconstruction of the full corpus and selected hydrated documents.

## Interpretation limits

This is **lossless dictionary coding**, not semantic summarization. The lazy
benchmark receives selected document IDs from the caller (oracle selection);
it does not measure whether a retriever can find relevant documents. The result
does not establish production LLM savings, answer quality, latency, or API cost.
Provider prompt framing and tool-schema overhead are excluded.

A positive token delta means the encoded payload costs more tokens than the
unencoded baseline. That is a valid and useful result.
