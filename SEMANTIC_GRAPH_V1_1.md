# CSC-LCH Semantic Graph Engine (v1.1)

This directory-level addition introduces a standard-library-only semantic graph
engine alongside the repository's existing prompt-tier and benchmark work.

## Scope

- Exact source retention with SHA-256 integrity checks.
- Reversible lexical segmentation that preserves whitespace and Unicode.
- Interned symbols with stable integer IDs and memory-ring membership.
- Typed, weighted, undirected relationships.
- Codebook save/load with format-version validation and atomic file replacement.
- Lazy node, neighbor, and source retrieval with a simple audit log.

## Important measurement boundary

The graph indexes tokens but retains the complete original source. It is **not
itself a compression algorithm** and makes no token-saving claim. Compression
must be evaluated separately against the repository's existing benchmark
baseline, including reconstruction and quality checks.

## Run tests

From the repository root:

```bash
python -m unittest discover -s tests -v
```

No API key, network access, or third-party dependency is required.
